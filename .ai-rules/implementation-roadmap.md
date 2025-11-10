# 分阶段实施路线图

## 🎯 实施策略

**核心原则**:
- ✅ 分阶段渐进式开发
- ✅ 每个阶段独立可测试
- ✅ 先验证功能可行性，再添加优化

**预计总时间**: 2-4天

---

## 📋 阶段1：MVP基础版本

### 目标
实现核心功能链路：**音频捕获 → Whisper转录 → DeepL翻译 → 字幕显示**

**预计时间**: 1-2天
**代码总量**: ~340行

---

### 1.1 实现 `app/audio_capture.py` (~80行)

**职责**: 捕获VB-Cable系统音频，固定5秒分块

**关键功能**:
```python
class AudioCaptureThread(threading.Thread):
    def __init__(self, audio_queue, stop_event):
        # 音频参数
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 2          # 立体声
        self.RATE = 48000          # VB-Cable默认采样率
        self.CHUNK_DURATION = 5    # 秒

    def find_cable_device(self, audio):
        # 查找VB-Cable输出设备
        # 关键词: "cable output"

    def run(self):
        # 主循环: 捕获5秒音频 → 放入队列
        while not self.stop_event.is_set():
            audio_chunk = self.capture_chunk(stream)
            audio_queue.put(audio_chunk, timeout=1)

    def capture_chunk(self, stream):
        # 捕获固定5秒的音频块
        frames = []
        for _ in range(int(self.RATE / self.CHUNK * self.CHUNK_DURATION)):
            data = stream.read(self.CHUNK)
            frames.append(data)
        return b''.join(frames)
```

**注意事项**:
- ⚠️ 阶段1不实现VAD，所有音频都处理
- ✅ 设置 `daemon=True`
- ✅ 使用 `timeout=1` 避免队列满时阻塞

---

### 1.2 实现 `app/transcription.py` (~60行)

**职责**: 调用Whisper API转录，调用DeepL API翻译

**关键功能**:
```python
class TranscriptionThread(threading.Thread):
    def __init__(self, audio_queue, stop_event, callback, openai_key, deepl_key):
        self.openai_client = OpenAI(api_key=openai_key)
        self.deepl_translator = deepl.Translator(deepl_key)

    def run(self):
        # 主循环: 获取音频 → 转录 → 翻译 → 回调
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

    def transcribe(self, audio_data):
        # 转换为WAV格式
        audio_file = io.BytesIO()
        with wave.open(audio_file, 'wb') as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(48000)
            wf.writeframes(audio_data)

        audio_file.seek(0)
        audio_file.name = "audio.wav"

        # 调用Whisper API
        response = self.openai_client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en"
        )
        return response.text

    def translate(self, text):
        # 调用DeepL API
        result = self.deepl_translator.translate_text(
            text,
            target_lang="ZH"
        )
        return result.text
```

**注意事项**:
- ⚠️ 阶段1不实现重试机制，简单记录错误
- ✅ 空字幕跳过不回调
- ✅ 使用 `queue.Empty` 异常处理

---

### 1.3 实现 `app/subtitle_storage.py` (~50行)

**职责**: 内存存储字幕，导出SRT格式

**关键功能**:
```python
class SubtitleStorage:
    def __init__(self):
        self.subtitles = []
        self.start_time = time.time()

    def add_subtitle(self, original, translation):
        timestamp = time.time() - self.start_time
        self.subtitles.append({
            'timestamp': timestamp,
            'original': original,
            'translation': translation
        })

    def export_srt(self, filepath):
        with open(filepath, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(self.subtitles, 1):
                start = self.format_srt_time(sub['timestamp'])

                # 时长计算: 根据下一条字幕时间戳
                if i < len(self.subtitles):
                    duration = self.subtitles[i]['timestamp'] - sub['timestamp']
                else:
                    duration = 5.0  # 最后一条默认5秒

                end = self.format_srt_time(sub['timestamp'] + duration)

                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{sub['original']}\n")
                f.write(f"{sub['translation']}\n")
                f.write("\n")

    def format_srt_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def clear(self):
        self.subtitles = []
        self.start_time = time.time()
```

