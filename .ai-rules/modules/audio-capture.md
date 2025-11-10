# 音频捕获模块设计

## 📝 模块概述

**文件**: `app/audio_capture.py`
**职责**: 捕获VB-Cable虚拟音频设备的系统音频，固定时长分块，集成VAD语音检测

**代码量**:
- 阶段1（基础版）: ~80行
- 阶段2（集成VAD）: ~120行

---

## 🎯 核心功能

1. **音频捕获**: 使用PyAudio从VB-Cable设备读取音频流
2. **设备检测**: 自动查找VB-Cable虚拟设备
3. **固定分块**: 每5秒为一个音频块
4. **VAD集成**: 检测语音活动，跳过静音段（阶段2）
5. **队列传递**: 将音频块放入线程安全队列

---

## 🔧 类设计

### AudioCaptureThread

```python
class AudioCaptureThread(threading.Thread):
    """
    音频捕获线程

    职责:
    - 持续捕获VB-Cable音频流
    - 固定5秒分块
    - VAD语音检测（可选）
    - 将音频放入队列
    """

    def __init__(self, audio_queue, stop_event, enable_vad=False):
        """
        参数:
            audio_queue (queue.Queue): 音频数据队列
            stop_event (threading.Event): 停止信号
            enable_vad (bool): 是否启用VAD检测
        """
        super().__init__(daemon=True)
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.enable_vad = enable_vad

        # 音频参数
        self.CHUNK = 1024                    # 每次读取的帧数
        self.FORMAT = pyaudio.paInt16        # 16-bit采样
        self.CHANNELS = 2                    # 立体声
        self.RATE = 48000                    # 48kHz采样率（VB-Cable默认）
        self.CHUNK_DURATION = 5              # 每块5秒

        # VAD相关（阶段2）
        self.vad_model = None
        self.vad_iterator = None
        self.is_silence = False
        self.silence_count = 0

        if enable_vad:
            self._init_vad()

    def find_cable_device(self, audio):
        """查找VB-Cable输出设备"""

    def run(self):
        """线程主循环"""

    def capture_chunk(self, stream):
        """捕获固定5秒的音频块"""

    # === 阶段2新增方法 ===
    def _init_vad(self):
        """初始化VAD模型（3次重试）"""

    def _run_vad(self, audio_data):
        """对音频块运行VAD检测"""

    def is_silent_audio(self):
        """判断当前是否为静音"""
```

---

## 🚀 阶段1实现（基础版）

### 关键方法实现

#### 1. find_cable_device()

**职责**: 遍历音频设备，查找VB-Cable虚拟设备

```python
def find_cable_device(self, audio):
    """
    查找VB-Cable输出设备

    返回:
        int: 设备索引，未找到返回None
    """
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        # 关键词匹配: "cable output"
        if 'cable output' in info['name'].lower():
            print(f"[INFO] 找到VB-Cable设备: {info['name']} (索引: {i})")
            return i

    return None
```

**注意事项**:
- ✅ 关键词使用小写匹配 `'cable output'`
- ✅ 找不到设备时抛出明确异常
- ✅ 打印设备名称和索引，方便调试

---

#### 2. run()

**职责**: 线程主循环，持续捕获音频并放入队列

```python
def run(self):
    """线程主循环"""
    audio = pyaudio.PyAudio()

    try:
        # 1. 查找VB-Cable设备
        device_index = self.find_cable_device(audio)
        if device_index is None:
            raise Exception("未找到VB-Cable设备，请确保驱动已安装并重启电脑")

        # 2. 打开音频流
        stream = audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=self.CHUNK
        )

        print("[INFO] 音频捕获线程已启动")

        # 3. 捕获循环
        while not self.stop_event.is_set():
            # 捕获5秒音频
            audio_chunk = self.capture_chunk(stream)

            # 放入队列（阶段1: 阻塞，阶段2: 超时丢弃）
            try:
                self.audio_queue.put(audio_chunk, timeout=1)
            except queue.Full:
                # 阶段2添加: 队列满时丢弃音频
                print("[WARNING] 队列已满，丢弃音频块")

        # 4. 清理
        stream.stop_stream()
        stream.close()
        print("[INFO] 音频捕获线程已停止")

    finally:
        audio.terminate()
```

**注意事项**:
- ✅ 使用 `try-finally` 确保资源清理
- ✅ 打印日志方便调试
- ⚠️ 阶段1不处理 `queue.Full`（阶段2添加）

---

#### 3. capture_chunk()

