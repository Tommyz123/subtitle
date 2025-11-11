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
from desktop_subtitle import DesktopSubtitleWindow
import time

# ========== 语言配置 ==========
# Whisper支持的源语言
WHISPER_LANGUAGES = {
    "中文": "zh",
    "英语": "en",
    "日语": "ja",
    "韩语": "ko",
    "法语": "fr",
    "德语": "de",
    "西班牙语": "es",
    "俄语": "ru",
    "意大利语": "it",
    "葡萄牙语": "pt",
    "荷兰语": "nl",
    "阿拉伯语": "ar",
    "印地语": "hi",
    "泰语": "th",
    "越南语": "vi"
}

# DeepL支持的目标语言
DEEPL_LANGUAGES = {
    "中文（简体）": "ZH",
    "英语（美式）": "EN-US",
    "英语（英式）": "EN-GB",
    "日语": "JA",
    "韩语": "KO",
    "法语": "FR",
    "德语": "DE",
    "西班牙语": "ES",
    "俄语": "RU",
    "意大利语": "IT",
    "葡萄牙语（巴西）": "PT-BR",
    "葡萄牙语（葡萄牙）": "PT-PT",
    "荷兰语": "NL",
    "波兰语": "PL",
    "瑞典语": "SV",
    "丹麦语": "DA",
    "芬兰语": "FI",
    "希腊语": "EL",
    "捷克语": "CS",
    "罗马尼亚语": "RO",
    "匈牙利语": "HU",
    "保加利亚语": "BG",
    "斯洛伐克语": "SK",
    "斯洛文尼亚语": "SL",
    "爱沙尼亚语": "ET",
    "拉脱维亚语": "LV",
    "立陶宛语": "LT",
    "印尼语": "ID",
    "土耳其语": "TR",
    "乌克兰语": "UK"
}


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

        # 桌面字幕窗口
        self.desktop_subtitle_window = None

        # 统计信息
        self.subtitle_count = 0
        self.start_time = None

        # 创建界面
        self.create_widgets()

    def create_widgets(self):
        """创建GUI组件"""
        # 设置窗口标题和大小
        self.root.title("🎬 实时语音翻译字幕系统")
        self.root.geometry("950x750")

        # 设置窗口图标颜色主题
        style = ttk.Style()
        style.theme_use('clam')  # 使用更现代的主题

        # 配置样式
        style.configure('Title.TLabelframe', background='#f0f0f0')
        style.configure('Title.TLabelframe.Label', font=('Microsoft YaHei', 10, 'bold'))

        # === 顶部标题栏 ===
        header_frame = tk.Frame(self.root, bg='#2c3e50', height=50)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        tk.Label(
            header_frame,
            text="🎬 实时语音翻译字幕系统",
            font=("Microsoft YaHei", 16, "bold"),
            bg='#2c3e50',
            fg='white'
        ).pack(side=tk.LEFT, padx=20, pady=10)

        # 状态指示灯
        self.status_canvas = tk.Canvas(header_frame, width=20, height=20, bg='#2c3e50', highlightthickness=0)
        self.status_canvas.pack(side=tk.RIGHT, padx=20)
        self.status_indicator = self.status_canvas.create_oval(2, 2, 18, 18, fill='#95a5a6', outline='#7f8c8d')

        self.status_label = tk.Label(
            header_frame,
            text="● 未运行",
            font=("Microsoft YaHei", 10),
            bg='#2c3e50',
            fg='#ecf0f1'
        )
        self.status_label.pack(side=tk.RIGHT, padx=5)

        # === 语言选择区域 ===
        lang_frame = ttk.LabelFrame(self.root, text="⚙️ 语言设置", padding="15", style='Title.TLabelframe')
        lang_frame.pack(fill=tk.X, padx=15, pady=(15, 10))

        # 源语言选择
        source_lang_frame = ttk.Frame(lang_frame)
        source_lang_frame.pack(side=tk.LEFT, padx=5)

        ttk.Label(
            source_lang_frame,
            text="🎤 原语言:",
            font=("Microsoft YaHei", 10)
        ).pack(side=tk.LEFT, padx=5)
        self.source_lang_var = tk.StringVar(value="中文")
        self.source_lang_combo = ttk.Combobox(
            source_lang_frame,
            textvariable=self.source_lang_var,
            values=list(WHISPER_LANGUAGES.keys()),
            state="readonly",
            width=15,
            font=("Microsoft YaHei", 10)
        )
        self.source_lang_combo.pack(side=tk.LEFT, padx=5)

        # 目标语言选择
        target_lang_frame = ttk.Frame(lang_frame)
        target_lang_frame.pack(side=tk.LEFT, padx=5)

        ttk.Label(
            target_lang_frame,
            text="🌍 翻译为:",
            font=("Microsoft YaHei", 10)
        ).pack(side=tk.LEFT, padx=5)
        self.target_lang_var = tk.StringVar(value="英语（美式）")
        self.target_lang_combo = ttk.Combobox(
            target_lang_frame,
            textvariable=self.target_lang_var,
            values=list(DEEPL_LANGUAGES.keys()),
            state="readonly",
            width=15,
            font=("Microsoft YaHei", 10)
        )
        self.target_lang_combo.pack(side=tk.LEFT, padx=5)

        # 桌面字幕开关
        self.desktop_subtitle_var = tk.BooleanVar(value=False)
        self.desktop_subtitle_check = ttk.Checkbutton(
            lang_frame,
            text="📺 显示桌面字幕",
            variable=self.desktop_subtitle_var,
            style='TCheckbutton'
        )
        self.desktop_subtitle_check.pack(side=tk.LEFT, padx=20)

        # === 控制按钮区域 ===
        control_frame = tk.Frame(self.root, bg='#ecf0f1')
        control_frame.pack(fill=tk.X, padx=15, pady=10)

        # 按钮容器
        button_container = tk.Frame(control_frame, bg='#ecf0f1')
        button_container.pack(side=tk.LEFT, padx=10, pady=10)

        # 创建样式化的按钮
        self.btn_start = tk.Button(
            button_container,
            text="▶️  开始捕获",
            command=self.start_capture,
            font=("Microsoft YaHei", 11, "bold"),
            bg='#27ae60',
            fg='white',
            activebackground='#229954',
            activeforeground='white',
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2',
            width=12
        )
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = tk.Button(
            button_container,
            text="⏹️  停止",
            command=self.stop_capture,
            font=("Microsoft YaHei", 11, "bold"),
            bg='#95a5a6',
            fg='white',
            activebackground='#7f8c8d',
            activeforeground='white',
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2',
            width=12,
            state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        self.btn_export = tk.Button(
            button_container,
            text="💾  导出SRT",
            command=self.export_srt,
            font=("Microsoft YaHei", 11, "bold"),
            bg='#3498db',
            fg='white',
            activebackground='#2980b9',
            activeforeground='white',
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2',
            width=12
        )
        self.btn_export.pack(side=tk.LEFT, padx=5)

        # 统计信息区域
        stats_container = tk.Frame(control_frame, bg='#ecf0f1')
        stats_container.pack(side=tk.RIGHT, padx=10, pady=10)

        self.stats_label = tk.Label(
            stats_container,
            text="📊 字幕: 0 条 | ⏱️ 时长: 00:00:00",
            font=("Microsoft YaHei", 10),
            bg='#ecf0f1',
            fg='#34495e'
        )
        self.stats_label.pack()

        # === 原文显示区域 ===
        original_frame_container = ttk.LabelFrame(
            self.root,
            text="📝 原文字幕",
            padding="10",
            style='Title.TLabelframe'
        )
        original_frame_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5, 5))

        # 原文文本框和滚动条
        self.original_text = tk.Text(
            original_frame_container,
            wrap=tk.WORD,
            font=("Arial", 11),
            bg='#ffffff',
            fg='#2c3e50',
            insertbackground='#3498db',
            selectbackground='#3498db',
            selectforeground='white',
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.original_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        original_scroll = ttk.Scrollbar(
            original_frame_container,
            command=self.original_text.yview
        )
        original_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.original_text.config(yscrollcommand=original_scroll.set)

        # === 翻译显示区域 ===
        translated_frame_container = ttk.LabelFrame(
            self.root,
            text="🌍 翻译字幕",
            padding="10",
            style='Title.TLabelframe'
        )
        translated_frame_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=(5, 10))

        # 翻译文本框和滚动条
        self.translated_text = tk.Text(
            translated_frame_container,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 11),
            bg='#ffffff',
            fg='#2c3e50',
            insertbackground='#3498db',
            selectbackground='#3498db',
            selectforeground='white',
            relief=tk.FLAT,
            padx=10,
            pady=10
        )
        self.translated_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        translated_scroll = ttk.Scrollbar(
            translated_frame_container,
            command=self.translated_text.yview
        )
        translated_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.translated_text.config(yscrollcommand=translated_scroll.set)

        # === 底部状态栏 ===
        status_bar = tk.Frame(self.root, bg='#34495e', height=25)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)

        self.status_bar_label = tk.Label(
            status_bar,
            text="💡 提示：选择语言后点击'开始捕获'，勾选'显示桌面字幕'可启用置顶字幕窗口",
            font=("Microsoft YaHei", 9),
            bg='#34495e',
            fg='#ecf0f1',
            anchor=tk.W
        )
        self.status_bar_label.pack(side=tk.LEFT, padx=10)

    def start_capture(self):
        """开始捕获音频 (阶段2: 支持VAD配置 + 语言选择)"""
        # 1. 读取API Keys
        openai_key = os.getenv('OPENAI_API_KEY')
        deepl_key = os.getenv('DEEPL_API_KEY')

        if not openai_key or not deepl_key:
            print("[ERROR] 请在.env文件中配置API Keys")
            print("[ERROR] 请确保.env文件中包含:")
            print("[ERROR]   OPENAI_API_KEY=your_openai_key")
            print("[ERROR]   DEEPL_API_KEY=your_deepl_key")
            return

        # 2. 获取用户选择的语言
        source_lang_name = self.source_lang_var.get()
        target_lang_name = self.target_lang_var.get()
        source_lang_code = WHISPER_LANGUAGES[source_lang_name]
        target_lang_code = DEEPL_LANGUAGES[target_lang_name]

        print(f"[INFO] 源语言: {source_lang_name} ({source_lang_code})")
        print(f"[INFO] 目标语言: {target_lang_name} ({target_lang_code})")

        # 3. P0修复: 配置验证支持多格式
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

        # 6. 启动转录翻译线程 (阶段2: 传入audio_thread引用 + 语言参数)
        self.transcription_thread = TranscriptionThread(
            self.audio_queue,
            self.stop_event,
            self.on_subtitle_ready,
            openai_key,
            deepl_key,
            source_lang=source_lang_code,  # ← 传递用户选择的源语言
            target_lang=target_lang_code,  # ← 传递用户选择的目标语言
            audio_thread=self.audio_thread  # ← 传递引用用于VAD检查
        )
        self.transcription_thread.daemon = True
        self.transcription_thread.start()

        # 7. 创建桌面字幕窗口（如果启用）
        if self.desktop_subtitle_var.get():
            if self.desktop_subtitle_window is None:
                self.desktop_subtitle_window = DesktopSubtitleWindow(self.root)
            self.desktop_subtitle_window.show()
            print("[INFO] 桌面字幕窗口已启用")
        else:
            if self.desktop_subtitle_window:
                self.desktop_subtitle_window.hide()

        # 8. 启动队列监控任务（方案B优化）
        self.start_queue_monitor()

        # 9. 更新按钮状态
        self.btn_start.config(state=tk.DISABLED, bg='#95a5a6')
        self.btn_stop.config(state=tk.NORMAL, bg='#e74c3c')

        # 10. 更新状态指示和统计
        self._update_status("running")
        self.subtitle_count = 0
        self.start_time = time.time()
        self._start_stats_update()

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
        """停止捕获 - 包含P0修复 + VAD统计 + 关闭桌面字幕"""
        # 1. 设置停止信号
        self.stop_event.set()

        # 方案B优化: 停止队列监控
        self.monitor_active = False

        # 隐藏桌面字幕窗口（但不销毁，以便下次使用）
        if self.desktop_subtitle_window:
            self.desktop_subtitle_window.hide()

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
        self.btn_start.config(state=tk.NORMAL, bg='#27ae60')
        self.btn_stop.config(state=tk.DISABLED, bg='#95a5a6')

        # 5. 更新状态指示
        self._update_status("stopped")

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
        # 详细调试日志
        print(f"[GUI更新] 原文长度: {len(original)} | 翻译长度: {len(translation)}")
        print(f"[GUI更新] 原文内容: '{original}'")
        print(f"[GUI更新] 翻译内容: '{translation}'")

        # 验证文本框状态
        print(f"[GUI状态] original_text存在: {self.original_text is not None}")
        print(f"[GUI状态] translated_text存在: {self.translated_text is not None}")

        # 更新原文区域
        self.original_text.insert(tk.END, original + "\n")
        self.original_text.see(tk.END)
        print(f"[GUI更新] ✓ 原文已插入到文本框")

        # 更新译文区域
        self.translated_text.insert(tk.END, translation + "\n")
        self.translated_text.see(tk.END)
        print(f"[GUI更新] ✓ 翻译已插入到文本框")

        # 验证文本框内容
        original_content = self.original_text.get("1.0", tk.END)
        translated_content = self.translated_text.get("1.0", tk.END)
        print(f"[GUI验证] 原文框当前行数: {original_content.count(chr(10))}")
        print(f"[GUI验证] 翻译框当前行数: {translated_content.count(chr(10))}")

        # 更新桌面字幕窗口
        if self.desktop_subtitle_window and self.desktop_subtitle_window.is_visible():
            self.desktop_subtitle_window.update_subtitle(original, translation)

        # P0修复: 使用锁保护SubtitleStorage并发访问
        with self.storage_lock:
            self.subtitle_storage.add_subtitle(original, translation)

        # 更新统计信息
        self.subtitle_count += 1

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
            messagebox.showinfo("导出成功", f"字幕已成功导出到:\n{filepath}")

    def _update_status(self, status):
        """
        更新状态指示灯

        参数:
            status (str): 状态 - "running", "stopped"
        """
        if status == "running":
            self.status_canvas.itemconfig(self.status_indicator, fill='#27ae60', outline='#229954')
            self.status_label.config(text="● 运行中")
            self.status_bar_label.config(text="🎬 正在捕获音频并生成字幕...")
        elif status == "stopped":
            self.status_canvas.itemconfig(self.status_indicator, fill='#95a5a6', outline='#7f8c8d')
            self.status_label.config(text="● 未运行")
            self.status_bar_label.config(text="💡 提示：选择语言后点击'开始捕获'，勾选'显示桌面字幕'可启用置顶字幕窗口")

    def _start_stats_update(self):
        """启动统计信息更新"""
        def update_stats():
            if self.start_time:
                elapsed = int(time.time() - self.start_time)
                hours = elapsed // 3600
                minutes = (elapsed % 3600) // 60
                seconds = elapsed % 60
                time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

                self.stats_label.config(text=f"📊 字幕: {self.subtitle_count} 条 | ⏱️ 时长: {time_str}")

                # 继续更新
                if not self.stop_event.is_set():
                    self.root.after(1000, update_stats)

        update_stats()


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