**注意事项**:
- ✅ 时长根据下一条字幕计算（重要！）
- ✅ SRT格式使用逗号分隔毫秒（不是点）
- ⚠️ 阶段1不实现VTT/TXT导出

---

### 1.4 实现 `app/main.py` (~150行)

**职责**: Tkinter GUI主程序，管理线程生命周期

**关键功能**:
```python
class SubtitleApp:
    def __init__(self, root):
        self.root = root
        self.audio_queue = queue.Queue()  # 阶段1: 无maxsize限制
        self.stop_event = threading.Event()
        self.subtitle_storage = SubtitleStorage()

        self.audio_thread = None
        self.transcription_thread = None

        self.create_widgets()

    def create_widgets(self):
        # 控制按钮
        btn_start = tk.Button(text="开始捕获", command=self.start_capture)
        btn_stop = tk.Button(text="停止", command=self.stop_capture)
        btn_export = tk.Button(text="导出SRT", command=self.export_srt)

        # 原文显示区
        self.original_text = tk.Text(height=10)

        # 翻译显示区
        self.translated_text = tk.Text(height=10)

    def start_capture(self):
        # 清除停止信号
        self.stop_event.clear()

        # 启动音频线程
        self.audio_thread = AudioCaptureThread(
            self.audio_queue,
            self.stop_event
        )
        self.audio_thread.daemon = True
        self.audio_thread.start()

        # 启动转录线程
        openai_key = os.getenv('OPENAI_API_KEY')
        deepl_key = os.getenv('DEEPL_API_KEY')

        self.transcription_thread = TranscriptionThread(
            self.audio_queue,
            self.stop_event,
            self.on_subtitle_ready,
            openai_key,
            deepl_key
        )
        self.transcription_thread.daemon = True
        self.transcription_thread.start()

    def stop_capture(self):
        # 设置停止信号
        self.stop_event.set()

        # 等待线程结束
        if self.audio_thread:
            self.audio_thread.join(timeout=5)
        if self.transcription_thread:
            self.transcription_thread.join(timeout=10)

    def on_subtitle_ready(self, original, translation):
        # 线程安全的GUI更新
        self.root.after(0, self.update_subtitle, original, translation)

    def update_subtitle(self, original, translation):
        # 更新原文区域
        self.original_text.insert(tk.END, original + "\n")
        self.original_text.see(tk.END)

        # 更新译文区域
        self.translated_text.insert(tk.END, translation + "\n")
        self.translated_text.see(tk.END)

        # 保存到存储
        self.subtitle_storage.add_subtitle(original, translation)

    def export_srt(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".srt",
            filetypes=[("SRT files", "*.srt")]
        )
        if filepath:
            self.subtitle_storage.export_srt(filepath)
```

**注意事项**:
- ✅ 使用 `root.after(0, ...)` 确保GUI更新在主线程
- ✅ 设置 `daemon=True`
- ⚠️ 阶段1不实现 `storage_lock`，先验证功能

---

### 1.5 创建入口文件

```python
# app/__init__.py
# 空文件

# app/main.py (末尾)
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    root = tk.Tk()
    root.title("实时字幕系统")
    root.geometry("800x600")

    app = SubtitleApp(root)
    root.mainloop()
```

---

### 1.6 阶段1验收标准

**功能测试**:
- [ ] 运行 `python app/main.py` 成功启动GUI
- [ ] 点击"开始捕获"，无报错
- [ ] 播放YouTube视频，字幕正确显示在窗口中
- [ ] 原文和翻译都正确显示
- [ ] 点击"导出SRT"，生成的文件格式正确
- [ ] 点击"停止"，程序正常停止捕获

**错误处理**:
- [ ] VB-Cable未安装时，给出明确错误提示
- [ ] API Key错误时，记录错误日志

**已知问题（阶段2修复）**:
- ⚠️ 长时间运行可能内存泄漏（队列无限制）
- ⚠️ API失败没有重试
- ⚠️ 静音段也会调用API（浪费成本）
- ⚠️ SubtitleStorage 并发访问不安全

---

## ⚡ 阶段2：优化版本

### 目标
- 集成VAD节省30-50%成本
- 添加错误重试提升成功率到99.9%
- 修复所有P0级别的Bug

