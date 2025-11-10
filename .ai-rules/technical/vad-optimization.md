# VAD优化与成本节省

## 📝 什么是VAD？

**VAD (Voice Activity Detection)** = 语音活动检测

**功能**: 识别音频中是否存在人类语音

**应用**:
- **跳过静音段**: 电影中的安静场景、音乐间奏不发送API
- **降低成本**: 节省30-50%的Whisper API费用
- **提升效率**: 减少无效处理

---

## 🎯 为什么选择Silero VAD？

### 技术对比

| 对比项 | Silero VAD | WebRTC VAD | 简单音量阈值 |
|-------|-----------|-----------|-------------|
| **精度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ |
| **CPU占用** | 中等 | 低 | 极低 |
| **误报率** | 极低 | 中等 | 高 |
| **许可证** | MIT(免费) | BSD(免费) | - |
| **适用场景** | 电影/视频 | 实时通话 | 简单环境 |

### 选择理由

1. **基于深度学习**: 识别准确率高达99%
2. **支持16kHz**: 与Whisper API兼容
3. **MIT许可证**: 商业友好，无需付费
4. **社区活跃**: GitHub 3K+ stars，维护良好
5. **易于集成**: PyTorch模型，一行代码加载

---

## 🔧 VAD工作原理

### 处理流程

```
原始音频 (48kHz, 立体声)
    ↓
立体声 → 单声道 (⚠️ 必须用int32避免溢出)
    ↓
48kHz → 16kHz (⚠️ 必须用scipy重采样)
    ↓
归一化到 float32 [-1, 1]
    ↓
Silero VAD 模型推理
    ↓
语音概率 (0.0 - 1.0)
    ↓
if 概率 > threshold (0.5):
    认为是语音，继续处理
else:
    认为是静音，跳过API调用
```

### 关键参数

#### 1. threshold (语音概率阈值)

```python
VAD_THRESHOLD=0.5  # 默认值
```

**效果**:
- `0.3`: 非常宽松，捕获更多，成本略高
- `0.5`: 平衡（**推荐**）
- `0.7`: 严格，节省更多成本但可能漏检

**调优建议**:
```
背景噪音多 → 降低阈值 (0.3-0.4)
清晰对话   → 默认阈值 (0.5)
成本敏感   → 提高阈值 (0.6-0.7)
```

---

#### 2. min_silence_duration_ms (最小静音持续时间)

```python
VAD_MIN_SILENCE_MS=500  # 默认500毫秒
```

**作用**: 避免短暂停顿被误判为静音

**示例**:
```
说话: "Hello" [停顿300ms] "world"

如果 min_silence_ms=200:
  → 误判为两个独立语音段

如果 min_silence_ms=500:
  → 正确识别为一个连续语音段
```

---

#### 3. speech_pad_ms (语音段填充)

```python
speech_pad_ms=30  # 默认30毫秒
```

**作用**: 在检测到的语音段前后填充时间，避免切掉词语的开头/结尾

---

## 💰 成本节省分析

### 不同内容类型的节省效果

| 内容类型 | 语音占比 | 无VAD成本 | 有VAD成本 | 节省 |
|---------|---------|----------|----------|-----|
| **对话密集片** | 80% | $0.54 | $0.43 | 20% |
| **普通电影** | 60% | $0.54 | $0.32 | 41% |
| **纪录片** | 50% | $0.54 | $0.27 | 50% |
| **音乐MV** | 20% | $0.54 | $0.11 | 80% |
| **在线课程** | 70% | $0.54 | $0.38 | 30% |

**数据说明**: 基于90分钟视频，Whisper API $0.006/分钟

---

### 月度成本对比

**场景**: 每天使用1小时

| 方案 | 月成本 | 年成本 | vs 基础版 |
|-----|-------|-------|----------|
| **基础版 (无VAD)** | $10.80 | $129.60 | - |
| **优化版 (VAD)** | $6.48 | $78.00 | 节省$51.60/年 |

**结论**: VAD优化是最划算的优化，一年可节省$50+

---

## 🚀 集成步骤

### 阶段1: 基础版本（跳过）

不实现VAD，所有音频都处理

---

### 阶段2: 集成VAD

#### 步骤1: 实现 silero_vad_iterator.py

参考 `example/WhisperLiveKit-main/whisperlivekit/silero_vad_iterator.py`

