# 转录翻译模块设计

## 📝 模块概述

**文件**: `app/transcription.py`
**职责**: 从队列获取音频，调用Whisper API转录，调用DeepL API翻译，通过回调返回结果

**代码量**:
- 阶段1（基础版）: ~60行
- 阶段2（添加重试）: ~100行

---

## 🎯 核心功能

1. **音频转录**: 调用OpenAI Whisper API将语音转为文字
2. **文本翻译**: 调用DeepL API翻译为中文
3. **错误重试**: 3次重试+指数退避（阶段2）
4. **VAD优化**: 跳过静音段节省成本（阶段2）
5. **线程安全**: 通过回调函数返回结果给GUI主线程

---

## 🔧 类设计

### TranscriptionThread

```python
class TranscriptionThread(threading.Thread):
    """
    转录翻译线程

    职责:
    - 从队列获取音频块
    - 调用Whisper API转录
    - 调用DeepL API翻译
    - 通过回调返回结果
    """

    def __init__(self, audio_queue, stop_event, callback,
                 openai_key, deepl_key, audio_thread=None):
        """
        参数:
            audio_queue (queue.Queue): 音频数据队列
            stop_event (threading.Event): 停止信号
            callback (callable): 回调函数 callback(original, translation)
            openai_key (str): OpenAI API Key
            deepl_key (str): DeepL API Key
            audio_thread (AudioCaptureThread): 音频线程引用（阶段2，用于VAD）
        """
        super().__init__(daemon=True)
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.callback = callback
        self.audio_thread = audio_thread  # 阶段2新增

        # API客户端
        from openai import OpenAI
        import deepl

        self.openai_client = OpenAI(api_key=openai_key)
        self.deepl_translator = deepl.Translator(deepl_key)

    def run(self):
        """线程主循环"""

    def transcribe(self, audio_data):
        """调用Whisper API转录"""

    def translate(self, text):
        """调用DeepL API翻译"""
```

---

## 🚀 阶段1实现（基础版）

### 关键方法实现

#### 1. run()

**职责**: 主循环，获取音频→转录→翻译→回调

```python
def run(self):
    """线程主循环"""
    print("[INFO] 转录翻译线程已启动")

    while not self.stop_event.is_set():
        try:
            # 1. 从队列获取音频（1秒超时）
            audio_data = self.audio_queue.get(timeout=1)
        except queue.Empty:
            continue

        try:
            # 2. 转录
            original_text = self.transcribe(audio_data)
            if not original_text or not original_text.strip():
                continue

            # 3. 翻译
            translated_text = self.translate(original_text)
            if not translated_text:
                continue

            # 4. 回调GUI主线程
            self.callback(original_text, translated_text)

        except Exception as e:
            print(f"[ERROR] 处理音频时发生错误: {e}")
            # 阶段1: 简单记录错误，继续处理下一个

    print("[INFO] 转录翻译线程已停止")
```

**注意事项**:
- ✅ 使用 `timeout=1` 避免无限阻塞
- ✅ `queue.Empty` 异常处理
- ✅ 空字幕跳过，不回调
- ⚠️ 阶段1不处理API重试

---

#### 2. transcribe()

**职责**: 调用OpenAI Whisper API转录音频

```python
def transcribe(self, audio_data):
    """
    调用Whisper API转录

    参数:
        audio_data (bytes): 48kHz立体声音频数据

    返回:
        str: 转录文本，失败返回None
    """
    import io
    import wave

    # 1. 转换为WAV格式
    audio_file = io.BytesIO()
    with wave.open(audio_file, 'wb') as wf:
        wf.setnchannels(2)           # 立体声
        wf.setsampwidth(2)           # 16-bit (2字节)
        wf.setframerate(48000)       # 48kHz
        wf.writeframes(audio_data)

    # 2. 重置指针
    audio_file.seek(0)
    audio_file.name = "audio.wav"  # 必须设置name属性

    # 3. 调用Whisper API
    try:
        response = self.openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en"  # 可从环境变量读取
        )
        return response.text

    except Exception as e:
        print(f"[ERROR] Whisper API调用失败: {e}")
        return None
```

**关键点**:
1. **音频格式转换**: bytes → WAV格式（io.BytesIO）
2. **必须设置name属性**: `audio_file.name = "audio.wav"`
3. **语言参数**: 可选，帮助提高准确率

**注意事项**:
- ✅ WAV参数必须与音频捕获一致（48kHz, 立体声, 16-bit）
- ✅ 使用 `io.BytesIO()` 避免写入磁盘
- ⚠️ 阶段1不实现重试