**预计时间**: 1-2天
**新增代码**: ~200行
**修改代码**: ~100行

---

### 2.1 实现 `app/silero_vad_iterator.py` (~150行)

**职责**: 封装Silero VAD模型，支持任意长度音频

**关键类设计**:
```python
class VADIterator:
    def __init__(self, model, threshold=0.5, sampling_rate=16000,
                 min_silence_duration_ms=500, speech_pad_ms=30):
        self.model = model
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.min_silence_duration_ms = min_silence_duration_ms
        self.speech_pad_ms = speech_pad_ms

        # ⚠️ 关键修复: 必须是实例变量！
        self.triggered = False
        self.temp_end = 0
        self.current_sample = 0
        self.speech_start = None  # ← 必须是 self.speech_start

    def __call__(self, x, return_seconds=False):
        # 调用VAD模型
        speech_prob = self.model(torch.from_numpy(x), self.sampling_rate).item()

        # 状态机: 检测语音开始/结束
        if speech_prob >= self.threshold and self.temp_end:
            self.temp_end = 0

        if speech_prob >= self.threshold and not self.triggered:
            self.triggered = True
            self.speech_start = self.current_sample

        if speech_prob < self.threshold and self.triggered:
            if not self.temp_end:
                self.temp_end = self.current_sample

            if self.current_sample - self.temp_end >= \
               self.min_silence_duration_ms * self.sampling_rate / 1000:
                # 检测到静音段结束
                speech_end = self.temp_end
                self.triggered = False
                self.temp_end = 0

                return {'start': self.speech_start, 'end': speech_end}

        self.current_sample += len(x)
        return None

class FixedVADIterator(VADIterator):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.buffer = np.array([], dtype=np.float32)
        self.window_size_samples = 512

    def __call__(self, x, return_seconds=False):
        # 添加到缓冲区
        self.buffer = np.concatenate([self.buffer, x])

        speech_segments = []

        # 每512样本调用一次父类
        while len(self.buffer) >= self.window_size_samples:
            chunk = self.buffer[:self.window_size_samples]
            self.buffer = self.buffer[self.window_size_samples:]

            result = super().__call__(chunk, return_seconds)
            if result:
                speech_segments.append(result)

        if speech_segments:
            return {'start': speech_segments[0]['start'],
                    'end': speech_segments[-1]['end']}
        return None
```

**参考**: `example/WhisperLiveKit-main/whisperlivekit/silero_vad_iterator.py`

---

### 2.2 更新 `app/audio_capture.py`

**新增功能**:
1. 集成VAD检测
2. scipy高质量重采样
3. 立体声→单声道转换（int32避免溢出）
4. 队列满时丢弃音频

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
        # 3次重试加载模型
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
                break
            except Exception as e:
                if attempt == 2:
                    print(f"[WARNING] VAD加载失败，禁用VAD: {e}")
                    self.enable_vad = False

    def capture_chunk(self, stream):
        # 读取5秒音频
        frames = []
        for _ in range(int(self.RATE / self.CHUNK * self.CHUNK_DURATION)):
            try:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)
            except Exception as e:
                # ⚠️ 捕获异常，填充静音
                frames.append(b'\x00' * (self.CHUNK * 2))

        audio_data = b''.join(frames)

        # VAD检测（如果启用）
        if self.enable_vad and self.vad_iterator:
            self._run_vad(audio_data)

        return audio_data

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

    def run(self):
        # ... 原有逻辑 ...
        while not self.stop_event.is_set():
            audio_chunk = self.capture_chunk(stream)

            try:
                # ⚠️ 队列满时丢弃，防止内存泄漏
                self.audio_queue.put(audio_chunk, timeout=1)
            except queue.Full:
                print("[WARNING] 队列已满，丢弃音频块")
