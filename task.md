# 实时字幕系统 - 执行任务清单

> 📌 **Claude Code 专用**: 按照本文档的步骤顺序执行开发任务

---

## 📋 执行前准备

### 1. 阅读文档（必须按顺序）

```
第1步: claude.md                              # 了解当前状态和规范
第2步: .ai-rules/README.md                    # 项目概览
第3步: .ai-rules/architecture.md              # 理解架构设计
第4步: .ai-rules/implementation-roadmap.md    # 详细实施计划
第5步: .ai-rules/technical/critical-fixes.md  # ⚠️ 必读：12个P0修复
```

### 2. 确认环境配置

- [ ] `.env.example` 已创建（包含API Keys配置模板）
- [ ] `requirements.txt` 已创建（包含所有依赖）
- [ ] `app/__init__.py` 已存在（空文件）
- [ ] VB-Cable 虚拟音频驱动已安装（用户环境）

---

## 🚀 阶段1：基础MVP版本

**目标**: 实现核心功能链路（音频捕获 → 转录 → 翻译 → 显示）
**代码总量**: 340行（4个模块）
**P0修复**: 应用6个基础修复

### 任务1.1：实现 `app/subtitle_storage.py` (~50行)

**阅读文档**:
- `.ai-rules/modules/storage.md`
- `.ai-rules/technical/critical-fixes.md` (第9条: 字幕时长计算)

**实现内容**:
```python
class SubtitleStorage:
    - __init__(): 初始化字幕列表和起始时间
    - add_subtitle(original, translation): 添加字幕
    - export_srt(filepath): 导出SRT格式
    - format_srt_time(seconds): 格式化时间戳
    - clear(): 清空字幕
```

**P0修复应用**:
- ✅ 字幕时长根据下一条字幕计算（不固定5秒）

**验收标准**:
- [ ] 类定义正确，方法签名符合设计文档
- [ ] `export_srt()` 生成的SRT格式正确（使用逗号分隔毫秒）
- [ ] 时长计算使用下一条字幕时间戳

**日志记录**:
```
[YYYY-MM-DD HH:MM:SS] [阶段1] [subtitle_storage] 开始实现
[YYYY-MM-DD HH:MM:SS] [阶段1] [subtitle_storage] 完成，共50行，应用1个P0修复
```

**更新进度**:
- 更新 `PROGRESS.md` 表格：状态改为 ✅，记录行数和完成时间
- 追加日志到 `logs/development.log`
- 创建 `logs/modules/storage.log` 记录详细实施过程

---

### 任务1.2：实现 `app/audio_capture.py` (~80行，基础版)

**阅读文档**:
- `.ai-rules/modules/audio-capture.md` (仅阅读"阶段1基础版本"部分)
- `.ai-rules/technical/critical-fixes.md` (第5条、第11条)

**实现内容**:
```python
class AudioCaptureThread(threading.Thread):
    - __init__(audio_queue, stop_event): 初始化参数
    - find_cable_device(audio): 查找VB-Cable输出设备
    - run(): 主循环（捕获5秒音频 → 放入队列）
    - capture_chunk(stream): 捕获固定5秒音频块
```

**关键参数**:
```python
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 2          # 立体声
RATE = 48000          # VB-Cable默认采样率
CHUNK_DURATION = 5    # 秒
```

**P0修复应用**:
- ✅ `Queue.put(audio_chunk, timeout=1)` 避免阻塞
- ✅ `stream.read(self.CHUNK, exception_on_overflow=False)` 捕获异常
- ✅ 异常时填充静音数据: `b'\x00' * (self.CHUNK * 2)`

**注意事项**:
- ⚠️ 阶段1**不实现VAD**，所有音频都处理
- ⚠️ 阶段1**不实现重采样**，保持48kHz立体声
- ✅ 设置 `daemon=True`

**验收标准**:
- [ ] 能找到VB-Cable设备（关键词: "cable output"）
- [ ] 每5秒产生一个音频块
- [ ] 应用了2个P0修复（Queue.put timeout, stream.read异常处理）

**日志记录**:
```
[YYYY-MM-DD HH:MM:SS] [阶段1] [audio_capture] 开始实现基础版本
[YYYY-MM-DD HH:MM:SS] [阶段1] [audio_capture] 完成，共80行，应用2个P0修复
```

**更新进度**:
- 更新 `PROGRESS.md`
- 追加 `logs/development.log`
- 创建 `logs/modules/audio_capture.log`

