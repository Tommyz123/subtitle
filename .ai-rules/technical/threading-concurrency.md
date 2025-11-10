# 线程管理与并发控制

## 📝 概述

本文档说明项目中的线程管理策略、并发控制机制和常见陷阱。

**关键原则**:
- ✅ 使用Queue进行线程间通信
- ✅ 使用Event进行停止信号
- ✅ 使用Lock保护共享资源
- ✅ 使用root.after()切换到主线程

---

## 🧵 线程模型

### 三线程架构

```
主线程 (Main Thread)
  ├─ Tkinter GUI事件循环
  ├─ 启动/停止工作线程
  └─ 更新GUI显示

工作线程1 (AudioCaptureThread)
  ├─ daemon=True
  ├─ 捕获音频
  └─ 放入队列

工作线程2 (TranscriptionThread)
  ├─ daemon=True
  ├─ 从队列获取音频
  ├─ 调用API
  └─ 回调主线程
```

---

## 📊 线程间通信

### 1. Queue（队列通信）

**用途**: 音频数据从捕获线程传递到转录线程

```python
# main.py
audio_queue = queue.Queue(maxsize=10)  # ⚠️ 必须设置maxsize
```

**为什么需要maxsize？**

| 场景 | 无maxsize | 有maxsize=10 |
|------|----------|--------------|
| **转录慢于捕获** | 队列无限增长，最终OOM | 队列满时丢弃音频，内存可控 |
| **长时间运行** | 内存泄漏 | 最大9.6MB内存 |
| **停止响应** | 需要处理完所有队列数据 | 清空队列快速退出 |

**计算内存占用**:
```
每块音频: 48000 Hz * 2 channels * 2 bytes * 5 seconds = 960KB
队列maxsize=10: 960KB * 10 = 9.6MB
```

**正确用法**:
```python
# 音频捕获线程: 放入队列
try:
    audio_queue.put(audio_chunk, timeout=1)
except queue.Full:
    print("[WARNING] 队列已满，丢弃音频块")
    # 丢弃音频，防止阻塞

# 转录翻译线程: 从队列获取
try:
    audio_data = audio_queue.get(timeout=1)
except queue.Empty:
    continue
    # 超时后重新检查stop_event
```

---

### 2. Event（停止信号）

**用途**: 主线程通知工作线程停止

```python
# main.py
stop_event = threading.Event()

# 启动时清除信号
def start_capture():
    stop_event.clear()
    # 启动线程...

# 停止时设置信号
def stop_capture():
    stop_event.set()
    # 等待线程结束...

# 工作线程检查信号
def run(self):
    while not self.stop_event.is_set():
        # 工作循环...
```

**为什么使用Event而不是布尔标志？**
- ✅ Event是线程安全的
- ✅ 支持wait()阻塞等待
- ❌ 布尔标志需要额外加锁

---

### 3. Callback（回调函数）

**用途**: 转录线程返回结果到主线程

```python
# 转录线程调用回调
def run(self):
    # ... 转录翻译 ...
    self.callback(original_text, translated_text)

# 主线程的回调函数
def on_subtitle_ready(self, original, translation):
    # ⚠️ 此时在转录线程中，不能直接更新GUI！
    self.root.after(0, self.update_subtitle, original, translation)

# 主线程的GUI更新函数
def update_subtitle(self, original, translation):
    # ✅ 现在在主线程中，可以安全更新GUI
    self.original_text.insert(tk.END, original + "\n")
```

**为什么需要root.after(0, ...)?**
- ❌ Tkinter不是线程安全的
- ✅ `root.after(delay, func, *args)` 将任务调度到主线程事件循环
- `delay=0` 表示尽快执行

---

## 🔒 并发访问保护

### 共享资源: SubtitleStorage

**问题**:
```python
# 转录线程（通过回调）
subtitle_storage.add_subtitle(original, translation)  # 写入

# GUI主线程
subtitle_storage.export_srt(filepath)  # 读取
```

**风险**:
- 导出时正在写入 → 数据不一致
- 多次并发写入 → 列表损坏

**解决方案: threading.Lock**

```python
# main.py
storage_lock = threading.Lock()

# 写入时加锁
def update_subtitle(self, original, translation):
    # 更新GUI（无需锁）
    self.original_text.insert(tk.END, original + "\n")

    # 保存到存储（需要锁）
    with self.storage_lock:
        self.subtitle_storage.add_subtitle(original, translation)

# 读取时加锁
def export_srt(self):
    filepath = # ... 文件选择 ...
    if filepath:
        with self.storage_lock:
            self.subtitle_storage.export_srt(filepath)
```

---

### 优化: 减少持锁时间（阶段3）

**问题**: 导出SRT时长时间持锁，阻塞新字幕写入

```python
# ❌ 不推荐: 文件IO在锁内执行
def export_srt(self):
    with self.storage_lock:
        # 持锁时间 = 数据复制时间 + 文件IO时间
        self.subtitle_storage.export_srt(filepath)
```

**优化方案**:
```python
# ✅ 推荐: 先复制数据，锁外执行文件IO
def export_srt(self):
    filepath = filedialog.asksaveasfilename(...)
    if not filepath:
        return

    # 在锁内快速复制数据副本
    with self.storage_lock:
        data_copy = self.subtitle_storage.subtitles.copy()

    # 文件IO在锁外执行，不阻塞新字幕写入
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(data_copy, 1):
                # ... 写入SRT格式 ...
    except Exception as e:
        print(f"[ERROR] 导出失败: {e}")
```

---

## ⏹️ 线程清理流程

### 阶段1: 基础停止流程