**职责**: 捕获固定5秒的音频块

```python
def capture_chunk(self, stream):
    """
    捕获固定时长的音频块

    返回:
        bytes: 音频数据（48kHz, 立体声, 16-bit）
    """
    frames = []

    # 计算需要读取的次数
    num_chunks = int(self.RATE / self.CHUNK * self.CHUNK_DURATION)

    for _ in range(num_chunks):
        try:
            # 读取音频数据
            data = stream.read(self.CHUNK, exception_on_overflow=False)
            frames.append(data)
        except Exception as e:
            # ⚠️ 阶段2添加: 捕获异常，填充静音
            print(f"[WARNING] 音频流读取异常: {e}")
            # 填充静音数据（避免时序错乱）
            frames.append(b'\x00' * (self.CHUNK * self.CHANNELS * 2))

    # 合并所有帧
    audio_data = b''.join(frames)

    # ⚠️ 阶段2添加: VAD检测
    if self.enable_vad and self.vad_iterator:
        self._run_vad(audio_data)

    return audio_data
```

**关键计算**:
- `num_chunks = RATE / CHUNK * CHUNK_DURATION`
- 例如: `48000 / 1024 * 5 ≈ 234` 次读取

**注意事项**:
- ✅ 设置 `exception_on_overflow=False` 避免缓冲区溢出异常
- ⚠️ 阶段2添加异常捕获和静音填充

---

## ⚡ 阶段2实现（VAD集成）

### 新增方法

#### 1. _init_vad()

**职责**: 加载Silero VAD模型，3次重试机制

```python
def _init_vad(self):
    """
    初始化VAD模型

    特性:
    - 3次重试机制
    - 失败时禁用VAD但程序继续运行
    - 验证配置参数
    """
    import os

    # 读取配置
    vad_threshold = float(os.getenv('VAD_THRESHOLD', '0.5'))
    vad_min_silence = int(os.getenv('VAD_MIN_SILENCE_MS', '500'))

    # 参数验证
    if not 0.0 <= vad_threshold <= 1.0:
        raise ValueError("VAD_THRESHOLD 必须在 0.0-1.0 范围内")
    if vad_min_silence < 0:
        raise ValueError("VAD_MIN_SILENCE_MS 必须为非负整数")

    # 3次重试加载模型
    for attempt in range(3):
        try:
            import torch
            from silero_vad_iterator import FixedVADIterator

            print(f"[INFO] 正在加载Silero VAD模型（尝试 {attempt+1}/3）...")

            self.vad_model, _ = torch.hub.load(
                "snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                skip_validation=True
            )

            self.vad_iterator = FixedVADIterator(
                self.vad_model,
                threshold=vad_threshold,
                sampling_rate=16000,
                min_silence_duration_ms=vad_min_silence,
                speech_pad_ms=30
            )

            print(f"[INFO] VAD模型加载成功: threshold={vad_threshold}, min_silence={vad_min_silence}ms")
            return

        except Exception as e:
            print(f"[WARNING] VAD模型加载失败（尝试 {attempt+1}/3）: {e}")
            if attempt == 2:
                print("[WARNING] VAD加载最终失败，禁用VAD功能（程序继续运行）")
                self.enable_vad = False
            else:
                time.sleep(2)  # 重试间隔
```

**关键设计**:
- ✅ 3次重试机制，增加成功率
- ✅ 最终失败时禁用VAD但程序继续运行
- ✅ 参数验证防止配置错误
- ✅ `skip_validation=True` 加速加载

---

#### 2. _run_vad()

**职责**: 对音频块运行VAD检测

```python
def _run_vad(self, audio_data):
    """
    对音频块运行VAD检测

    流程:
    1. 立体声 → 单声道
    2. 48kHz → 16kHz (VAD模型要求)
    3. 调用VAD模型
    4. 更新静音状态

    参数:
        audio_data (bytes): 48kHz立体声音频
    """
    import numpy as np
    from scipy import signal

    # 1. 转换为numpy数组（int16）
    audio_np = np.frombuffer(audio_data, dtype=np.int16)

    # 2. 立体声 → 单声道
    # ⚠️ 关键修复: 必须先转int32避免溢出！
    stereo = audio_np.reshape(-1, 2)
    mono = stereo.astype(np.int32).mean(axis=1).astype(np.int16)

    # 3. 48kHz → 16kHz 重采样
    # ⚠️ 关键修复: 必须使用scipy抗混叠重采样，不能简单抽取！
    audio_16k = signal.resample_poly(mono, up=1, down=3)

    # 4. 归一化到 float32 [-1, 1]
    audio_float32 = audio_16k.astype(np.float32) / 32768.0

    # 5. 调用VAD检测
    result = self.vad_iterator(audio_float32, return_seconds=False)

    # 6. 更新静音状态
    # 策略: 连续2次静音（10秒）才标记为静音，避免误判
    if result and 'end' in result:
        self.silence_count += 1
        if self.silence_count >= 2:
            self.is_silence = True
    else:
        # 检测到语音活动
        self.is_silence = False
        self.silence_count = 0
```

