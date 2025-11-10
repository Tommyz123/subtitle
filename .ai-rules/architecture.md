# 系统架构设计

## 📐 整体架构

### 三层架构模型

```
┌────────────────────────────────────────────────────┐
│           用户层 (User Layer)                       │
│  [视频播放器] [浏览器] [会议软件]                    │
│       VLC     Chrome    Zoom/Teams                 │
└───────────────────┬────────────────────────────────┘
                    │ 系统音频
                    ▼
┌───────────────────────────────────────────────────┐
│        音频捕获层 (Audio Capture Layer)            │
│                                                   │
│  VB-Cable 虚拟音频设备 → PyAudio 捕获线程         │
│  • 48kHz, 立体声, 16-bit                          │
│  • 固定5秒分块                                    │
│  • VAD语音检测（阶段2）                            │
└───────────────────┬───────────────────────────────┘
                    │ audio_queue (Queue)
                    ▼
┌───────────────────────────────────────────────────┐
│       处理层 (Processing Layer)                    │
│                                                   │
│  转录翻译线程                                      │
│  1. 从队列获取音频块                               │
│  2. 调用 Whisper API (语音→文字)                  │
│  3. 调用 DeepL API (英文→中文)                    │
│  4. 通过回调函数返回结果                           │
└───────────────────┬───────────────────────────────┘
                    │ callback(original, translation)
                    ▼
┌───────────────────────────────────────────────────┐
│         展示层 (Presentation Layer)               │
│                                                   │
│  Tkinter GUI 主窗口                               │
│  • 控制按钮（开始/停止/导出）                      │
│  • 原文字幕显示区                                  │
│  • 翻译字幕显示区                                  │
│  • 字幕存储和导出                                  │
└───────────────────────────────────────────────────┘
```

---

## 🧵 线程模型

### 三线程并发设计

```
┌──────────────────────────────────────────────────┐
│              主线程 (Main Thread)                 │
│              Tkinter GUI 事件循环                 │
│                                                  │
│  • 处理用户交互 (按钮点击)                        │
│  • 更新GUI显示 (root.after)                      │
│  • 导出字幕文件                                   │
│  • 管理线程生命周期                               │
└────────┬─────────────────────────────────────────┘
         │ start_capture()
         │ stop_capture()
         ▼
┌──────────────────────────────────────────────────┐
│          线程1: AudioCaptureThread                │
│          (daemon=True)                           │
│                                                  │
│  while not stop_event.is_set():                 │
│      audio_chunk = capture(5秒)                 │
│      audio_queue.put(audio_chunk, timeout=1)    │
│                                                  │
│  • 捕获VB-Cable音频流                             │
│  • VAD语音检测（阶段2）                           │
│  • 固定5秒分块                                    │
└────────┬─────────────────────────────────────────┘
         │ Queue(maxsize=10)
         ▼
┌──────────────────────────────────────────────────┐
│       线程2: TranscriptionThread                 │
│       (daemon=True)                              │
│                                                  │
│  while not stop_event.is_set():                 │
│      audio = audio_queue.get(timeout=1)         │
│      text = whisper_api(audio)                  │
│      translation = deepl_api(text)              │
│      callback(text, translation)                │
│                                                  │
│  • 调用 OpenAI Whisper API                       │
│  • 调用 DeepL API                                │
│  • 错误重试机制（阶段2）                          │
└────────┬─────────────────────────────────────────┘
         │ callback
         ▼
┌──────────────────────────────────────────────────┐
│              主线程 GUI更新                       │
│                                                  │
│  root.after(0, update_subtitle, text, trans)    │
│  • 线程安全的GUI更新                              │
│  • 使用 storage_lock 保护并发访问                │
└──────────────────────────────────────────────────┘
```

### 线程同步机制

**共享资源**:
- `audio_queue`: Queue(maxsize=10) - 音频数据队列
- `stop_event`: threading.Event() - 停止信号
- `subtitle_storage`: SubtitleStorage() - 字幕存储（需要锁保护）
- `storage_lock`: threading.Lock() - 并发访问锁

**关键设计**:
- 所有工作线程设置 `daemon=True`，主线程退出时自动清理
- Queue 设置 `maxsize=10`，防止内存泄漏（最多缓存50秒音频）
- 使用 `timeout` 参数避免无限阻塞

---

## 📊 数据流时序图

```
用户     GUI      音频线程    转录线程    Whisper    DeepL
│        │          │          │           │         │
├─点击───►│          │          │           │         │
│  开始   │          │          │           │         │
│        ├─启动────►│          │           │         │
│        │          │          │           │         │
│        ├─启动────────────────►│           │         │
│        │          │          │           │         │
│        │          ├─捕获─────┤           │         │
│        │          │  5秒音频 │           │         │
│        │          │          │           │         │
│        │          ├─put─────►│           │         │
│        │          │  queue   │           │         │
│        │          │          │           │         │
│        │          │          ├─get──────┤         │
│        │          │          │           │         │
│        │          │          ├─POST─────►│         │
│        │          │          │  audio    │         │
│        │          │          │           │         │
│        │          │          │◄─返回────┤         │
│        │          │          │  text     │         │
│        │          │          │           │         │
│        │          │          ├─POST─────────────────►│
│        │          │          │  text                │
│        │          │          │                      │
│        │          │          │◄─返回────────────────┤
│        │          │          │  translation         │
│        │          │          │                      │
│        │◄─callback────────────┤                      │
│        │  (text, trans)       │                      │
│        │          │          │                      │
│◄─显示──┤          │          │                      │
│  字幕  │          │          │                      │
│        │          │          │                      │
│        │   (循环继续...)     │                      │
```

---

## 🔄 队列通信机制

