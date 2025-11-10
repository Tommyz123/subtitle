# 关键Bug修复清单

## 📋 概述

本文档列出所有**必须修复**的关键问题（P0级别）。这些问题会导致：
- 程序崩溃
- 内存泄漏
- 数据损坏
- 音质下降
- 并发错误

**重要**: 在实施阶段2之前，必须确保这些问题全部修复！

---

## 🚨 P0级别问题清单

### 1. VADIterator speech_start 必须改为实例变量

**位置**: `app/silero_vad_iterator.py`

**问题代码**:
```python
class VADIterator:
    # ❌ 错误: 类变量，多实例共享状态
    speech_start = None

    def __init__(self, ...):
        pass
```

**修复方案**:
```python
class VADIterator:
    def __init__(self, ...):
        # ✅ 正确: 实例变量
        self.speech_start = None
        self.triggered = False
        self.temp_end = 0
        self.current_sample = 0
```

**严重性**: ⚠️⚠️⚠️ 极高
**后果**: 多实例VAD状态混乱，检测结果错误
**优先级**: P0 - 必须修复

---

### 2. 立体声转单声道必须用 int32 避免溢出

**位置**: `app/audio_capture.py` 的 `_run_vad()` 方法

**问题代码**:
```python
# ❌ 错误: 直接取平均，可能溢出
audio_np = np.frombuffer(audio_data, dtype=np.int16)
mono = audio_np.reshape(-1, 2).mean(axis=1).astype(np.int16)
```

**修复方案**:
```python
# ✅ 正确: 先转int32，避免溢出
audio_np = np.frombuffer(audio_data, dtype=np.int16)
stereo = audio_np.reshape(-1, 2)
mono = stereo.astype(np.int32).mean(axis=1).astype(np.int16)
```

**原理**:
- int16范围: -32768 ~ 32767
- 两个int16相加可能超出int16范围
- int32范围: -2147483648 ~ 2147483647（足够大）

**严重性**: ⚠️⚠️⚠️ 高
**后果**: 音频数据溢出，VAD误判
**优先级**: P0 - 必须修复

---

### 3. 必须使用 scipy 重采样，不能简单抽取

**位置**: `app/audio_capture.py` 的 `_run_vad()` 方法

**问题代码**:
```python
# ❌ 错误: 简单抽取，混叠失真
audio_16k = mono[::3]
```

**修复方案**:
```python
# ✅ 正确: 抗混叠滤波重采样
from scipy import signal
audio_16k = signal.resample_poly(mono, up=1, down=3)
```

**原理**:
- 简单抽取违反Nyquist采样定理
- 高频信号会混叠到低频，导致失真
- `resample_poly()` 使用多相滤波器，正确处理

**严重性**: ⚠️⚠️⚠️ 高
**后果**: VAD准确率下降20-30%
**优先级**: P0 - 必须修复

---

### 4. Queue 必须设置 maxsize 限制

**位置**: `app/main.py` 的 `__init__()` 方法

**问题代码**:
```python
# ❌ 错误: 无大小限制
self.audio_queue = queue.Queue()
```

**修复方案**:
```python
# ✅ 正确: 设置maxsize=10
self.audio_queue = queue.Queue(maxsize=10)
```

**问题分析**:
- 转录速度 < 捕获速度时，队列无限增长
- 长时间运行导致内存泄漏
- 最坏情况: 几小时后OOM崩溃

**严重性**: ⚠️⚠️ 中高
**后果**: 内存泄漏，最终OOM
**优先级**: P0 - 必须修复

---

### 5. 队列满时必须处理 queue.Full 异常

**位置**: `app/audio_capture.py` 的 `run()` 方法

**问题代码**:
```python
# ❌ 错误: 队列满时阻塞
audio_queue.put(audio_chunk)
```

**修复方案**:
```python
# ✅ 正确: 设置超时，处理Full异常
try:
    self.audio_queue.put(audio_chunk, timeout=1)
except queue.Full:
    print("[WARNING] 队列已满，丢弃音频块")
```