---

### 任务1.3：实现 `app/transcription.py` (~60行，基础版)

**阅读文档**:
- `.ai-rules/modules/transcription.md` (仅阅读"阶段1基础版本"部分)

**实现内容**:
```python
class TranscriptionThread(threading.Thread):
    - __init__(audio_queue, stop_event, callback, openai_key, deepl_key)
    - run(): 主循环（获取音频 → 转录 → 翻译 → 回调）
    - transcribe(audio_data): 调用Whisper API
    - translate(text): 调用DeepL API
```

**关键逻辑**:
```python
def run(self):
    while not self.stop_event.is_set():
        try:
            audio_data = self.audio_queue.get(timeout=1)
        except queue.Empty:
            continue

        # 转录
        original_text = self.transcribe(audio_data)
        if not original_text.strip():
            continue

        # 翻译
        translated_text = self.translate(original_text)

        # 回调GUI
        self.callback(original_text, translated_text)
```

**API调用**:
```python
# Whisper API
response = self.openai_client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_file,  # BytesIO对象，设置name="audio.wav"
    language="en"
)

# DeepL API
result = self.deepl_translator.translate_text(
    text,
    target_lang="ZH"
)
```

**注意事项**:
- ⚠️ 阶段1**不实现重试机制**，简单记录错误
- ⚠️ 阶段1**不检查VAD静音**
- ✅ 空字幕跳过不回调
- ✅ 设置 `daemon=True`

**验收标准**:
- [ ] 能正确调用Whisper API
- [ ] 能正确调用DeepL API
- [ ] 空字幕正确跳过
- [ ] 使用 `queue.Empty` 异常处理

**日志记录**:
```
[YYYY-MM-DD HH:MM:SS] [阶段1] [transcription] 开始实现基础版本
[YYYY-MM-DD HH:MM:SS] [阶段1] [transcription] 完成，共60行
```

**更新进度**:
- 更新 `PROGRESS.md`
- 追加 `logs/development.log`
- 创建 `logs/modules/transcription.log`

---

### 任务1.4：实现 `app/main.py` (~150行)

**阅读文档**:
- `.ai-rules/modules/gui-main.md` (仅阅读"阶段1基础版本"部分)
- `.ai-rules/technical/critical-fixes.md` (第4条、第6条、第7条)

**实现内容**:
```python
class SubtitleApp:
    - __init__(root): 创建GUI组件和线程变量
    - create_widgets(): 创建界面布局
    - start_capture(): 启动音频和转录线程
    - stop_capture(): 停止线程并清理
    - on_subtitle_ready(original, translation): 线程回调（线程安全）
    - update_subtitle(original, translation): 更新GUI显示
    - export_srt(): 导出SRT文件
```

**GUI布局**:
```python
# 控制按钮
btn_start = tk.Button(text="开始捕获", command=self.start_capture)
btn_stop = tk.Button(text="停止", command=self.stop_capture)
btn_export = tk.Button(text="导出SRT", command=self.export_srt)

# 原文显示区
self.original_text = tk.Text(height=10)

# 翻译显示区
self.translated_text = tk.Text(height=10)
```

**P0修复应用**:
- ✅ `self.audio_queue = queue.Queue(maxsize=10)` 防止内存泄漏
- ✅ `self.storage_lock = threading.Lock()` 保护并发访问
- ✅ 线程清理时清空队列（加速退出）

**关键实现**:
```python
def stop_capture(self):
    # 1. 设置停止信号
    self.stop_event.set()

    # 2. 等待音频线程停止
    if self.audio_thread:
        self.audio_thread.join(timeout=5)

    # 3. 清空队列
    while not self.audio_queue.empty():
        try:
            self.audio_queue.get_nowait()
        except queue.Empty:
            break

    # 4. 等待转录线程停止
    if self.transcription_thread:
        self.transcription_thread.join(timeout=10)

def on_subtitle_ready(self, original, translation):
    # 线程安全的GUI更新
    self.root.after(0, self.update_subtitle, original, translation)

def update_subtitle(self, original, translation):
    # 更新GUI
    self.original_text.insert(tk.END, original + "\n")
    self.original_text.see(tk.END)
    self.translated_text.insert(tk.END, translation + "\n")
    self.translated_text.see(tk.END)

    # 使用锁保护
    with self.storage_lock:
        self.subtitle_storage.add_subtitle(original, translation)
```