```

---

### 2.3 更新 `app/transcription.py`

**新增功能**:
1. 错误重试机制（3次，指数退避）
2. VAD静音段跳过
3. 详细日志

**关键修改**:
```python
class TranscriptionThread(threading.Thread):
    def __init__(self, audio_queue, stop_event, callback,
                 openai_key, deepl_key, audio_thread=None):
        # ... 原有参数 ...
        self.audio_thread = audio_thread  # 阶段2: 传入音频线程引用

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

    def translate(self, text):
        max_retries = 3
        retry_delay = 1.0

        for attempt in range(max_retries):
            try:
                # ... 原有API调用代码 ...
                return result.text

            except Exception as e:
                print(f"[ERROR] DeepL API调用失败 (尝试{attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    delay = retry_delay * (2 ** attempt)
                    time.sleep(delay)
                else:
                    return None
```

---

### 2.4 更新 `app/main.py`

**新增功能**:
1. Queue设置maxsize=10
2. SubtitleStorage并发访问保护（threading.Lock）
3. 配置验证
4. 线程清理优化

**关键修改**:
```python
class SubtitleApp:
    def __init__(self, root):
        # ⚠️ 队列大小限制
        self.audio_queue = queue.Queue(maxsize=10)

        # ⚠️ 并发访问锁
        self.storage_lock = threading.Lock()

        # ... 其他初始化 ...

    def start_capture(self):
        # 配置验证
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

    def stop_capture(self):
        # 1. 设置停止信号
        self.stop_event.set()

        # 2. 等待音频线程停止
        if self.audio_thread:
            self.audio_thread.join(timeout=5)

        # 3. 清空队列（让转录线程快速退出）
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        # 4. 等待转录线程停止
        if self.transcription_thread:
            self.transcription_thread.join(timeout=10)

    def update_subtitle(self, original, translation):
        # 更新GUI
        self.original_text.insert(tk.END, original + "\n")
        self.original_text.see(tk.END)
        self.translated_text.insert(tk.END, translation + "\n")
        self.translated_text.see(tk.END)

        # ⚠️ 使用锁保护并发访问
        with self.storage_lock:
            self.subtitle_storage.add_subtitle(original, translation)

    def export_srt(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".srt",
            filetypes=[("SRT files", "*.srt")]
        )
        if filepath:
            # ⚠️ 使用锁保护导出
            with self.storage_lock:
                self.subtitle_storage.export_srt(filepath)
```

---

### 2.5 阶段2验收标准

**功能测试**:
- [ ] 启用VAD后，日志显示跳过静音段
- [ ] VAD节省成本30-50%（查看日志统计）
- [ ] API失败自动重试，成功率99.9%
- [ ] 长时间运行（1小时）无内存泄漏

**性能测试**:
```python
# 在transcription.py中添加统计
self.total_chunks = 0
self.skipped_chunks = 0

# 打印统计
savings = (self.skipped_chunks / (self.total_chunks + self.skipped_chunks)) * 100
print(f"[统计] 已跳过 {self.skipped_chunks} 块, 节省 {savings:.1f}% 成本")
```

**已修复的问题**:
- ✅ 队列无限增长 → 设置maxsize=10
- ✅ API失败不重试 → 3次重试+指数退避
- ✅ 静音段浪费成本 → VAD跳过
- ✅ 并发访问不安全 → threading.Lock
- ✅ VADIterator状态混乱 → speech_start改为实例变量
- ✅ 音频重采样失真 → 使用scipy
- ✅ 立体声转换溢出 → 先转int32

---

## 🏁 阶段3：完善版本（可选）

### 目标
生产级稳定性和用户体验优化

**预计时间**: 1天（可选）

### 优化项

1. **日志系统**
   - 使用Python logging模块
   - 控制台 + 文件日志（logs/目录）
   - DEBUG/INFO/WARNING/ERROR级别

2. **线程健康监控**
   - 心跳检测机制
   - 线程异常自动恢复

3. **GUI增强**
   - 窗口关闭事件处理
   - 状态栏显示统计信息
   - 暗色主题支持

4. **导出优化**
   - 支持VTT/TXT格式
   - 导出时复制数据副本（避免长时间持锁）

---

## 📊 成本对比

| 阶段 | 月度成本（每天1小时） | 成功率 | 内存泄漏风险 |
|-----|-------------------|-------|------------|
| 阶段1 | $10.80 | 95% | 高 |
| 阶段2 | $6.48 | 99.9% | 低 |
| 节省 | **-$4.32 (40%)** | **+4.9%** | **✅ 已修复** |

---

**最后更新**: 2025-11-05
**文档版本**: v1.0
