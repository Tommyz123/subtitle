# GUI主程序设计

## 📝 模块概述

**文件**: `app/main.py`
**职责**: Tkinter GUI界面，线程生命周期管理，用户交互处理

**代码量**:
- 阶段1（基础版）: ~150行
- 阶段2（添加锁和配置）: ~200行
- 阶段3（完善功能）: ~240行

---

## 🎯 核心功能

1. **GUI界面**: Tkinter窗口和组件
2. **线程管理**: 启动/停止音频捕获和转录线程
3. **字幕显示**: 实时更新原文和翻译文本框
4. **文件导出**: 选择文件路径并导出SRT字幕
5. **配置验证**: 验证环境变量和API Keys

---

## 🔧 类设计

### SubtitleApp

```python
class SubtitleApp:
    """
    字幕应用主类

    职责:
    - 创建GUI界面
    - 管理线程生命周期
    - 处理用户交互
    - 更新字幕显示
    """

    def __init__(self, root):
        """
        参数:
            root (tk.Tk): Tkinter主窗口
        """
        self.root = root

        # 线程通信
        self.audio_queue = queue.Queue()          # 阶段1: 无maxsize
        self.stop_event = threading.Event()

        # 数据存储
        self.subtitle_storage = SubtitleStorage()
        self.storage_lock = None  # 阶段2新增

        # 线程引用
        self.audio_thread = None
        self.transcription_thread = None

        # GUI组件
        self.original_text = None      # 原文显示区
        self.translated_text = None    # 译文显示区
        self.btn_start = None          # 开始按钮
        self.btn_stop = None           # 停止按钮
        self.btn_export = None         # 导出按钮

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        """创建GUI组件"""

    def start_capture(self):
        """开始捕获音频"""

    def stop_capture(self):
        """停止捕获"""

    def on_subtitle_ready(self, original, translation):
        """字幕回调函数（从转录线程调用）"""

    def update_subtitle(self, original, translation):
        """更新GUI显示（在主线程执行）"""

    def export_srt(self):
        """导出SRT字幕"""

    def on_closing(self):
        """窗口关闭事件处理（阶段2/3）"""
```

---

## 🚀 阶段1实现（基础版）

### 1. __init__()

```python
def __init__(self, root):
    """初始化应用"""
    self.root = root

    # 阶段1: 基础队列（无大小限制）
    self.audio_queue = queue.Queue()
    self.stop_event = threading.Event()

    # 数据存储
    from subtitle_storage import SubtitleStorage
    self.subtitle_storage = SubtitleStorage()

    # 线程引用
    self.audio_thread = None
    self.transcription_thread = None

    # 创建界面
    self.create_widgets()
```

---

### 2. create_widgets()

**职责**: 创建Tkinter GUI组件

```python
def create_widgets(self):
    """创建GUI组件"""
    import tkinter as tk
    from tkinter import ttk

    # 设置窗口标题和大小
    self.root.title("实时字幕系统")
    self.root.geometry("800x600")

    # === 控制按钮区域 ===
    control_frame = ttk.Frame(self.root, padding="10")
    control_frame.pack(fill=tk.X)

    self.btn_start = ttk.Button(
        control_frame,
        text="开始捕获",
        command=self.start_capture
    )
    self.btn_start.pack(side=tk.LEFT, padx=5)

    self.btn_stop = ttk.Button(
        control_frame,
        text="停止",
        command=self.stop_capture,
        state=tk.DISABLED  # 初始禁用
    )
    self.btn_stop.pack(side=tk.LEFT, padx=5)

    self.btn_export = ttk.Button(
        control_frame,
        text="导出SRT",
        command=self.export_srt
    )
    self.btn_export.pack(side=tk.LEFT, padx=5)

    # === 原文显示区域 ===
    original_label = ttk.Label(self.root, text="原文字幕:")
    original_label.pack(anchor=tk.W, padx=10)

    self.original_text = tk.Text(
        self.root,
        height=12,
        wrap=tk.WORD,
        font=("Arial", 11)
    )
    self.original_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # 添加滚动条
    original_scroll = ttk.Scrollbar(
        self.original_text,
        command=self.original_text.yview
    )
    self.original_text.config(yscrollcommand=original_scroll.set)
    original_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # === 翻译显示区域 ===
    translated_label = ttk.Label(self.root, text="翻译字幕:")
    translated_label.pack(anchor=tk.W, padx=10)

    self.translated_text = tk.Text(
        self.root,
        height=12,
        wrap=tk.WORD,
        font=("Microsoft YaHei", 11)  # 中文字体
    )
    self.translated_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

    # 添加滚动条
    translated_scroll = ttk.Scrollbar(
        self.translated_text,
        command=self.translated_text.yview
    )
    self.translated_text.config(yscrollcommand=translated_scroll.set)
    translated_scroll.pack(side=tk.RIGHT, fill=tk.Y)
```