**入口代码**:
```python
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    root = tk.Tk()
    root.title("实时字幕系统")
    root.geometry("800x600")

    app = SubtitleApp(root)
    root.mainloop()
```

**验收标准**:
- [ ] GUI正确显示（3个按钮 + 2个文本框）
- [ ] 应用了3个P0修复（Queue maxsize, Lock, 队列清空）
- [ ] 使用 `root.after(0, ...)` 确保GUI更新在主线程
- [ ] 线程设置 `daemon=True`

**日志记录**:
```
[YYYY-MM-DD HH:MM:SS] [阶段1] [main] 开始实现GUI主程序
[YYYY-MM-DD HH:MM:SS] [阶段1] [main] 完成，共150行，应用3个P0修复
```

**更新进度**:
- 更新 `PROGRESS.md`
- 追加 `logs/development.log`
- 创建 `logs/modules/gui_main.log`

---

### 任务1.5：阶段1功能测试

**测试步骤**:
1. 运行 `python app/main.py`
2. 点击"开始捕获"
3. 播放测试视频（YouTube等）
4. 观察字幕是否显示
5. 点击"导出SRT"，检查文件格式
6. 点击"停止"，确认正常停止

**验收标准**:
- [ ] ✅ 能捕获VB-Cable音频
- [ ] ✅ 字幕正确显示在窗口
- [ ] ✅ 能导出SRT文件
- [ ] ✅ 原文和翻译都正确
- [ ] ✅ 停止按钮正常工作

**P0修复验收**:
- [ ] Queue设置maxsize=10 ✅
- [ ] Queue.put()使用timeout=1 ✅
- [ ] SubtitleStorage使用Lock保护 ✅
- [ ] 字幕时长根据下一条计算 ✅
- [ ] 线程清理清空队列 ✅
- [ ] PyAudio异常捕获 ✅

**已知问题（阶段2修复）**:
- ⚠️ 长时间运行内存稳定性待验证（无VAD，所有音频都处理）
- ⚠️ API失败没有重试
- ⚠️ 静音段也会调用API（浪费成本）

**日志记录**:
```
[YYYY-MM-DD HH:MM:SS] [阶段1] [测试] 开始功能测试
[YYYY-MM-DD HH:MM:SS] [阶段1] [测试] 测试通过，字幕正常显示和导出
[YYYY-MM-DD HH:MM:SS] [阶段1] [验收] 阶段1完成 ✅，6个P0修复已应用
```

**更新状态**:
- 更新 `PROGRESS.md`: 阶段1状态改为 ✅，更新统计信息
- 更新 `claude.md`: 当前阶段改为"阶段1完成 ✅"
- 更新 `.ai-rules/README.md`: 勾选阶段1所有任务
- 追加 `logs/development.log`

---

## ⚡ 阶段2：优化版本

**目标**: 集成VAD节省30-50%成本 + 错误重试提升稳定性
**新增代码**: ~150行（1个新模块）
**修改代码**: ~100行（更新3个模块）
**P0修复**: 应用全部12个修复

### 任务2.1：实现 `app/silero_vad_iterator.py` (~150行)

**阅读文档**:
- `.ai-rules/technical/vad-optimization.md`
- `.ai-rules/technical/critical-fixes.md` (第1条: VADIterator实例变量)
- `example/WhisperLiveKit-main/whisperlivekit/silero_vad_iterator.py` (参考实现)

**实现内容**:
```python
class VADIterator:
    - __init__(model, threshold, sampling_rate, min_silence_duration_ms, speech_pad_ms)
    - __call__(x, return_seconds): 处理音频块，返回语音段信息
    - reset_states(): 重置状态

class FixedVADIterator(VADIterator):
    - __init__(*args, **kwargs): 继承父类，添加缓冲区
    - __call__(x, return_seconds): 处理任意长度音频
```

**⚠️ 关键修复（P0）**:
```python
class VADIterator:
    def __init__(self, ...):
        # ✅ 必须是实例变量，不能是类变量！
        self.speech_start = None
        self.triggered = False
        self.temp_end = 0
        self.current_sample = 0
```

**参数验证**:
```python
if not 0.0 <= threshold <= 1.0:
    raise ValueError("VAD_THRESHOLD 必须在 0.0-1.0 范围内")
```

**验收标准**:
- [ ] VADIterator.speech_start 是实例变量（self.speech_start）
- [ ] 参数验证正确（threshold 0-1）
- [ ] FixedVADIterator 支持任意长度音频

