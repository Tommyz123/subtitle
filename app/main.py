"""
GUI主程序 - 阶段2优化版本 + 所有P0修复

职责:
- Tkinter GUI界面
- 线程生命周期管理
- 用户交互处理
- 字幕显示和导出

阶段1+2包含的P0修复:
- Queue设置maxsize=10 (防止内存泄漏)
- SubtitleStorage并发访问使用Lock
- 线程清理时清空队列
- P0修复: 配置验证支持多格式 (true/1/yes/on)
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import queue
import os
import sys
import io
from dotenv import load_dotenv

# 设置stdout为UTF-8编码(解决Windows控制台中文显示问题)
if sys.platform == 'win32':
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except:
        pass

from audio_capture import AudioCaptureThread
from transcription import TranscriptionThread
from subtitle_storage import SubtitleStorage


def parse_bool_config(value, default=False):
    """
    P0修复: 配置验证支持多格式

    支持格式:
    - 布尔值: True/False
    - 字符串: "true"/"false", "1"/"0", "yes"/"no", "on"/"off"
    - 数字: 1/0

    参数:
        value: 配置值
        default (bool): 默认值

    返回:
        bool: 解析后的布尔值
    """
    if value is None:
        return default

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    if isinstance(value, str):
        value_lower = value.lower().strip()
        if value_lower in ['true', '1', 'yes', 'on']:
            return True
        elif value_lower in ['false', '0', 'no', 'off']:
            return False

    return default


class SubtitleApp:
    """字幕应用主类 - GUI和线程管理"""

    def __init__(self, root):
        """初始化应用"""
        self.root = root

        # P0修复: Queue设置maxsize防止内存泄漏
        # 阶段A修复: 从10扩大到30，适配8秒音频块的处理时间
        # 方案B修复: 移除maxsize限制，借鉴WhisperLiveKit的无限队列策略
        # 通过动态监控和批量处理来管理内存，而不是丢弃数据
        self.audio_queue = queue.Queue()  # 无限队列
        self.stop_event = threading.Event()

        # 数据存储
        self.subtitle_storage = SubtitleStorage()

        # P0修复: SubtitleStorage并发访问保护
        self.storage_lock = threading.Lock()

        # 线程引用
        self.audio_thread = None
        self.transcription_thread = None

        # 方案B优化: 队列监控
        self.monitor_active = False

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        """创建GUI组件"""
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
            state=tk.DISABLED
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
        original_label.pack(anchor=tk.W, padx=10, pady=(10, 0))

        # 原文文本框和滚动条容器
        original_frame = ttk.Frame(self.root)
        original_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.original_text = tk.Text(
            original_frame,
            height=12,
            wrap=tk.WORD,
            font=("Arial", 11)
        )
        self.original_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        original_scroll = ttk.Scrollbar(
            original_frame,
            command=self.original_text.yview
        )
        original_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.original_text.config(yscrollcommand=original_scroll.set)

        # === 翻译显示区域 ===
        translated_label = ttk.Label(self.root, text="翻译字幕:")
        translated_label.pack(anchor=tk.W, padx=10, pady=(10, 0))

        # 翻译文本框和滚动条容器
        translated_frame = ttk.Frame(self.root)
        translated_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.translated_text = tk.Text(
            translated_frame,
            height=12,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 11)
        )
        self.translated_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        translated_scroll = ttk.Scrollbar(
            translated_frame,
            command=self.translated_text.yview
        )
        translated_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.translated_text.config(yscrollcommand=translated_scroll.set)

    def start_capture(self):
        """开始捕获音频 (阶段2: 支持VAD配置)"""
        # 1. 读取API Keys
        openai_key = os.getenv('OPENAI_API_KEY')
        deepl_key = os.getenv('DEEPL_API_KEY')

        if not openai_key or not deepl_key:
            print("[ERROR] 请在.env文件中配置API Keys")
            print("[ERROR] 请确保.env文件中包含:")
            print("[ERROR]   OPENAI_API_KEY=your_openai_key")
            print("[ERROR]   DEEPL_API_KEY=your_deepl_key")
            return

        # 2. P0修复: 配置验证支持多格式
        enable_vad_raw = os.getenv('ENABLE_VAD', 'true')
        vad_enabled = parse_bool_config(enable_vad_raw, default=True)

        print(f"[INFO] VAD功能: {'启用' if vad_enabled else '禁用'}")

        # 3. 清除停止信号
        self.stop_event.clear()

        # 4. 清空字幕存储（使用锁保护）
        with self.storage_lock:
            self.subtitle_storage.clear()

        # 清空文本框
        self.original_text.delete(1.0, tk.END)
        self.translated_text.delete(1.0, tk.END)

        # 5. 启动音频捕获线程 (阶段2: 传入VAD配置)
        self.audio_thread = AudioCaptureThread(
            self.audio_queue,
            self.stop_event,
            enable_vad=vad_enabled
        )
        self.audio_thread.daemon = True
        self.audio_thread.start()

        # 6. 启动转录翻译线程 (阶段2: 传入audio_thread引用)
        self.transcription_thread = TranscriptionThread(
            self.audio_queue,
            self.stop_event,
            self.on_subtitle_ready,
            openai_key,
            deepl_key,
            audio_thread=self.audio_thread  # ← 传递引用用于VAD检查
        )
        self.transcription_thread.daemon = True
        self.transcription_thread.start()

        # 7. 启动队列监控任务（方案B优化）
        self.start_queue_monitor()

        # 8. 更新按钮状态
        self.btn_start.config(state=tk.DISABLED)
        self.btn_stop.config(state=tk.NORMAL)

        print("[INFO] 字幕捕获已启动")

    def start_queue_monitor(self):
        """
        方案B优化: 启动队列监控任务
        定期检查队列大小，输出警告日志
        """
        self.monitor_active = True

        def monitor_loop():
            """监控循环"""
            while self.monitor_active and not self.stop_event.is_set():
                try:
                    queue_size = self.audio_queue.qsize()

                    # 警告阈值
                    if queue_size > 20:
                        print(f"[WARNING] 队列堆积: {queue_size} 块音频待处理")
                    elif queue_size > 50:
                        print(f"[ERROR] 队列严重堆积: {queue_size} 块, 系统可能无法跟上")
                    elif queue_size > 10:
                        print(f"[INFO] 队列状态: {queue_size} 块")

                    # 每5秒检查一次
                    import time
                    time.sleep(5)

                except Exception as e:
                    print(f"[ERROR] 队列监控异常: {e}")

        # 启动监控线程
        monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        monitor_thread.start()

    def stop_capture(self):
        """停止捕获 - 包含P0修复 + VAD统计"""
        # 1. 设置停止信号
        self.stop_event.set()

        # 方案B优化: 停止队列监控
        self.monitor_active = False

        # 2. 等待音频线程停止
        if self.audio_thread:
            self.audio_thread.join(timeout=5)

            # 阶段2: 打印VAD统计
            if self.audio_thread.enable_vad:
                stats = self.audio_thread.get_vad_statistics()
                print(f"[VAD最终统计] 总共 {stats['total']} 块, "
                      f"跳过 {stats['skipped']} 块, "
                      f"节省 {stats['savings_percent']:.1f}% 成本")

        # P0修复: 清空队列加速转录线程退出
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        # 3. 等待转录线程停止
        if self.transcription_thread:
            self.transcription_thread.join(timeout=10)

        # 4. 更新按钮状态
        self.btn_start.config(state=tk.NORMAL)
        self.btn_stop.config(state=tk.DISABLED)

        print("[INFO] 字幕捕获已停止")

    def on_subtitle_ready(self, original, translation):
        """
        字幕回调函数 - 从转录线程调用

        参数:
            original (str): 原文
            translation (str): 翻译

        注意:
            - 此方法在转录线程中调用
            - 必须使用root.after确保GUI更新在主线程执行
        """
        # 使用after(0)确保在主线程执行GUI更新
        self.root.after(0, self.update_subtitle, original, translation)

    def update_subtitle(self, original, translation):
        """
        更新GUI显示 - 在主线程执行

        参数:
            original (str): 原文
            translation (str): 翻译
        """
        # 更新原文区域
        self.original_text.insert(tk.END, original + "\n")
        self.original_text.see(tk.END)

        # 更新译文区域
        self.translated_text.insert(tk.END, translation + "\n")
        self.translated_text.see(tk.END)

        # P0修复: 使用锁保护SubtitleStorage并发访问
        with self.storage_lock:
            self.subtitle_storage.add_subtitle(original, translation)

    def export_srt(self):
        """导出SRT字幕"""
        # 选择保存路径
        filepath = filedialog.asksaveasfilename(
            defaultextension=".srt",
            filetypes=[("SRT files", "*.srt"), ("All files", "*.*")]
        )

        if filepath:
            # P0修复: 使用锁保护导出操作
            with self.storage_lock:
                self.subtitle_storage.export_srt(filepath)
            print(f"[INFO] 字幕已导出到: {filepath}")


def main():
    """程序入口"""
    # 加载环境变量
    load_dotenv()

    # 创建主窗口
    root = tk.Tk()

    # 创建应用
    app = SubtitleApp(root)

    # 启动主循环
    root.mainloop()


if __name__ == "__main__":
    main()