### 阶段1：基础消息格式（字节流）

```python
# 音频捕获线程
audio_data = capture_5_seconds()  # bytes
audio_queue.put(audio_data)

# 转录翻译线程
audio_data = audio_queue.get(timeout=1)  # bytes
```

### 阶段2：优化消息格式（结构化）

```python
# 音频捕获线程（带VAD信息）
message = {
    'data': audio_data,          # bytes, 48kHz立体声音频
    'is_silent': False,          # bool, VAD检测结果
    'timestamp': 12.5            # float, 相对时间戳
}
audio_queue.put(message)

# 转录翻译线程
message = audio_queue.get(timeout=1)
if message['is_silent']:
    continue  # 跳过静音段，节省API成本
audio_data = message['data']
```

**优化说明**:
- 阶段1简单传递字节流，快速实现功能
- 阶段2传递结构化消息，实现VAD优化和模块解耦
- 结构化消息避免了 TranscriptionThread 直接调用 AudioCaptureThread 的方法

---

## 📁 项目目录结构

```
subtitle/
├── .ai-rules/                   # Claude Code 指导文档
│   ├── README.md               # 总览和导航
│   ├── architecture.md         # 本文档
│   ├── implementation-roadmap.md
│   ├── modules/
│   │   ├── audio-capture.md
│   │   ├── transcription.md
│   │   ├── storage.md
│   │   └── gui-main.md
│   └── technical/
│       ├── threading-concurrency.md
│       ├── vad-optimization.md
│       └── critical-fixes.md
│
├── app/                        # 应用代码
│   ├── __init__.py
│   ├── main.py                 # GUI主程序 (~240行)
│   ├── audio_capture.py        # 音频捕获 + VAD (~120行)
│   ├── transcription.py        # 转录翻译 (~100行)
│   ├── subtitle_storage.py     # 字幕存储 (~80行)
│   └── silero_vad_iterator.py  # VAD实现 (~150行, 阶段2)
│
├── logs/                       # 日志文件（运行时生成）
│   └── subtitle_*.log
│
├── .env                        # API密钥配置（不提交）
├── .env.example                # 配置模板
├── .gitignore
├── requirements.txt
├── README.md                   # 用户文档
└── plan.md                     # 原始详细设计文档
```

---

## 🔐 线程安全设计

### 共享资源保护

**SubtitleStorage 并发访问**:
```python
# main.py
storage_lock = threading.Lock()

# 写入（转录线程回调）
def update_subtitle(original, translation):
    with storage_lock:
        subtitle_storage.add_subtitle(original, translation)
    # GUI更新在锁外执行

# 读取（导出操作）
def export_srt():
    with storage_lock:
        data_copy = subtitle_storage.subtitles.copy()
    # 文件IO在锁外执行，避免长时间持锁
```

**Queue 线程安全**:
- Python 的 `queue.Queue` 本身是线程安全的
- 不需要额外加锁
- 但需要设置 `maxsize` 和 `timeout` 防止阻塞

---

## ⚙️ 配置管理

### 环境变量（.env）

```env
# API密钥（必填）
OPENAI_API_KEY=sk-xxxxx
DEEPL_API_KEY=xxxxx:fx

# 音频参数
AUDIO_SAMPLE_RATE=48000
AUDIO_CHUNK_DURATION=5

# 语言配置
SOURCE_LANGUAGE=en
TARGET_LANGUAGE=ZH

# VAD配置（阶段2）
ENABLE_VAD=true
VAD_THRESHOLD=0.5
VAD_MIN_SILENCE_MS=500
```

### 配置验证（main.py）

```python
# 验证布尔值配置
enable_vad = os.getenv('ENABLE_VAD', 'true').lower()
if enable_vad in ['true', '1', 'yes', 'on']:
    vad_enabled = True
else:
    vad_enabled = False

# 验证数值范围
vad_threshold = float(os.getenv('VAD_THRESHOLD', '0.5'))
if not 0.0 <= vad_threshold <= 1.0:
    raise ValueError("VAD_THRESHOLD 必须在 0.0-1.0 范围内")
```

---

## 🚦 状态管理

### 应用状态机

```
[初始状态]
    │
    ├─ start_capture() → [运行中]
    │                         │
    │                         ├─ 音频线程活跃
    │                         ├─ 转录线程活跃
    │                         └─ 字幕实时更新
    │                         │
    └─ stop_capture() ← ──────┘
           │
           ↓
    [已停止]
    │
    ├─ export_srt() → 导出字幕
    ├─ clear() → 清空字幕
    └─ start_capture() → [运行中]
```

### 线程状态检查

```python
# 健康检查（可选，阶段3）
def check_thread_health(self):
    if self.audio_thread and not self.audio_thread.is_alive():
        logging.warning("音频线程意外退出")
    if self.transcription_thread and not self.transcription_thread.is_alive():
        logging.warning("转录线程意外退出")
```

---

## 🎯 关键设计决策

### 为什么使用 Queue 而不是直接回调？
- ✅ 解耦音频捕获和转录处理
- ✅ 缓冲机制，处理速度不匹配时平滑运行
- ✅ 线程安全，无需额外加锁
- ✅ 支持背压（队列满时丢弃音频）

### 为什么音频分块设置为5秒？
- ⚖️ 延迟与成本的平衡
- 更短（如3秒）：延迟低，但API调用频繁，成本高
- 更长（如10秒）：成本低，但延迟高，用户体验差
- 5秒是最佳折中方案

### 为什么使用 daemon 线程？
- ✅ 主线程退出时自动清理工作线程
- ✅ 避免线程泄漏
- ⚠️ 但仍需要优雅停止机制（stop_event）

---

**最后更新**: 2025-11-05
**文档版本**: v1.0