**关键类**:
```python
class VADIterator:
    """基础VAD迭代器，处理512样本的固定窗口"""

class FixedVADIterator(VADIterator):
    """支持任意长度音频的VAD迭代器"""
    # 内部维护缓冲区，每512样本调用一次父类
```

**⚠️ 关键修复**:
```python
class VADIterator:
    def __init__(self, ...):
        # ❌ 错误: 类变量，多实例共享状态
        # speech_start = None

        # ✅ 正确: 实例变量
        self.speech_start = None
        self.triggered = False
        self.temp_end = 0
        self.current_sample = 0
```

---

#### 步骤2: audio_capture.py 集成VAD

**新增初始化逻辑**:
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
        """加载VAD模型（3次重试）"""
        for attempt in range(3):
            try:
                import torch
                self.vad_model, _ = torch.hub.load(
                    "snakers4/silero-vad",
                    model="silero_vad",
                    force_reload=False
                )

                self.vad_iterator = FixedVADIterator(
                    self.vad_model,
                    threshold=float(os.getenv('VAD_THRESHOLD', '0.5')),
                    sampling_rate=16000,
                    min_silence_duration_ms=int(os.getenv('VAD_MIN_SILENCE_MS', '500'))
                )
                print("[INFO] VAD模型加载成功")
                return

            except Exception as e:
                if attempt == 2:
                    print(f"[WARNING] VAD加载失败，禁用VAD: {e}")
                    self.enable_vad = False
```

**新增VAD检测方法**:
```python
def _run_vad(self, audio_data):
    """对音频块运行VAD检测"""
    import numpy as np
    from scipy import signal

    # 1. bytes → numpy数组
    audio_np = np.frombuffer(audio_data, dtype=np.int16)

    # 2. 立体声 → 单声道
    # ⚠️ 必须先转int32避免溢出！
    stereo = audio_np.reshape(-1, 2)
    mono = stereo.astype(np.int32).mean(axis=1).astype(np.int16)

    # 3. 48kHz → 16kHz 重采样
    # ⚠️ 必须使用scipy，不能简单抽取！
    audio_16k = signal.resample_poly(mono, up=1, down=3)

    # 4. 归一化到 float32 [-1, 1]
    audio_float32 = audio_16k.astype(np.float32) / 32768.0

    # 5. VAD检测
    result = self.vad_iterator(audio_float32, return_seconds=False)

    # 6. 更新静音状态
    # 策略: 连续2次静音（10秒）才标记为静音
    if result and 'end' in result:
        self.silence_count += 1
        if self.silence_count >= 2:
            self.is_silence = True
    else:
        self.is_silence = False
        self.silence_count = 0

def is_silent_audio(self):
    """查询当前是否为静音"""
    return self.is_silence and self.silence_count >= 2
```

**在 capture_chunk() 中调用**:
```python
def capture_chunk(self, stream):
    # ... 读取音频 ...
    audio_data = b''.join(frames)

    # VAD检测（如果启用）
    if self.enable_vad and self.vad_iterator:
        self._run_vad(audio_data)

    return audio_data
```

---

#### 步骤3: transcription.py 跳过静音段

```python
class TranscriptionThread(threading.Thread):
    def __init__(self, ..., audio_thread=None):
        # ... 原有参数 ...
        self.audio_thread = audio_thread  # 保存音频线程引用

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

            # ... 转录翻译 ...
```

---

#### 步骤4: main.py 传递配置

```python
def start_capture(self):
    # 读取VAD配置
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

---

## ⚠️ 关键修复说明

### 修复1: 立体声转单声道必须用int32

```python
# ❌ 错误: 直接取平均可能溢出
audio_np = np.frombuffer(audio_data, dtype=np.int16)
mono = audio_np.reshape(-1, 2).mean(axis=1).astype(np.int16)

# ✅ 正确: 先转int32避免溢出
stereo = audio_np.reshape(-1, 2)
mono = stereo.astype(np.int32).mean(axis=1).astype(np.int16)
```

**原因**:
- int16范围: -32768 ~ 32767
- 两个int16相加可能超出范围
- int32范围足够大，不会溢出

---

### 修复2: 重采样必须用scipy

```python
# ❌ 错误: 简单抽取会导致混叠失真
audio_16k = mono[::3]

# ✅ 正确: 抗混叠滤波重采样
from scipy import signal
audio_16k = signal.resample_poly(mono, up=1, down=3)
```