**界面布局**:
```
┌────────────────────────────────────────┐
│ [开始捕获] [停止] [导出SRT]              │
├────────────────────────────────────────┤
│ 原文字幕:                               │
│ ┌────────────────────────────────────┐ │
│ │ Hello, how are you?                │ │
│ │ I'm doing great!                   │ │
│ │                                    │ │
│ └────────────────────────────────────┘ │
├────────────────────────────────────────┤
│ 翻译字幕:                               │
│ ┌────────────────────────────────────┐ │
│ │ 你好，你好吗？                       │ │
│ │ 我很好！                            │ │
│ │                                    │ │
│ └────────────────────────────────────┘ │
└────────────────────────────────────────┘
```

---

### 3. start_capture()

**职责**: 启动音频捕获和转录线程

```python
def start_capture(self):
    """开始捕获音频"""
    import os
    from audio_capture import AudioCaptureThread
    from transcription import TranscriptionThread

    # 1. 读取API Keys
    openai_key = os.getenv('OPENAI_API_KEY')
    deepl_key = os.getenv('DEEPL_API_KEY')

    if not openai_key or not deepl_key:
        print("[ERROR] 请在.env文件中配置API Keys")
        return

    # 2. 清除停止信号
    self.stop_event.clear()

    # 3. 启动音频捕获线程（阶段1: 不启用VAD）
    self.audio_thread = AudioCaptureThread(
        self.audio_queue,
        self.stop_event,
        enable_vad=False  # 阶段1暂不启用
    )
    self.audio_thread.daemon = True
    self.audio_thread.start()

    # 4. 启动转录翻译线程
    self.transcription_thread = TranscriptionThread(
        self.audio_queue,
        self.stop_event,
        self.on_subtitle_ready,  # 回调函数
        openai_key,
        deepl_key
    )
    self.transcription_thread.daemon = True
    self.transcription_thread.start()

    # 5. 更新按钮状态
    self.btn_start.config(state=tk.DISABLED)
    self.btn_stop.config(state=tk.NORMAL)

    print("[INFO] 字幕捕获已启动")
```

**注意事项**:
- ✅ 设置 `daemon=True` 确保主线程退出时自动清理
- ✅ 更新按钮状态提供视觉反馈
- ⚠️ 阶段1不验证VAD配置

---

### 4. stop_capture()

**职责**: 停止线程，清理资源

```python
def stop_capture(self):
    """停止捕获"""
    # 1. 设置停止信号
    self.stop_event.set()

    # 2. 等待线程结束
    if self.audio_thread:
        self.audio_thread.join(timeout=5)
    if self.transcription_thread:
        self.transcription_thread.join(timeout=10)

    # 3. 更新按钮状态
    self.btn_start.config(state=tk.NORMAL)
    self.btn_stop.config(state=tk.DISABLED)

    print("[INFO] 字幕捕获已停止")
```

**注意事项**:
- ✅ 使用 `timeout` 避免无限等待
- ⚠️ 阶段1不清空队列（阶段2优化）

---

### 5. on_subtitle_ready()

**职责**: 接收转录线程的回调（跨线程调用）

```python
def on_subtitle_ready(self, original, translation):
    """
    字幕回调函数（从转录线程调用）

    重要: 此方法在转录线程中执行，不能直接操作GUI！
    必须使用 root.after() 切换到主线程
    """
    # 线程安全: 切换到主线程执行GUI更新
    self.root.after(0, self.update_subtitle, original, translation)
```

**为什么需要 `root.after()`？**
- ❌ Tkinter不是线程安全的，不能在工作线程直接更新GUI
- ✅ `root.after(0, ...)` 将任务调度到主线程的事件循环
- 参数: `delay=0` 表示尽快执行