**日志记录**:
```
[YYYY-MM-DD HH:MM:SS] [阶段2] [silero_vad_iterator] 开始实现VAD封装
[YYYY-MM-DD HH:MM:SS] [阶段2] [silero_vad_iterator] 完成，共150行，应用1个P0修复
```

**更新进度**:
- 更新 `PROGRESS.md`
- 追加 `logs/development.log`
- 创建 `logs/modules/vad_iterator.log`

---

### 任务2.2：更新 `app/audio_capture.py` (+40行)

**阅读文档**:
- `.ai-rules/modules/audio-capture.md` (阅读"阶段2优化版本"部分)
- `.ai-rules/technical/critical-fixes.md` (第2条、第3条、第8条)

**新增功能**:
1. 集成VAD检测
2. 立体声→单声道转换（⚠️ 使用int32避免溢出）
3. 48kHz→16kHz重采样（⚠️ 使用scipy）
4. VAD模型加载3次重试

**关键修改**:
```python
class AudioCaptureThread(threading.Thread):
    def __init__(self, audio_queue, stop_event, enable_vad=False):
        # ... 原有参数 ...
        self.enable_vad = enable_vad
        self.vad_model = None
        self.vad_iterator = None
        self.is_silence = False
        self.silence_count = 0

        if enable_vad:
            self._init_vad()

    def _init_vad(self):
        # ⚠️ 3次重试加载模型
        for attempt in range(3):
            try:
                import torch
                self.vad_model, _ = torch.hub.load(
                    "snakers4/silero-vad",
                    model="silero_vad",
                    force_reload=False
                )

                vad_threshold = float(os.getenv('VAD_THRESHOLD', '0.5'))
                if not 0.0 <= vad_threshold <= 1.0:
                    raise ValueError("VAD_THRESHOLD 必须在 0.0-1.0 范围内")

                self.vad_iterator = FixedVADIterator(
                    self.vad_model,
                    threshold=vad_threshold,
                    sampling_rate=16000,
                    min_silence_duration_ms=int(os.getenv('VAD_MIN_SILENCE_MS', '500'))
                )
                print("[INFO] VAD模型加载成功")
                break
            except Exception as e:
                if attempt == 2:
                    print(f"[WARNING] VAD加载失败，禁用VAD: {e}")
                    self.enable_vad = False

    def _run_vad(self, audio_data):
        # 1. 立体声→单声道（⚠️ 必须用int32避免溢出）
        audio_np = np.frombuffer(audio_data, dtype=np.int16)
        stereo = audio_np.reshape(-1, 2)
        mono = stereo.astype(np.int32).mean(axis=1).astype(np.int16)

        # 2. 48kHz → 16kHz（⚠️ 必须用scipy重采样）
        from scipy import signal
        audio_16k = signal.resample_poly(mono, up=1, down=3)

        # 3. 归一化到 float32 [-1, 1]
        audio_float32 = audio_16k.astype(np.float32) / 32768.0

        # 4. VAD检测
        result = self.vad_iterator(audio_float32, return_seconds=False)

        # 5. 静音判断: 连续2次静音（10秒）才标记为静音
        if result and 'end' in result:
            self.silence_count += 1
            if self.silence_count >= 2:
                self.is_silence = True
        else:
            self.is_silence = False
            self.silence_count = 0

    def is_silent_audio(self):
        return self.is_silence and self.silence_count >= 2
```

**P0修复应用**:
- ✅ 立体声转单声道使用int32
- ✅ 重采样使用scipy.signal.resample_poly()
- ✅ VAD模型加载3次重试
- ✅ VAD参数验证（threshold 0-1）

**验收标准**:
- [ ] 应用了4个P0修复
- [ ] VAD模型加载失败时禁用VAD（不崩溃）
- [ ] 静音检测正确（连续2次静音才标记）

**日志记录**:
```
[YYYY-MM-DD HH:MM:SS] [阶段2] [audio_capture] 开始集成VAD
[YYYY-MM-DD HH:MM:SS] [阶段2] [audio_capture] 完成，新增40行，应用4个P0修复
```

**更新进度**:
- 更新 `PROGRESS.md`
- 追加 `logs/development.log`
- 追加 `logs/modules/audio_capture.log`

---

### 任务2.3：更新 `app/transcription.py` (+40行)

**阅读文档**:
- `.ai-rules/modules/transcription.md` (阅读"阶段2优化版本"部分)