**为什么？**
- 简单抽取违反Nyquist采样定理
- 高频信号会混叠到低频
- VAD准确率下降20-30%

**参数说明**:
- `up=1, down=3`: 48000 Hz ÷ 3 = 16000 Hz
- `resample_poly()`: 多相滤波器，高效且高质量

---

### 修复3: VADIterator实例变量

```python
class VADIterator:
    def __init__(self, ...):
        # ❌ 错误: 如果写在类级别，多实例会共享状态
        # speech_start = None

        # ✅ 正确: 必须是实例变量
        self.speech_start = None
        self.triggered = False
        self.temp_end = 0
```

**原因**: 每个VADIterator实例需要独立的状态机

---

## 📊 统计和监控

### 添加统计代码

```python
# transcription.py
class TranscriptionThread(threading.Thread):
    def __init__(self, ...):
        # ... 原有初始化 ...
        self.total_chunks = 0
        self.skipped_chunks = 0

    def run(self):
        while not self.stop_event.is_set():
            # ... 获取音频 ...

            # VAD检查
            if self.audio_thread and self.audio_thread.is_silent_audio():
                self.skipped_chunks += 1
                print(f"[INFO] [VAD] 跳过静音段 (总计: {self.skipped_chunks})")
                continue

            self.total_chunks += 1
            # ... 转录翻译 ...

        # 线程结束时打印统计
        total = self.total_chunks + self.skipped_chunks
        if total > 0:
            savings = (self.skipped_chunks / total) * 100
            print(f"[统计] 总音频块: {total}, 跳过: {self.skipped_chunks} ({savings:.1f}%)")
```

---

## 🔍 调试技巧

### 1. 打印VAD检测结果

```python
def _run_vad(self, audio_data):
    # ... VAD检测 ...
    result = self.vad_iterator(audio_float32)

    if result and 'end' in result:
        print(f"[DEBUG] [VAD] 检测到静音段: start={result.get('start')}, end={result['end']}")
    else:
        print("[DEBUG] [VAD] 检测到语音活动")
```

---

### 2. 保存重采样后的音频

```python
def _run_vad(self, audio_data):
    # ... 重采样 ...
    audio_16k = signal.resample_poly(mono, up=1, down=3)

    # 保存到文件（调试用）
    import wave
    with wave.open(f"debug_16k_{time.time()}.wav", 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(audio_16k.astype(np.int16).tobytes())

    # ... 继续VAD检测 ...
```

---

### 3. 测试不同阈值

```bash
# 测试阈值0.3
VAD_THRESHOLD=0.3 python app/main.py

# 测试阈值0.7
VAD_THRESHOLD=0.7 python app/main.py
```

---

## 📚 配置示例

### .env 配置

```env
# 启用VAD
ENABLE_VAD=true

# VAD阈值（0.0-1.0）
VAD_THRESHOLD=0.5

# 最小静音持续时间（毫秒）
VAD_MIN_SILENCE_MS=500
```

### 不同场景的推荐配置

#### 场景1: 清晰对话（课程、采访）
```env
VAD_THRESHOLD=0.6         # 较高阈值
VAD_MIN_SILENCE_MS=500
```

#### 场景2: 普通电影
```env
VAD_THRESHOLD=0.5         # 默认平衡
VAD_MIN_SILENCE_MS=500
```

#### 场景3: 嘈杂环境（街头采访）
```env
VAD_THRESHOLD=0.3         # 较低阈值，捕获更多
VAD_MIN_SILENCE_MS=300
```

---

## ✅ 验收标准

- [ ] VAD模型成功加载（或失败时禁用VAD继续运行）
- [ ] 日志显示 "[VAD] 跳过静音段"
- [ ] 统计显示节省比例（30-50%）
- [ ] 立体声转单声道无溢出警告
- [ ] 重采样使用scipy（无混叠失真）
- [ ] VADIterator使用实例变量

---

## 📖 参考资源

- Silero VAD GitHub: https://github.com/snakers4/silero-vad
- scipy.signal文档: https://docs.scipy.org/doc/scipy/reference/signal.html
- WhisperLiveKit示例: example/WhisperLiveKit-main/

---

**最后更新**: 2025-11-05
**文档版本**: v1.0