---

### 6. update_subtitle()

**职责**: 更新GUI显示字幕（在主线程执行）

```python
def update_subtitle(self, original, translation):
    """
    更新GUI显示（在主线程执行）

    参数:
        original (str): 原文
        translation (str): 翻译
    """
    # 1. 更新原文显示区
    self.original_text.insert(tk.END, original + "\n")
    self.original_text.see(tk.END)  # 自动滚动到最新

    # 2. 更新译文显示区
    self.translated_text.insert(tk.END, translation + "\n")
    self.translated_text.see(tk.END)

    # 3. 保存到存储（阶段1: 无锁保护）
    self.subtitle_storage.add_subtitle(original, translation)
```

**注意事项**:
- ✅ `tk.END` 表示文本末尾
- ✅ `see(tk.END)` 自动滚动到底部
- ⚠️ 阶段1不使用锁保护并发访问

---

### 7. export_srt()

**职责**: 选择文件路径并导出SRT字幕

```python
def export_srt(self):
    """导出SRT字幕"""
    from tkinter import filedialog

    # 1. 文件选择对话框
    filepath = filedialog.asksaveasfilename(
        defaultextension=".srt",
        filetypes=[
            ("SRT files", "*.srt"),
            ("All files", "*.*")
        ],
        initialfile="subtitle.srt"
    )

    # 2. 用户取消
    if not filepath:
        return

    # 3. 导出（阶段1: 无锁保护）
    try:
        self.subtitle_storage.export_srt(filepath)
        print(f"[INFO] 字幕已导出到: {filepath}")
    except Exception as e:
        print(f"[ERROR] 导出失败: {e}")
```

---

### 8. 主程序入口

```python
if __name__ == "__main__":
    import tkinter as tk
    from dotenv import load_dotenv
    import os

    # 加载环境变量
    load_dotenv()

    # 创建主窗口
    root = tk.Tk()

    # 创建应用
    app = SubtitleApp(root)

    # 启动事件循环
    root.mainloop()
```

---

## ⚡ 阶段2实现（优化版）

### 新增功能

#### 1. Queue大小限制

```python
def __init__(self, root):
    # ⚠️ 阶段2: 设置maxsize=10防止内存泄漏
    self.audio_queue = queue.Queue(maxsize=10)

    # ⚠️ 阶段2: 添加并发访问锁
    self.storage_lock = threading.Lock()

    # ... 其他初始化 ...
```

---

#### 2. VAD配置验证

```python
def start_capture(self):
    import os

    # ... API Keys验证 ...

    # ⚠️ 阶段2: 验证VAD配置
    enable_vad = os.getenv('ENABLE_VAD', 'true').lower()
    vad_enabled = enable_vad in ['true', '1', 'yes', 'on']

    # 启动音频线程（带VAD）
    self.audio_thread = AudioCaptureThread(
        self.audio_queue,
        self.stop_event,
        enable_vad=vad_enabled  # 使用配置值
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
        audio_thread=self.audio_thread  # ← 阶段2新增
    )
    self.transcription_thread.daemon = True
    self.transcription_thread.start()

    # ... 更新按钮状态 ...
```

---

#### 3. 线程清理优化

```python
def stop_capture(self):
    """停止捕获（阶段2优化）"""
    # 1. 设置停止信号
    self.stop_event.set()

    # 2. 等待音频线程停止
    if self.audio_thread:
        self.audio_thread.join(timeout=5)

    # 3. ⚠️ 清空队列（让转录线程快速退出）
    while not self.audio_queue.empty():
        try:
            self.audio_queue.get_nowait()
        except queue.Empty:
            break

    # 4. 等待转录线程停止
    if self.transcription_thread:
        self.transcription_thread.join(timeout=10)

    # 5. ⚠️ 检查线程是否成功停止
    if self.audio_thread and self.audio_thread.is_alive():
        print("[WARNING] 音频线程未能正常停止")
    if self.transcription_thread and self.transcription_thread.is_alive():
        print("[WARNING] 转录线程未能正常停止")

    # 6. 更新按钮状态
    self.btn_start.config(state=tk.NORMAL)
    self.btn_stop.config(state=tk.DISABLED)

    print("[INFO] 字幕捕获已停止")
```