**严重性**: ⚠️⚠️ 中高
**后果**: 线程阻塞，停止响应慢
**优先级**: P0 - 必须修复

---

### 6. SubtitleStorage 并发访问必须使用 threading.Lock

**位置**: `app/main.py`

**问题代码**:
```python
# ❌ 错误: 无锁保护
def update_subtitle(self, original, translation):
    self.subtitle_storage.add_subtitle(original, translation)

def export_srt(self):
    self.subtitle_storage.export_srt(filepath)
```

**修复方案**:
```python
# 在 __init__ 中创建锁
self.storage_lock = threading.Lock()

# ✅ 正确: 使用锁保护
def update_subtitle(self, original, translation):
    with self.storage_lock:
        self.subtitle_storage.add_subtitle(original, translation)

def export_srt(self):
    with self.storage_lock:
        self.subtitle_storage.export_srt(filepath)
```

**问题分析**:
- 转录线程写入字幕列表
- GUI线程导出读取字幕列表
- 并发访问可能导致列表损坏

**严重性**: ⚠️⚠️ 中高
**后果**: 数据竞争，列表损坏，程序崩溃
**优先级**: P0 - 必须修复

---

### 7. 线程清理必须清空队列加速退出

**位置**: `app/main.py` 的 `stop_capture()` 方法

**问题代码**:
```python
# ❌ 错误: 转录线程可能阻塞在queue.get()
def stop_capture(self):
    self.stop_event.set()
    self.audio_thread.join(timeout=5)
    self.transcription_thread.join(timeout=10)
```

**修复方案**:
```python
# ✅ 正确: 清空队列加速退出
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
```

**严重性**: ⚠️⚠️ 中
**后果**: 停止响应慢，用户体验差
**优先级**: P0 - 必须修复

---

### 8. VAD 模型加载必须有 3 次重试

**位置**: `app/audio_capture.py` 的 `_init_vad()` 方法

**问题代码**:
```python
# ❌ 错误: 加载失败直接崩溃
self.vad_model, _ = torch.hub.load("snakers4/silero-vad", model="silero_vad")
```

**修复方案**:
```python
# ✅ 正确: 3次重试，失败时禁用VAD
for attempt in range(3):
    try:
        self.vad_model, _ = torch.hub.load(
            "snakers4/silero-vad",
            model="silero_vad",
            force_reload=False
        )
        # ... 创建VAD迭代器 ...
        print("[INFO] VAD模型加载成功")
        return

    except Exception as e:
        print(f"[WARNING] VAD加载失败 (尝试 {attempt+1}/3): {e}")
        if attempt == 2:
            print("[WARNING] VAD最终失败，禁用VAD（程序继续运行）")
            self.enable_vad = False
        else:
            time.sleep(2)
```

**严重性**: ⚠️⚠️ 中
**后果**: 网络不稳定时加载失败，程序崩溃
**优先级**: P0 - 必须修复

---

### 9. 字幕时长必须根据下一条计算

**位置**: `app/subtitle_storage.py` 的 `export_srt()` 方法

**问题代码**:
```python
# ❌ 错误: 所有字幕都是5秒
duration = 5.0
end = self.format_srt_time(sub['timestamp'] + duration)
```

**修复方案**:
```python
# ✅ 正确: 根据下一条字幕计算实际时长
if i < len(self.subtitles):
    # 使用下一条字幕的时间戳
    duration = self.subtitles[i]['timestamp'] - sub['timestamp']
else:
    # 最后一条默认5秒
    duration = 5.0

end = self.format_srt_time(sub['timestamp'] + duration)
```

**严重性**: ⚠️ 中低
**后果**: 字幕时长不准确，播放效果差
**优先级**: P0 - 必须修复

---

### 10. 配置验证必须检查布尔值格式

**位置**: `app/main.py` 的 `start_capture()` 方法

**问题代码**:
```python
# ❌ 错误: 只检查 "true"
enable_vad = os.getenv('ENABLE_VAD', 'true')
vad_enabled = (enable_vad == 'true')
```

