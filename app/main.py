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
from ui_components import TechColors, GlowButton, StatusIndicator, StatsCard
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
        """创建GUI组件 - 2025现代化设计（响应式布局）"""
        # 设置窗口标题和最小/默认大小
        self.root.title("🎬 实时语音翻译字幕系统")
        self.root.geometry("1000x900")  # 默认大小
        self.root.minsize(800, 700)  # 最小大小

        # 允许窗口缩放
        self.root.resizable(True, True)

        # 设置窗口背景色（科技感深空蓝黑）
        self.root.configure(bg=TechColors.BG_PRIMARY)

        # 设置窗口图标颜色主题
        style = ttk.Style()
        style.theme_use('clam')

        # 配置现代化样式
        style.configure('Modern.TLabelframe',
                       background='#ffffff',
                       borderwidth=0)
        style.configure('Modern.TLabelframe.Label',
                       font=('Microsoft YaHei', 11, 'bold'),
                       foreground='#1976d2',
                       background='#ffffff')

        # 配置Combobox样式
        style.configure('Modern.TCombobox',
                       fieldbackground='#ffffff',
                       background='#1976d2',
                       borderwidth=1,
                       relief='flat')

        # 配置Checkbutton样式
        style.configure('Modern.TCheckbutton',
                       background='#ffffff',
                       font=('Microsoft YaHei', 10))

        style.map('Modern.TCheckbutton',
                 background=[('active', '#ffffff')])

        # 创建主容器（带内边距）
        main_container = tk.Frame(self.root, bg=TechColors.BG_PRIMARY)
        main_container.pack(fill=tk.BOTH, expand=True)

        # === 顶部标题栏（科技感风格）===
        header_frame = tk.Frame(main_container, bg=TechColors.BG_PRIMARY, height=70)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        # 添加阴影效果（使用渐变Frame模拟）
        shadow = tk.Frame(main_container, bg=TechColors.BORDER_PRIMARY, height=1)  # 2 → 1 更细腻
        shadow.pack(fill=tk.X)

        tk.Label(
            header_frame,
            text="🎬 实时语音翻译字幕系统",
            font=("Microsoft YaHei", 20, "bold"),
            bg=TechColors.BG_PRIMARY,
            fg=TechColors.TEXT_PRIMARY
        ).pack(side=tk.LEFT, padx=30, pady=20)

        # 状态指示区域
        status_frame = tk.Frame(header_frame, bg=TechColors.BG_PRIMARY)
        status_frame.pack(side=tk.RIGHT, padx=30, pady=20)

        self.status_canvas = tk.Canvas(status_frame, width=16, height=16, bg=TechColors.BG_PRIMARY, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 10))
        # 使用StatusIndicator组件
        self.status_indicator_obj = StatusIndicator(self.status_canvas, 8, 8, radius=6)

        self.status_label = tk.Label(
            status_frame,
            text="未运行",
            font=("Microsoft YaHei", 11, "bold"),
            bg=TechColors.BG_PRIMARY,
            fg=TechColors.TEXT_PRIMARY
        )
        self.status_label.pack(side=tk.LEFT)

        # === 语言选择区域（卡片样式）===
        card_container = tk.Frame(main_container, bg=TechColors.BG_PRIMARY)
        card_container.pack(fill=tk.X, padx=20, pady=20)

        lang_card = tk.Frame(card_container, bg=TechColors.BG_CARD, highlightbackground=TechColors.BORDER_PRIMARY, highlightthickness=1)
        lang_card.pack(fill=tk.X)

        lang_frame = tk.Frame(lang_card, bg=TechColors.BG_CARD)
        lang_frame.pack(fill=tk.X, padx=20, pady=15)

        # 源语言选择
        source_lang_frame = tk.Frame(lang_frame, bg=TechColors.BG_CARD)
        source_lang_frame.pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(
            source_lang_frame,
            text="🎤 原语言:",
            font=("Microsoft YaHei", 11),
            bg=TechColors.BG_CARD,
            fg=TechColors.TEXT_SECONDARY
        ).pack(side=tk.LEFT, padx=(0, 8))
        self.source_lang_var = tk.StringVar(value="中文")
        self.source_lang_combo = ttk.Combobox(
            source_lang_frame,
            textvariable=self.source_lang_var,
            values=list(WHISPER_LANGUAGES.keys()),
            state="readonly",
            width=14,
            font=("Microsoft YaHei", 10),
            style='Modern.TCombobox'
        )
        self.source_lang_combo.pack(side=tk.LEFT)

        # 目标语言选择
        target_lang_frame = tk.Frame(lang_frame, bg=TechColors.BG_CARD)
        target_lang_frame.pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(
            target_lang_frame,
            text="🌍 翻译为:",
            font=("Microsoft YaHei", 11),
            bg=TechColors.BG_CARD,
            fg=TechColors.TEXT_SECONDARY
        ).pack(side=tk.LEFT, padx=(0, 8))
        self.target_lang_var = tk.StringVar(value="英语（美式）")
        self.target_lang_combo = ttk.Combobox(
            target_lang_frame,
            textvariable=self.target_lang_var,
            values=list(DEEPL_LANGUAGES.keys()),
            state="readonly",
            width=16,
            font=("Microsoft YaHei", 10),
            style='Modern.TCombobox'
        )
        self.target_lang_combo.pack(side=tk.LEFT)

        # 桌面字幕开关
        self.desktop_subtitle_var = tk.BooleanVar(value=False)
        self.desktop_subtitle_check = ttk.Checkbutton(
            lang_frame,
            text="📺 显示桌面字幕",
            variable=self.desktop_subtitle_var,
            style='Modern.TCheckbutton'
        )
        self.desktop_subtitle_check.pack(side=tk.LEFT, padx=(20, 0))

        # === 控制按钮区域（卡片样式）===
        control_card = tk.Frame(main_container, bg=TechColors.BG_CARD, highlightbackground=TechColors.BORDER_PRIMARY, highlightthickness=1)
        control_card.pack(fill=tk.X, padx=20, pady=(0, 20))

        control_frame = tk.Frame(control_card, bg=TechColors.BG_CARD)
        control_frame.pack(fill=tk.X, padx=20, pady=20)

        # 按钮容器
        button_container = tk.Frame(control_frame, bg=TechColors.BG_CARD)
        button_container.pack(side=tk.LEFT)

        # 创建霓虹发光按钮（科技感风格）
        self.btn_start = GlowButton(
            button_container,
            text="▶   开始捕获",  # 增加图标间距
            style='success',
            command=self.start_capture
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 15))  # 12 → 15 按钮间距更宽

        self.btn_stop = GlowButton(
            button_container,
            text="⏹   停止",  # 增加图标间距
            style='error',
            command=self.stop_capture,
            state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 15))

        self.btn_export = GlowButton(
            button_container,
            text="💾   导出SRT",  # 增加图标间距
            style='primary',
            command=self.export_srt
        )
        self.btn_export.pack(side=tk.LEFT)

        # 统计信息区域
        stats_container = tk.Frame(control_frame, bg=TechColors.BG_CARD)
        stats_container.pack(side=tk.RIGHT)

        self.stats_label = tk.Label(
            stats_container,
            text="📊 字幕: 0 条  |  ⏱️ 时长: 00:00:00",
            font=("Microsoft YaHei", 11),
            bg=TechColors.BG_CARD,
            fg=TechColors.TEXT_SECONDARY
        )
        self.stats_label.pack()

        # === 文本框区域容器（使用Grid布局实现真正的响应式）===
        textbox_container = tk.Frame(main_container, bg=TechColors.BG_PRIMARY)
        textbox_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # 配置Grid权重，使两个文本框各占50%高度
        textbox_container.grid_rowconfigure(0, weight=1)  # 原文框
        textbox_container.grid_rowconfigure(1, weight=1)  # 翻译框
        textbox_container.grid_columnconfigure(0, weight=1)  # 宽度自适应

        # === 原文显示区域（科技感卡片样式 - 响应式）===
        original_card = tk.Frame(textbox_container, bg=TechColors.BG_CARD, highlightbackground=TechColors.BORDER_PRIMARY, highlightthickness=1)
        original_card.grid(row=0, column=0, sticky='nsew', pady=(0, 20))  # 15 → 20 更透气

        # 标题栏
        original_header = tk.Frame(original_card, bg=TechColors.BG_CARD)
        original_header.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(
            original_header,
            text="📝 原文字幕",
            font=("Microsoft YaHei", 12, "bold"),
            bg=TechColors.BG_CARD,
            fg=TechColors.ACCENT_PRIMARY
        ).pack(side=tk.LEFT)

        # 文本框容器（响应式填充剩余空间）
        original_text_container = tk.Frame(original_card, bg=TechColors.BG_CARD)
        original_text_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        # 原文文本框（响应式）
        self.original_text = tk.Text(
            original_text_container,
            wrap=tk.WORD,
            font=("Consolas", 12),  # 11 → 12 更清晰易读
            bg=TechColors.BG_SECONDARY,
            fg=TechColors.TEXT_PRIMARY,
            insertbackground=TechColors.ACCENT_PRIMARY,
            selectbackground=TechColors.ACCENT_PRIMARY,
            selectforeground=TechColors.BG_PRIMARY,
            relief=tk.FLAT,
            padx=15,
            pady=15,
            borderwidth=0,
            highlightthickness=0,
            spacing1=4,  # 段落上方间距
            spacing3=4   # 段落下方间距
        )
        self.original_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        original_scroll = ttk.Scrollbar(
            original_text_container,
            command=self.original_text.yview
        )
        original_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        self.original_text.config(yscrollcommand=original_scroll.set)

        # === 翻译显示区域（科技感卡片样式 - 响应式）===
        translated_card = tk.Frame(textbox_container, bg=TechColors.BG_CARD, highlightbackground=TechColors.BORDER_PRIMARY, highlightthickness=1)
        translated_card.grid(row=1, column=0, sticky='nsew')

        # 标题栏
        translated_header = tk.Frame(translated_card, bg=TechColors.BG_CARD)
        translated_header.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(
            translated_header,
            text="🌍 翻译字幕",
            font=("Microsoft YaHei", 12, "bold"),
            bg=TechColors.BG_CARD,
            fg=TechColors.ACCENT_PRIMARY
        ).pack(side=tk.LEFT)

        # 文本框容器（响应式填充剩余空间）
        translated_text_container = tk.Frame(translated_card, bg=TechColors.BG_CARD)
        translated_text_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        # 翻译文本框（响应式）
        self.translated_text = tk.Text(
            translated_text_container,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 12),  # 11 → 12 更清晰易读
            bg=TechColors.BG_SECONDARY,
            fg=TechColors.TEXT_PRIMARY,
            insertbackground=TechColors.ACCENT_PRIMARY,
            selectbackground=TechColors.ACCENT_PRIMARY,
            selectforeground=TechColors.BG_PRIMARY,
            relief=tk.FLAT,
            padx=15,
            pady=15,
            borderwidth=0,
            highlightthickness=0,
            spacing1=4,  # 段落上方间距
            spacing3=4   # 段落下方间距
        )
        self.translated_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        translated_scroll = ttk.Scrollbar(
            translated_text_container,
            command=self.translated_text.yview
        )
        translated_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        self.translated_text.config(yscrollcommand=translated_scroll.set)

        # === 状态监控区（实时仪表盘）===
        monitor_container = tk.Frame(main_container, bg=TechColors.BG_PRIMARY)
        monitor_container.pack(fill=tk.X, padx=20, pady=(0, 20))

        # 2x2 Grid布局
        monitor_frame = tk.Frame(monitor_container, bg=TechColors.BG_PRIMARY)
        monitor_frame.pack(fill=tk.X)

        monitor_frame.grid_columnconfigure(0, weight=1)
        monitor_frame.grid_columnconfigure(1, weight=1)

        # 卡片1：音频捕获
        self.audio_card = StatsCard(monitor_frame, "🔊", "音频捕获", show_progress=True)
        self.audio_card.grid(row=0, column=0, sticky='ew', padx=(0, 10), pady=(0, 10))

        # 卡片2：队列状态
        self.queue_card = StatsCard(monitor_frame, "📊", "队列状态", show_progress=True)
        self.queue_card.grid(row=0, column=1, sticky='ew', padx=(10, 0), pady=(0, 10))

        # 卡片3：API统计
        self.api_card = StatsCard(monitor_frame, "💰", "API统计", show_progress=False)
        self.api_card.grid(row=1, column=0, sticky='ew', padx=(0, 10))

        # 卡片4：VAD优化
        self.vad_card = StatsCard(monitor_frame, "⚡", "VAD优化", show_progress=True)
        self.vad_card.grid(row=1, column=1, sticky='ew', padx=(10, 0))

        # === 底部状态栏（科技感样式）===
        status_bar = tk.Frame(main_container, bg=TechColors.BG_SECONDARY, height=40)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)

        self.status_bar_label = tk.Label(
            status_bar,
            text="💡 提示：选择语言后点击'开始捕获'，勾选'显示桌面字幕'可启用置顶字幕窗口",
            font=("Microsoft YaHei", 10),
            bg=TechColors.BG_SECONDARY,
            fg=TechColors.TEXT_SECONDARY,
            anchor=tk.W
        )
        self.status_bar_label.pack(side=tk.LEFT, padx=20, pady=10)

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
        self.btn_start.config(state=tk.DISABLED)
        self.btn_start.normal_bg = TechColors.TEXT_TERTIARY  # 禁用时使用灰色
        self.btn_start.config(bg=TechColors.TEXT_TERTIARY)
        self.btn_stop.config(state=tk.NORMAL)

        # 10. 更新状态指示和统计
        self._update_status("running")
        self.subtitle_count = 0
        self.start_time = time.time()
        self._start_stats_update()
        self._update_monitor_stats()  # 启动监控区数据更新

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
        self.btn_start.config(state=tk.NORMAL)
        self.btn_start.normal_bg = TechColors.ACCENT_SUCCESS
        self.btn_start.config(bg=TechColors.ACCENT_SUCCESS)
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_stop.normal_bg = TechColors.TEXT_TERTIARY
        self.btn_stop.config(bg=TechColors.TEXT_TERTIARY)

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
        # 添加调试信息
        print(f"[MAIN.PY] update_subtitle被调用:")
        print(f"  - original: '{original}' (长度: {len(original) if original else 0})")
        print(f"  - translation: '{translation}' (长度: {len(translation) if translation else 0})")

        # 更新原文区域
        self.original_text.insert(tk.END, original + "\n")
        self.original_text.see(tk.END)

        # 更新译文区域
        self.translated_text.insert(tk.END, translation + "\n")
        self.translated_text.see(tk.END)

        # 更新桌面字幕窗口
        if self.desktop_subtitle_window and self.desktop_subtitle_window.is_visible():
            print(f"[MAIN.PY] 正在调用 desktop_subtitle_window.update_subtitle")
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
        更新状态指示灯（科技感风格 + 呼吸动画）

        参数:
            status (str): 状态 - "running", "stopped"
        """
        # 使用StatusIndicator组件
        self.status_indicator_obj.set_status(status)

        if status == "running":
            self.status_label.config(text="运行中")
            self.status_bar_label.config(text="🎬 正在实时捕获音频并生成双语字幕...")
        elif status == "stopped":
            self.status_label.config(text="未运行")
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

    def _update_monitor_stats(self):
        """更新状态监控区数据（每秒更新）"""
        if not self.stop_event.is_set():
            # 1. 更新音频捕获状态
            if self.audio_thread and self.audio_thread.is_alive():
                self.audio_card.set_progress(0.92, "92%")
                self.audio_card.set_value("✓ 正常运行")
            else:
                self.audio_card.set_progress(0, "0%")
                self.audio_card.set_value("✗ 未运行")

            # 2. 更新队列状态
            queue_size = self.audio_queue.qsize()
            queue_progress = min(queue_size / 10.0, 1.0)
            self.queue_card.set_progress(queue_progress, f"{queue_size}/10")

            if queue_size < 5:
                self.queue_card.set_value("✓ 处理流畅")
            elif queue_size < 8:
                self.queue_card.set_value("⚠ 轻微堆积")
            else:
                self.queue_card.set_value("❗ 严重堆积")

            # 3. 更新API统计
            api_cost = self.subtitle_count * 0.006
            self.api_card.set_value(f"{self.subtitle_count}次 (${api_cost:.2f})")

            # 4. 更新VAD统计
            if hasattr(self, 'audio_thread') and self.audio_thread and hasattr(self.audio_thread, 'enable_vad'):
                if self.audio_thread.enable_vad and hasattr(self.audio_thread, 'get_vad_statistics'):
                    try:
                        stats = self.audio_thread.get_vad_statistics()
                        savings = stats.get('savings_percent', 0)
                        self.vad_card.set_progress(savings / 100.0, f"{savings:.0f}%")
                        self.vad_card.set_value("✓ 已启用")
                    except:
                        self.vad_card.set_progress(0, "0%")
                        self.vad_card.set_value("✓ 已启用")
                else:
                    self.vad_card.set_progress(0, "0%")
                    self.vad_card.set_value("✗ 未启用")
            else:
                self.vad_card.set_progress(0, "0%")
                self.vad_card.set_value("✗ 未启用")

            # 每1秒更新一次
            self.root.after(1000, self._update_monitor_stats)


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