---

#### 3. translate()

**职责**: 调用DeepL API翻译文本

```python
def translate(self, text):
    """
    调用DeepL API翻译

    参数:
        text (str): 原文（英文）

    返回:
        str: 翻译文本（中文），失败返回None
    """
    try:
        result = self.deepl_translator.translate_text(
            text,
            target_lang="ZH"  # 翻译为中文
        )
        return result.text

    except Exception as e:
        print(f"[ERROR] DeepL API调用失败: {e}")
        return None
```

**支持的目标语言**:
- `ZH`: 中文
- `EN-US`: 英语（美式）
- `JA`: 日语
- `KO`: 韩语
- `FR`: 法语
- `DE`: 德语

**注意事项**:
- ✅ DeepL自动检测源语言
- ✅ 可通过环境变量配置目标语言
- ⚠️ 阶段1不实现重试

---

## ⚡ 阶段2实现（优化版）

### 新增功能

#### 1. VAD静音段跳过

**位置**: `run()` 方法开始处

```python
def run(self):
    print("[INFO] 转录翻译线程已启动")

    while not self.stop_event.is_set():
        try:
            audio_data = self.audio_queue.get(timeout=1)
        except queue.Empty:
            continue

        # ⚠️ 阶段2新增: VAD检查，跳过静音段
        if self.audio_thread and self.audio_thread.is_silent_audio():
            print("[INFO] [VAD] 跳过静音段，节省API成本")
            continue

        # ... 原有转录翻译逻辑 ...
```

**效果**:
- 节省30-50% API成本
- 减少无效处理

---

#### 2. 错误重试机制

**更新 `transcribe()` 方法**:

```python
def transcribe(self, audio_data):
    """
    调用Whisper API转录（带重试）

    重试策略:
    - 最大3次重试
    - 指数退避: 1s → 2s → 4s
    """
    import io
    import wave
    import time

    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            # 1. 转换为WAV格式
            audio_file = io.BytesIO()
            with wave.open(audio_file, 'wb') as wf:
                wf.setnchannels(2)
                wf.setsampwidth(2)
                wf.setframerate(48000)
                wf.writeframes(audio_data)

            audio_file.seek(0)
            audio_file.name = "audio.wav"

            # 2. 调用API
            response = self.openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language="en"
            )

            # 成功，返回结果
            return response.text

        except Exception as e:
            print(f"[ERROR] Whisper API调用失败 (尝试 {attempt+1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                # 指数退避
                delay = retry_delay * (2 ** attempt)
                print(f"[INFO] {delay}秒后重试...")
                time.sleep(delay)
            else:
                # 最终失败
                print("[ERROR] Whisper API调用最终失败")
                return None
```

**更新 `translate()` 方法**:

```python
def translate(self, text):
    """
    调用DeepL API翻译（带重试）

    重试策略:
    - 最大3次重试
    - 指数退避: 1s → 2s → 4s
    """
    import time

    max_retries = 3
    retry_delay = 1.0

    for attempt in range(max_retries):
        try:
            result = self.deepl_translator.translate_text(
                text,
                target_lang="ZH"
            )
            return result.text

        except Exception as e:
            print(f"[ERROR] DeepL API调用失败 (尝试 {attempt+1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                delay = retry_delay * (2 ** attempt)
                print(f"[INFO] {delay}秒后重试...")
                time.sleep(delay)
            else:
                print("[ERROR] DeepL API调用最终失败")
                return None
```

**重试策略说明**:

| 尝试次数 | 延迟时间 | 说明 |
|---------|---------|------|
| 第1次 | 立即 | 首次尝试 |
| 第2次 | 1秒后 | `1 * 2^0 = 1s` |
| 第3次 | 2秒后 | `1 * 2^1 = 2s` |
| 最终失败 | - | 返回None |

**为什么使用指数退避？**
- ✅ 避免"雪崩效应"（大量重试进一步压垮服务器）
- ✅ 给服务端恢复时间
- ✅ 行业标准做法（AWS、Google等都采用）

---

#### 3. 统计信息（可选）

**新增统计字段**:

```python
def __init__(self, ...):
    # ... 原有初始化 ...

    # 统计信息
    self.total_chunks = 0
    self.skipped_chunks = 0
    self.failed_chunks = 0
```

**在 `run()` 方法中更新统计**:

```python
def run(self):
    while not self.stop_event.is_set():
        # ... 获取音频 ...

        # VAD跳过
        if self.audio_thread and self.audio_thread.is_silent_audio():
            self.skipped_chunks += 1
            print(f"[INFO] [VAD] 跳过静音段 (总计跳过: {self.skipped_chunks})")
            continue

        self.total_chunks += 1

        # ... 转录翻译 ...

        if not original_text or not translated_text:
            self.failed_chunks += 1

    # 线程结束时打印统计
    total = self.total_chunks + self.skipped_chunks
    if total > 0:
        savings = (self.skipped_chunks / total) * 100
        success_rate = ((self.total_chunks - self.failed_chunks) / self.total_chunks * 100) if self.total_chunks > 0 else 0
        print(f"[统计] 总音频块: {total}, 跳过: {self.skipped_chunks} ({savings:.1f}%), 成功率: {success_rate:.1f}%")
```

---

## 📊 API调用参数

### Whisper API

```python
response = self.openai_client.audio.transcriptions.create(
    model="whisper-1",           # 模型名称
    file=audio_file,             # 音频文件（io.BytesIO）
    language="en",               # 源语言（可选）
    response_format="text",      # 返回格式（默认）
    temperature=0.0              # 采样温度（可选，0=确定性）
)
```

**支持的音频格式**:
- WAV (推荐)
- MP3
- M4A
- FLAC
- OGG

**最大文件大小**: 25MB

**定价**: $0.006 / 分钟

---

### DeepL API

```python
result = self.deepl_translator.translate_text(
    text,                        # 源文本
    target_lang="ZH",           # 目标语言
    source_lang="EN"            # 源语言（可选，自动检测）
)
```

**免费额度**: 500,000字符/月

**付费定价**: €4.99/月（无限制）

---

## ⚠️ 常见错误和解决方案

### 1. "Invalid API Key"

**原因**: API Key错误或格式不正确

**解决方案**:
```bash
# 验证OpenAI API Key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"

# 验证DeepL API Key
curl https://api-free.deepl.com/v2/usage \
  -H "Authorization: DeepL-Auth-Key YOUR_API_KEY"
```

---

### 2. "Rate limit exceeded"

**原因**: API调用频率过高

**解决方案**:
```python
# 增加重试延迟
retry_delay = 2.0  # 默认1.0 → 2.0秒
```

---

### 3. "Audio file too large"

**原因**: 音频块超过25MB（理论上5秒@48kHz只有960KB，不应该发生）

**解决方案**:
```python
# 减少分块时长
CHUNK_DURATION = 3  # 5秒 → 3秒
```

---

### 4. 翻译结果为空

**原因**: DeepL API配额耗尽

**解决方案**:
```bash
# 检查用量
curl https://api-free.deepl.com/v2/usage \
  -H "Authorization: DeepL-Auth-Key YOUR_API_KEY"
```

---

## 🔍 调试技巧

### 打印API响应

```python
def transcribe(self, audio_data):
    # ... API调用 ...
    response = self.openai_client.audio.transcriptions.create(...)

    print(f"[DEBUG] Whisper响应: {response.text}")
    return response.text
```

### 保存音频块到文件

```python
def run(self):
    while not self.stop_event.is_set():
        audio_data = self.audio_queue.get(timeout=1)

        # 调试: 保存音频
        import wave
        with wave.open(f"debug_{time.time()}.wav", 'wb') as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(audio_data)

        # ... 继续处理 ...
```

### 测试单个API调用

```python
# test_whisper.py
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

with open("test.wav", "rb") as audio_file:
    response = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file
    )
    print(response.text)
```

---

## 📚 依赖项

```python
import threading
import queue
import time
import io
import wave
import os

# API客户端
from openai import OpenAI
import deepl
```

**requirements.txt**:
```txt
openai>=1.0.0
deepl>=1.16.0
python-dotenv>=1.0.0
```

---

## 🎯 性能优化建议

### 1. 并行处理（可选，阶段3）

```python
# 使用ThreadPoolExecutor并行调用Whisper和DeepL
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=2) as executor:
    future_transcribe = executor.submit(self.transcribe, audio_data)
    # 等待转录完成
    original_text = future_transcribe.result()
    # 然后翻译
    translated_text = self.translate(original_text)
```

**注意**: Whisper和DeepL有顺序依赖，无法真正并行

---

### 2. 缓存翻译结果（可选）

```python
# 避免重复翻译相同的文本
self.translation_cache = {}

def translate(self, text):
    if text in self.translation_cache:
        return self.translation_cache[text]

    result = # ... API调用 ...

    self.translation_cache[text] = result
    return result
```

---

**最后更新**: 2025-11-05
**文档版本**: v1.0