**修复方案**:
```python
# ✅ 正确: 支持多种格式
enable_vad = os.getenv('ENABLE_VAD', 'true').lower()
vad_enabled = enable_vad in ['true', '1', 'yes', 'on']
```

**支持的格式**:
- `true`, `True`, `TRUE`
- `1`
- `yes`, `Yes`, `YES`
- `on`, `On`, `ON`

**严重性**: ⚠️ 低
**后果**: 配置不灵活，用户困惑
**优先级**: P0 - 建议修复

---

### 11. PyAudio 流读取必须捕获异常

**位置**: `app/audio_capture.py` 的 `capture_chunk()` 方法

**问题代码**:
```python
# ❌ 错误: 异常未捕获，导致线程崩溃
for _ in range(num_chunks):
    data = stream.read(self.CHUNK)
    frames.append(data)
```

**修复方案**:
```python
# ✅ 正确: 捕获异常，填充静音保持时序
for _ in range(num_chunks):
    try:
        data = stream.read(self.CHUNK, exception_on_overflow=False)
        frames.append(data)
    except Exception as e:
        print(f"[WARNING] 音频流读取异常: {e}")
        # 填充静音数据（避免时序错乱）
        frames.append(b'\x00' * (self.CHUNK * self.CHANNELS * 2))
```

**严重性**: ⚠️⚠️ 中高
**后果**: 系统负载高时流异常，线程崩溃
**优先级**: P0 - 必须修复

---

### 12. VAD 参数验证必须检查范围

**位置**: `app/audio_capture.py` 的 `_init_vad()` 方法

**问题代码**:
```python
# ❌ 错误: 不验证参数范围
vad_threshold = float(os.getenv('VAD_THRESHOLD', '0.5'))
```

**修复方案**:
```python
# ✅ 正确: 验证参数范围
vad_threshold = float(os.getenv('VAD_THRESHOLD', '0.5'))
if not 0.0 <= vad_threshold <= 1.0:
    raise ValueError("VAD_THRESHOLD 必须在 0.0-1.0 范围内")

vad_min_silence = int(os.getenv('VAD_MIN_SILENCE_MS', '500'))
if vad_min_silence < 0:
    raise ValueError("VAD_MIN_SILENCE_MS 必须为非负整数")
```

**严重性**: ⚠️ 低
**后果**: 错误配置导致VAD异常
**优先级**: P0 - 建议修复

---

## 📋 修复验收清单

### 阶段1（基础版本）

虽然阶段1不实现VAD，但以下修复仍然必须：

- [ ] Queue设置maxsize=10
- [ ] Queue.put()使用timeout参数
- [ ] SubtitleStorage并发访问使用Lock
- [ ] 字幕时长根据下一条计算
- [ ] 线程清理清空队列
- [ ] PyAudio流读取捕获异常

### 阶段2（优化版本）

必须修复所有12个问题：

- [ ] VADIterator.speech_start改为实例变量
- [ ] 立体声转单声道使用int32
- [ ] 重采样使用scipy.signal.resample_poly
- [ ] VAD模型加载3次重试
- [ ] VAD参数验证
- [ ] 配置验证支持多种格式

---

## 🔍 测试验证

### 1. 内存泄漏测试

```bash
# 运行1小时，监控内存
python app/main.py

# 预期: 内存稳定在 < 100MB
```

### 2. 并发安全测试

```python
# 同时导出和添加字幕
import threading

def export_loop():
    while True:
        app.export_srt()
        time.sleep(1)

threading.Thread(target=export_loop, daemon=True).start()
# 预期: 无崩溃，无数据损坏
```

### 3. VAD准确率测试

```bash
# 使用测试音频（已知语音占比60%）
# 预期: 统计显示节省40%左右
```

---

## 📚 参考

- 原始设计: `plan.md` 第5.6节
- 线程管理: `technical/threading-concurrency.md`
- VAD优化: `technical/vad-optimization.md`

---

**最后更新**: 2025-11-05
**文档版本**: v1.0
**状态**: ✅ 完整（包含所有P0级别问题）