**关键修复说明**:

1. **立体声转单声道必须用int32**:
   ```python
   # ❌ 错误: 直接取平均可能溢出
   mono = audio_np.reshape(-1, 2).mean(axis=1).astype(np.int16)

   # ✅ 正确: 先转int32避免溢出
   stereo = audio_np.reshape(-1, 2)
   mono = stereo.astype(np.int32).mean(axis=1).astype(np.int16)
   ```

2. **重采样必须用scipy**:
   ```python
   # ❌ 错误: 简单抽取会导致混叠失真
   audio_16k = mono[::3]

   # ✅ 正确: 抗混叠滤波重采样
   audio_16k = signal.resample_poly(mono, up=1, down=3)
   ```

---

#### 3. is_silent_audio()

**职责**: 查询当前是否为静音状态

```python
def is_silent_audio(self):
    """
    查询当前是否为静音状态

    返回:
        bool: True表示连续2次静音（10秒）
    """
    return self.is_silence and self.silence_count >= 2
```

**调用方**:
- `TranscriptionThread` 在处理音频前调用此方法
- 如果返回True，跳过API调用，节省成本

---

## 📊 音频参数说明

| 参数 | 值 | 说明 |
|-----|---|------|
| **采样率** | 48000 Hz | VB-Cable默认采样率 |
| **通道数** | 2 (立体声) | 保留原始音质 |
| **采样位深** | 16-bit | 标准CD音质 |
| **分块时长** | 5秒 | 延迟与成本的平衡 |
| **VAD采样率** | 16000 Hz | Silero VAD模型要求 |

**数据量计算**:
- 每秒数据: `48000 * 2 * 2 = 192KB`
- 5秒音频块: `192KB * 5 = 960KB`
- 队列maxsize=10: `960KB * 10 = 9.6MB` 最大内存占用

---

## ⚠️ 常见错误和解决方案

### 1. "VB-Cable设备未找到"

**原因**:
- VB-Cable驱动未安装
- 安装后未重启电脑
- 设备名称不匹配

**解决方案**:
```python
# 调试脚本: 列出所有音频设备
import pyaudio
audio = pyaudio.PyAudio()
for i in range(audio.get_device_count()):
    info = audio.get_device_info_by_index(i)
    print(f"{i}: {info['name']}")
```

---

### 2. "Input overflowed"

**原因**: 音频缓冲区溢出（系统负载高）

**解决方案**:
```python
# 设置 exception_on_overflow=False
stream.read(self.CHUNK, exception_on_overflow=False)
```

---

### 3. VAD误判静音

**原因**: 阈值设置过高

**解决方案**:
```env
# .env 文件
VAD_THRESHOLD=0.3  # 降低阈值（默认0.5）
```

---

### 4. 重采样后音质下降

**原因**: 使用了简单抽取而不是scipy重采样

**解决方案**:
```python
# ✅ 必须使用scipy
from scipy import signal
audio_16k = signal.resample_poly(mono, up=1, down=3)
```

---

## 🔍 调试技巧

### 打印VAD检测结果

```python
def _run_vad(self, audio_data):
    # ... VAD检测代码 ...

    # 调试输出
    if result and 'end' in result:
        print(f"[DEBUG] [VAD] 检测到静音段: {result}")
    else:
        print("[DEBUG] [VAD] 检测到语音活动")
```

### 保存音频块到文件

```python
def capture_chunk(self, stream):
    audio_data = # ...

    # 调试: 保存到文件
    import wave
    with wave.open(f"debug_{time.time()}.wav", 'wb') as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(48000)
        wf.writeframes(audio_data)

    return audio_data
```

---

## 📚 依赖项

```python
import pyaudio
import numpy as np
import threading
import queue
import time
import os

# 阶段2新增
import torch
from scipy import signal
from silero_vad_iterator import FixedVADIterator
```

---

**最后更新**: 2025-11-05
**文档版本**: v1.0