**优化说明**:
- ✅ 清空队列加速转录线程退出
- ✅ 检查线程是否成功停止

---

#### 4. 并发访问保护

```python
def update_subtitle(self, original, translation):
    """更新GUI显示（带锁保护）"""
    # 1. 更新GUI（无需锁，仅主线程访问）
    self.original_text.insert(tk.END, original + "\n")
    self.original_text.see(tk.END)
    self.translated_text.insert(tk.END, translation + "\n")
    self.translated_text.see(tk.END)

    # 2. ⚠️ 保存到存储（使用锁保护）
    with self.storage_lock:
        self.subtitle_storage.add_subtitle(original, translation)

def export_srt(self):
    """导出SRT（带锁保护）"""
    from tkinter import filedialog

    filepath = filedialog.asksaveasfilename(
        defaultextension=".srt",
        filetypes=[("SRT files", "*.srt"), ("All files", "*.*")],
        initialfile="subtitle.srt"
    )

    if not filepath:
        return

    try:
        # ⚠️ 使用锁保护读取和导出
        with self.storage_lock:
            self.subtitle_storage.export_srt(filepath)
        print(f"[INFO] 字幕已导出到: {filepath}")
    except Exception as e:
        print(f"[ERROR] 导出失败: {e}")
```

---

#### 5. 窗口关闭事件处理

```python
def create_widgets(self):
    # ... 创建组件 ...

    # ⚠️ 阶段2: 注册窗口关闭事件
    self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

def on_closing(self):
    """窗口关闭事件处理"""
    # 1. 检查线程是否正在运行
    if self.audio_thread and self.audio_thread.is_alive():
        print("[INFO] 正在停止线程...")
        self.stop_capture()

    # 2. 销毁窗口
    self.root.destroy()
```

---

## 🎨 阶段3增强（可选）

### 1. 状态栏

```python
def create_widgets(self):
    # ... 原有组件 ...

    # 状态栏
    self.status_label = ttk.Label(
        self.root,
        text="就绪",
        relief=tk.SUNKEN,
        anchor=tk.W
    )
    self.status_label.pack(side=tk.BOTTOM, fill=tk.X)

def update_status(self, message):
    """更新状态栏"""
    self.status_label.config(text=message)
```

---

### 2. 清空按钮

```python
def create_widgets(self):
    # 控制按钮区域
    # ... 开始、停止、导出按钮 ...

    self.btn_clear = ttk.Button(
        control_frame,
        text="清空",
        command=self.clear_subtitles
    )
    self.btn_clear.pack(side=tk.LEFT, padx=5)

def clear_subtitles(self):
    """清空字幕"""
    # 清空文本框
    self.original_text.delete('1.0', tk.END)
    self.translated_text.delete('1.0', tk.END)

    # 清空存储
    with self.storage_lock:
        self.subtitle_storage.clear()

    print("[INFO] 字幕已清空")
```

---

### 3. 内存保护（Text组件）

```python
def update_subtitle(self, original, translation):
    # ... 更新字幕 ...

    # ⚠️ 内存保护: Text组件超过1000行时删除旧内容
    line_count = int(self.original_text.index('end-1c').split('.')[0])
    if line_count > 1000:
        self.original_text.delete('1.0', '200.0')
        self.translated_text.delete('1.0', '200.0')
```

---

## 📚 依赖项

```python
import tkinter as tk
from tkinter import ttk, filedialog
import threading
import queue
import os

from dotenv import load_dotenv
from audio_capture import AudioCaptureThread
from transcription import TranscriptionThread
from subtitle_storage import SubtitleStorage
```

---

## ⚠️ 常见错误

### 1. "RuntimeError: main thread is not in main loop"

**原因**: 在工作线程直接更新GUI

**解决方案**: 使用 `root.after(0, ...)`

---

### 2. 窗口关闭但程序未退出

**原因**: daemon线程阻塞在queue.get()

**解决方案**: 使用 `timeout=1` 参数

---

### 3. 字幕显示延迟高

**原因**: `root.after(0, ...)` 在事件循环繁忙时延迟执行

**解决方案**: 正常现象，无需优化

---

**最后更新**: 2025-11-05
**文档版本**: v1.0