```python
def stop_capture(self):
    # 1. 设置停止信号
    self.stop_event.set()

    # 2. 等待线程结束
    if self.audio_thread:
        self.audio_thread.join(timeout=5)
    if self.transcription_thread:
        self.transcription_thread.join(timeout=10)
```

**问题**:
- 转录线程可能阻塞在 `queue.get()` 等待新音频
- 最坏情况需要等待 5秒（音频超时）+ 10秒（转录超时）= 15秒

---

### 阶段2: 优化停止流程

```python
def stop_capture(self):
    # 1. 设置停止信号
    self.stop_event.set()

    # 2. 等待音频线程停止（5秒超时）
    if self.audio_thread:
        self.audio_thread.join(timeout=5)

    # 3. ⚠️ 清空队列（让转录线程快速退出阻塞）
    while not self.audio_queue.empty():
        try:
            self.audio_queue.get_nowait()
        except queue.Empty:
            break

    # 4. 等待转录线程停止（10秒超时）
    if self.transcription_thread:
        self.transcription_thread.join(timeout=10)

    # 5. ⚠️ 检查线程是否成功停止
    if self.audio_thread and self.audio_thread.is_alive():
        print("[WARNING] 音频线程未能正常停止")
    if self.transcription_thread and self.transcription_thread.is_alive():
        print("[WARNING] 转录线程未能正常停止")
```

**优化说明**:
- 步骤3清空队列，让 `queue.get(timeout=1)` 快速超时
- 步骤5检查线程健康状态，便于诊断问题

---

### 为什么设置不同的超时时间？

| 线程 | 超时时间 | 原因 |
|-----|---------|------|
| AudioCaptureThread | 5秒 | 最多等待一次循环（5秒音频块） |
| TranscriptionThread | 10秒 | 可能正在等待API响应（慢） |

---

## 🚨 常见陷阱和解决方案

### 陷阱1: 在工作线程直接更新GUI

```python
# ❌ 错误: 在转录线程直接操作Tkinter组件
def run(self):
    # ...
    self.gui.original_text.insert(tk.END, text)  # RuntimeError!
```

**解决方案**:
```python
# ✅ 正确: 使用回调 + root.after()
def run(self):
    # ...
    self.callback(original_text, translated_text)

# 在main.py
def on_subtitle_ready(self, original, translation):
    self.root.after(0, self.update_subtitle, original, translation)
```

---

### 陷阱2: 忘记设置daemon=True

```python
# ❌ 错误: 主线程退出但程序未结束
thread = AudioCaptureThread(...)
thread.start()  # daemon默认为False
```

**后果**: 主窗口关闭后，程序仍在后台运行

**解决方案**:
```python
# ✅ 正确: 设置daemon=True
thread = AudioCaptureThread(...)
thread.daemon = True
thread.start()
```

---

### 陷阱3: Queue无限增长

```python
# ❌ 错误: 队列无大小限制
audio_queue = queue.Queue()

# 音频捕获速度 > 转录速度
# → 队列无限增长 → 内存泄漏
```

**解决方案**:
```python
# ✅ 正确: 设置maxsize并处理Full异常
audio_queue = queue.Queue(maxsize=10)

try:
    audio_queue.put(chunk, timeout=1)
except queue.Full:
    print("[WARNING] 队列已满，丢弃音频块")
```

---

### 陷阱4: 共享资源无锁保护

```python
# ❌ 错误: 多线程并发访问列表
# 线程1
subtitle_storage.add_subtitle(...)

# 线程2
subtitle_storage.export_srt(...)
```

**解决方案**:
```python
# ✅ 正确: 使用Lock保护
storage_lock = threading.Lock()

with storage_lock:
    subtitle_storage.add_subtitle(...)

with storage_lock:
    subtitle_storage.export_srt(...)
```

---

### 陷阱5: join()无超时

```python
# ❌ 错误: 无限等待
self.audio_thread.join()  # 如果线程卡死，永远阻塞
```

**解决方案**:
```python
# ✅ 正确: 设置超时并检查
self.audio_thread.join(timeout=5)
if self.audio_thread.is_alive():
    print("[WARNING] 线程未能在5秒内停止")
```

---

## 📋 线程安全检查清单

### 启动阶段
- [ ] `audio_queue` 设置 `maxsize=10`
- [ ] 工作线程设置 `daemon=True`
- [ ] `stop_event.clear()` 清除上次的停止信号

### 运行阶段
- [ ] Queue操作使用 `timeout` 参数
- [ ] GUI更新使用 `root.after(0, ...)`
- [ ] 共享资源访问使用 `with lock:`

### 停止阶段
- [ ] `stop_event.set()` 设置停止信号
- [ ] 先停止音频线程，再停止转录线程
- [ ] 清空队列加速转录线程退出
- [ ] `join(timeout=...)` 设置超时
- [ ] 检查 `thread.is_alive()` 确认停止

---

## 🔍 调试技巧

### 打印线程ID

```python
import threading

def run(self):
    print(f"[DEBUG] 线程ID: {threading.current_thread().ident}")
    # ...
```

### 检查队列深度

```python
print(f"[DEBUG] 队列深度: {audio_queue.qsize()}")
```

### 监控锁竞争

```python
import time

def export_srt(self):
    start = time.time()
    with self.storage_lock:
        # ...
    elapsed = time.time() - start
    if elapsed > 0.1:
        print(f"[WARNING] 获取锁耗时 {elapsed:.2f}秒")
```

---

## 📚 参考资源

- Python threading文档: https://docs.python.org/3/library/threading.html
- Queue文档: https://docs.python.org/3/library/queue.html
- Tkinter线程安全: https://wiki.python.org/moin/TkInter

---

**最后更新**: 2025-11-05
**文档版本**: v1.0