**新增功能**:
1. 错误重试机制（3次，指数退避）
2. VAD静音段跳过

**关键修改**:
```python
class TranscriptionThread(threading.Thread):
    def __init__(self, audio_queue, stop_event, callback,
                 openai_key, deepl_key, audio_thread=None):
        # ... 原有参数 ...
        self.audio_thread = audio_thread  # 传入音频线程引用

    def run(self):
        while not self.stop_event.is_set():
            try:
                audio_data = self.audio_queue.get(timeout=1)
            except queue.Empty:
                continue

            # ⚠️ VAD检查: 跳过静音段
            if self.audio_thread and self.audio_thread.is_silent_audio():
                print("[INFO] [VAD] 跳过静音段，节省API成本")
                continue

            # 转录（带重试）
            original_text = self.transcribe(audio_data)
            if not original_text:
                continue

            # 翻译（带重试）
            translated_text = self.translate(original_text)
            if not translated_text:
                continue

            # 回调
            self.callback(original_text, translated_text)

    def transcribe(self, audio_data):
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                # ... 原有API调用代码 ...
                return response.text

            except Exception as e:
                print(f"[ERROR] Whisper API调用失败 (尝试{attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)  # 指数退避
                    time.sleep(delay)
                else:
                    return None
```

**验收标准**:
- [ ] API失败自动重试（3次）
- [ ] 重试使用指数退避（1s, 2s, 4s）
- [ ] VAD静音段正确跳过

**日志记录**:
```
[YYYY-MM-DD HH:MM:SS] [阶段2] [transcription] 开始添加重试和VAD跳过
[YYYY-MM-DD HH:MM:SS] [阶段2] [transcription] 完成，新增40行
```

**更新进度**:
- 更新 `PROGRESS.md`
- 追加 `logs/development.log`
- 追加 `logs/modules/transcription.log`

---

### 任务2.4：更新 `app/main.py` (+50行)

**阅读文档**:
- `.ai-rules/modules/gui-main.md` (阅读"阶段2优化版本"部分)
- `.ai-rules/technical/critical-fixes.md` (第10条: 配置验证)

**新增功能**:
1. 配置验证（支持多种格式）
2. 传递音频线程引用给转录线程

**关键修改**:
```python
def start_capture(self):
    # 配置验证（支持多种格式）
    enable_vad = os.getenv('ENABLE_VAD', 'true').lower()
    vad_enabled = enable_vad in ['true', '1', 'yes', 'on']

    # 启动音频线程（带VAD）
    self.audio_thread = AudioCaptureThread(
        self.audio_queue,
        self.stop_event,
        enable_vad=vad_enabled
    )
    self.audio_thread.daemon = True
    self.audio_thread.start()

    # 启动转录线程（传入音频线程引用）
    self.transcription_thread = TranscriptionThread(
        self.audio_queue,
        self.stop_event,
        self.on_subtitle_ready,
        openai_key,
        deepl_key,
        audio_thread=self.audio_thread  # ← 传递引用
    )
    self.transcription_thread.daemon = True
    self.transcription_thread.start()
```

**P0修复应用**:
- ✅ 配置验证支持多种格式（true/1/yes/on）

**验收标准**:
- [ ] 配置验证支持多种格式
- [ ] 音频线程引用正确传递

**日志记录**:
```
[YYYY-MM-DD HH:MM:SS] [阶段2] [main] 开始添加配置验证和VAD集成
[YYYY-MM-DD HH:MM:SS] [阶段2] [main] 完成，新增50行，应用1个P0修复
```

**更新进度**:
- 更新 `PROGRESS.md`
- 追加 `logs/development.log`
- 追加 `logs/modules/gui_main.log`

---

### 任务2.5：阶段2功能测试

**测试步骤**:
1. 在 `.env` 中设置 `ENABLE_VAD=true`
2. 运行 `python app/main.py`
3. 播放测试视频（包含静音段）
4. 观察日志中的"[VAD] 跳过静音段"
5. 运行1小时，检查内存稳定性

**验收标准**:
- [ ] ✅ VAD模型成功加载
- [ ] ✅ 日志显示跳过静音段
- [ ] ✅ VAD节省成本30-50%（查看统计）
- [ ] ✅ API失败自动重试
- [ ] ✅ 运行1小时内存稳定

**P0修复总验收（12个）**:

**阶段1修复（6个）**:
- [ ] Queue设置maxsize=10 ✅
- [ ] Queue.put()使用timeout=1 ✅
- [ ] SubtitleStorage使用Lock保护 ✅
- [ ] 字幕时长根据下一条计算 ✅
- [ ] 线程清理清空队列 ✅
- [ ] PyAudio异常捕获 ✅

**阶段2新增修复（6个）**:
- [ ] VADIterator.speech_start实例变量 ✅
- [ ] 立体声转单声道使用int32 ✅
- [ ] 重采样使用scipy ✅
- [ ] VAD模型3次重试 ✅
- [ ] VAD参数验证 ✅
- [ ] 配置验证多格式 ✅

**性能统计**:
```
成本节省: 30-50%
API成功率: ≥99.9%
内存: 稳定 < 100MB
停止响应: < 15秒
```

**日志记录**:
```
[YYYY-MM-DD HH:MM:SS] [阶段2] [测试] 开始功能测试
[YYYY-MM-DD HH:MM:SS] [阶段2] [测试] VAD成功跳过静音段，节省40%成本
[YYYY-MM-DD HH:MM:SS] [阶段2] [测试] 运行1小时，内存稳定
[YYYY-MM-DD HH:MM:SS] [阶段2] [验收] 阶段2完成 ✅，全部12个P0修复已应用
```

**更新状态**:
- 更新 `PROGRESS.md`: 阶段2状态改为 ✅，总体完成8/13模块
- 更新 `claude.md`: 当前阶段改为"阶段2完成 ✅"
- 更新 `.ai-rules/README.md`: 勾选阶段2所有任务
- 追加 `logs/development.log`

---

## 🏁 阶段3：完善版本（可选）

**目标**: 生产级稳定性和用户体验优化
**预计时间**: 1天（可选）

**优化项**:
1. 使用Python logging模块（替换print）
2. 线程健康监控和自动恢复
3. GUI增强（窗口关闭事件、状态栏、暗色主题）
4. 导出优化（支持VTT/TXT格式）

**实施步骤**:
- 参考 `.ai-rules/implementation-roadmap.md` 第3节

---

## 📊 文档对齐检查清单

### 项目规模一致性
- [ ] 阶段1: 4个模块，340行代码 ✅
- [ ] 阶段2: 1个新模块 + 3个更新，+190行代码 ✅
- [ ] P0修复: 阶段1需要6个，阶段2需要全部12个 ✅

### 实施顺序一致性
- [ ] 阶段1顺序: subtitle_storage → audio_capture → transcription → main ✅
- [ ] 阶段2顺序: silero_vad_iterator → 更新audio_capture → 更新transcription → 更新main ✅

### 文档引用一致性
- [ ] `claude.md` 与 `README.md` 状态同步 ✅
- [ ] `PROGRESS.md` 与实际代码行数匹配 ✅
- [ ] `implementation-roadmap.md` 与模块设计文档一致 ✅

---

## 🔗 快速参考

### 关键文档速查
- **入口文件**: `claude.md`
- **项目概览**: `.ai-rules/README.md`
- **架构设计**: `.ai-rules/architecture.md`
- **实施路线图**: `.ai-rules/implementation-roadmap.md`
- **P0修复清单**: `.ai-rules/technical/critical-fixes.md`
- **进度追踪**: `PROGRESS.md`
- **开发日志**: `logs/development.log`

### P0修复速查表

| 编号 | 问题 | 位置 | 阶段 |
|-----|------|------|------|
| 1 | VADIterator实例变量 | silero_vad_iterator.py | 阶段2 |
| 2 | 立体声转单声道int32 | audio_capture.py | 阶段2 |
| 3 | scipy重采样 | audio_capture.py | 阶段2 |
| 4 | Queue maxsize=10 | main.py | 阶段1 |
| 5 | Queue.put(timeout=1) | audio_capture.py | 阶段1 |
| 6 | Lock保护SubtitleStorage | main.py | 阶段1 |
| 7 | 线程清理清空队列 | main.py | 阶段1 |
| 8 | VAD模型3次重试 | audio_capture.py | 阶段2 |
| 9 | 字幕时长计算 | subtitle_storage.py | 阶段1 |
| 10 | 配置验证多格式 | main.py | 阶段2 |
| 11 | PyAudio异常捕获 | audio_capture.py | 阶段1 |
| 12 | VAD参数验证 | audio_capture.py | 阶段2 |

---

**最后更新**: 2025-11-06
**文档版本**: v1.0
**状态**: ✅ 已对齐，可执行
