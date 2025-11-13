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
        """创建GUI组件 - 2025现代化设计（响应式布局）"""
        # 设置窗口标题和最小/默认大小
        self.root.title("🎬 实时语音翻译字幕系统")
        self.root.geometry("1000x900")  # 默认大小
        self.root.minsize(800, 700)  # 最小大小

        # 允许窗口缩放
        self.root.resizable(True, True)

        # 设置窗口背景色（Material Design浅灰）
        self.root.configure(bg='#f5f5f5')

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
        main_container = tk.Frame(self.root, bg='#f5f5f5')
        main_container.pack(fill=tk.BOTH, expand=True)

        # === 顶部标题栏（Material Design风格）===
        header_frame = tk.Frame(main_container, bg='#1976d2', height=70)
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        # 添加阴影效果（使用渐变Frame模拟）
        shadow = tk.Frame(main_container, bg='#e0e0e0', height=2)
        shadow.pack(fill=tk.X)

        tk.Label(
            header_frame,
            text="🎬 实时语音翻译字幕系统",
            font=("Microsoft YaHei", 20, "bold"),
            bg='#1976d2',
            fg='white'
        ).pack(side=tk.LEFT, padx=30, pady=20)

        # 状态指示区域
        status_frame = tk.Frame(header_frame, bg='#1976d2')
        status_frame.pack(side=tk.RIGHT, padx=30, pady=20)

        self.status_canvas = tk.Canvas(status_frame, width=16, height=16, bg='#1976d2', highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.status_indicator = self.status_canvas.create_oval(2, 2, 14, 14, fill='#bdbdbd', outline='#757575', width=2)

        self.status_label = tk.Label(
            status_frame,
            text="未运行",
            font=("Microsoft YaHei", 11, "bold"),
            bg='#1976d2',
            fg='white'
        )
        self.status_label.pack(side=tk.LEFT)

        # === 语言选择区域（卡片样式）===
        card_container = tk.Frame(main_container, bg='#f5f5f5')
        card_container.pack(fill=tk.X, padx=20, pady=20)

        lang_card = tk.Frame(card_container, bg='#ffffff', highlightbackground='#e0e0e0', highlightthickness=1)
        lang_card.pack(fill=tk.X)

        lang_frame = tk.Frame(lang_card, bg='#ffffff')
        lang_frame.pack(fill=tk.X, padx=20, pady=15)

        # 源语言选择
        source_lang_frame = tk.Frame(lang_frame, bg='#ffffff')
        source_lang_frame.pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(
            source_lang_frame,
            text="🎤 原语言:",
            font=("Microsoft YaHei", 11),
            bg='#ffffff',
            fg='#424242'
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
        target_lang_frame = tk.Frame(lang_frame, bg='#ffffff')
        target_lang_frame.pack(side=tk.LEFT, padx=(0, 20))

        tk.Label(
            target_lang_frame,
            text="🌍 翻译为:",
            font=("Microsoft YaHei", 11),
            bg='#ffffff',
            fg='#424242'
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

        # === 转录模式选择区域（新增卡片）===
        model_card = tk.Frame(card_container, bg='#ffffff', highlightbackground='#e0e0e0', highlightthickness=1)
        model_card.pack(fill=tk.X, pady=(10, 0))

        model_frame = tk.Frame(model_card, bg='#ffffff')
        model_frame.pack(fill=tk.X, padx=20, pady=15)

        # 标题
        tk.Label(
            model_frame,
            text="🤖 转录模式",
            font=("Microsoft YaHei", 11, 'bold'),
            bg='#ffffff',
            fg='#1976d2'
        ).pack(anchor=tk.W)

        # 模式选择区域
        mode_selection_frame = tk.Frame(model_frame, bg='#ffffff')
        mode_selection_frame.pack(fill=tk.X, pady=(10, 0))

        # 转录模式单选框
        self.transcription_mode_var = tk.StringVar(value="api")

        mode_radio_frame = tk.Frame(mode_selection_frame, bg='#ffffff')
        mode_radio_frame.pack(side=tk.LEFT)

        # API 模式
        self.api_radio = tk.Radiobutton(
            mode_radio_frame,
            text="☁️  API模式 (在线)",
            variable=self.transcription_mode_var,
            value="api",
            font=("Microsoft YaHei", 10),
            bg='#ffffff',
            fg='#424242',
            selectcolor='#ffffff',
            activebackground='#ffffff',
            command=self.on_mode_change
        )
        self.api_radio.pack(side=tk.LEFT, padx=(0, 20))

        # 本地模式
        self.local_radio = tk.Radiobutton(
            mode_radio_frame,
            text="💻  本地模式 (离线)",
            variable=self.transcription_mode_var,
            value="local",
            font=("Microsoft YaHei", 10),
            bg='#ffffff',
            fg='#424242',
            selectcolor='#ffffff',
            activebackground='#ffffff',
            command=self.on_mode_change
        )
        self.local_radio.pack(side=tk.LEFT)

        # 本地模型大小选择
        model_size_frame = tk.Frame(mode_selection_frame, bg='#ffffff')
        model_size_frame.pack(side=tk.LEFT, padx=(30, 0))

        tk.Label(
            model_size_frame,
            text="模型大小:",
            font=("Microsoft YaHei", 10),
            bg='#ffffff',
            fg='#424242'
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.model_size_var = tk.StringVar(value="base")
        self.model_size_combo = ttk.Combobox(
            model_size_frame,
            textvariable=self.model_size_var,
            values=["tiny", "base", "small", "medium", "large-v2"],
            state="readonly",
            width=12,
            font=("Microsoft YaHei", 9),
            style='Modern.TCombobox'
        )
        self.model_size_combo.pack(side=tk.LEFT)
        self.model_size_combo.config(state=tk.DISABLED)  # 默认禁用

        # 提示信息标签
        self.mode_info_label = tk.Label(
            model_frame,
            text="💡 API模式: 需要OpenAI API Key，在线调用，按量付费",
            font=("Microsoft YaHei", 9),
            bg='#ffffff',
            fg='#757575',
            justify=tk.LEFT
        )
        self.mode_info_label.pack(anchor=tk.W, pady=(8, 0))

        # === 控制按钮区域（卡片样式）===
        control_card = tk.Frame(main_container, bg='#ffffff', highlightbackground='#e0e0e0', highlightthickness=1)
        control_card.pack(fill=tk.X, padx=20, pady=(0, 20))

        control_frame = tk.Frame(control_card, bg='#ffffff')
        control_frame.pack(fill=tk.X, padx=20, pady=20)

        # 按钮容器
        button_container = tk.Frame(control_frame, bg='#ffffff')
        button_container.pack(side=tk.LEFT)

        # 创建现代化圆角按钮（Material Design风格）
        self.btn_start = tk.Button(
            button_container,
            text="▶  开始捕获",
            command=self.start_capture,
            font=("Microsoft YaHei", 11, "bold"),
            bg='#4caf50',
            fg='white',
            activebackground='#45a049',
            activeforeground='white',
            relief=tk.FLAT,
            padx=25,
            pady=12,
            cursor='hand2',
            borderwidth=0,
            highlightthickness=0
        )
        self.btn_start.pack(side=tk.LEFT, padx=(0, 12))
        # 添加悬停效果
        self.btn_start.bind('<Enter>', lambda e: self.btn_start.config(bg='#45a049'))
        self.btn_start.bind('<Leave>', lambda e: self.btn_start.config(bg='#4caf50'))

        self.btn_stop = tk.Button(
            button_container,
            text="⏹  停止",
            command=self.stop_capture,
            font=("Microsoft YaHei", 11, "bold"),
            bg='#bdbdbd',
            fg='white',
            activebackground='#9e9e9e',
            activeforeground='white',
            relief=tk.FLAT,
            padx=25,
            pady=12,
            cursor='hand2',
            borderwidth=0,
            highlightthickness=0,
            state=tk.DISABLED
        )
        self.btn_stop.pack(side=tk.LEFT, padx=(0, 12))
        self.btn_stop.bind('<Enter>', lambda e: self.btn_stop.config(bg='#9e9e9e') if self.btn_stop['state'] == tk.NORMAL else None)
        self.btn_stop.bind('<Leave>', lambda e: self.btn_stop.config(bg='#f44336') if self.btn_stop['state'] == tk.NORMAL else None)

        self.btn_export = tk.Button(
            button_container,
            text="💾  导出SRT",
            command=self.export_srt,
            font=("Microsoft YaHei", 11, "bold"),
            bg='#2196f3',
            fg='white',
            activebackground='#1976d2',
            activeforeground='white',
            relief=tk.FLAT,
            padx=25,
            pady=12,
            cursor='hand2',
            borderwidth=0,
            highlightthickness=0
        )
        self.btn_export.pack(side=tk.LEFT)
        self.btn_export.bind('<Enter>', lambda e: self.btn_export.config(bg='#1976d2'))
        self.btn_export.bind('<Leave>', lambda e: self.btn_export.config(bg='#2196f3'))

        # 统计信息区域
        stats_container = tk.Frame(control_frame, bg='#ffffff')
        stats_container.pack(side=tk.RIGHT)

        self.stats_label = tk.Label(
            stats_container,
            text="📊 字幕: 0 条  |  ⏱️ 时长: 00:00:00",
            font=("Microsoft YaHei", 11),
            bg='#ffffff',
            fg='#616161'
        )
        self.stats_label.pack()

        # === 文本框区域容器（使用Grid布局实现真正的响应式）===
        textbox_container = tk.Frame(main_container, bg='#f5f5f5')
        textbox_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))

        # 配置Grid权重，使两个文本框各占50%高度
        textbox_container.grid_rowconfigure(0, weight=1)  # 原文框
        textbox_container.grid_rowconfigure(1, weight=1)  # 翻译框
        textbox_container.grid_columnconfigure(0, weight=1)  # 宽度自适应

        # === 原文显示区域（现代卡片样式 - 响应式）===
        original_card = tk.Frame(textbox_container, bg='#ffffff', highlightbackground='#e0e0e0', highlightthickness=1)
        original_card.grid(row=0, column=0, sticky='nsew', pady=(0, 15))

        # 标题栏
        original_header = tk.Frame(original_card, bg='#ffffff')
        original_header.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(
            original_header,
            text="📝 原文字幕",
            font=("Microsoft YaHei", 12, "bold"),
            bg='#ffffff',
            fg='#1976d2'
        ).pack(side=tk.LEFT)

        # 文本框容器（响应式填充剩余空间）
        original_text_container = tk.Frame(original_card, bg='#ffffff')
        original_text_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        # 原文文本框（响应式）
        self.original_text = tk.Text(
            original_text_container,
            wrap=tk.WORD,
            font=("Consolas", 11),
            bg='#fafafa',
            fg='#212121',
            insertbackground='#1976d2',
            selectbackground='#bbdefb',
            selectforeground='#212121',
            relief=tk.FLAT,
            padx=15,
            pady=15,
            borderwidth=0,
            highlightthickness=0
        )
        self.original_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        original_scroll = ttk.Scrollbar(
            original_text_container,
            command=self.original_text.yview
        )
        original_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        self.original_text.config(yscrollcommand=original_scroll.set)

        # === 翻译显示区域（现代卡片样式 - 响应式）===
        translated_card = tk.Frame(textbox_container, bg='#ffffff', highlightbackground='#e0e0e0', highlightthickness=1)
        translated_card.grid(row=1, column=0, sticky='nsew')

        # 标题栏
        translated_header = tk.Frame(translated_card, bg='#ffffff')
        translated_header.pack(fill=tk.X, padx=20, pady=(15, 10))

        tk.Label(
            translated_header,
            text="🌍 翻译字幕",
            font=("Microsoft YaHei", 12, "bold"),
            bg='#ffffff',
            fg='#1976d2'
        ).pack(side=tk.LEFT)

        # 文本框容器（响应式填充剩余空间）
        translated_text_container = tk.Frame(translated_card, bg='#ffffff')
        translated_text_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 15))

        # 翻译文本框（响应式）
        self.translated_text = tk.Text(
            translated_text_container,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 11),
            bg='#fafafa',
            fg='#212121',
            insertbackground='#1976d2',
            selectbackground='#bbdefb',
            selectforeground='#212121',
            relief=tk.FLAT,
            padx=15,
            pady=15,
            borderwidth=0,
            highlightthickness=0
        )
        self.translated_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        translated_scroll = ttk.Scrollbar(
            translated_text_container,
            command=self.translated_text.yview
        )
        translated_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))
        self.translated_text.config(yscrollcommand=translated_scroll.set)

        # === 底部状态栏（现代化样式）===
        status_bar = tk.Frame(main_container, bg='#424242', height=40)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)

        self.status_bar_label = tk.Label(
            status_bar,
            text="💡 提示：选择语言后点击'开始捕获'，勾选'显示桌面字幕'可启用置顶字幕窗口",
            font=("Microsoft YaHei", 10),
            bg='#424242',
            fg='#e0e0e0',
            anchor=tk.W
        )
        self.status_bar_label.pack(side=tk.LEFT, padx=20, pady=10)

    def on_mode_change(self):
        """处理转录模式切换"""
        mode = self.transcription_mode_var.get()

        if mode == "local":
            # 启用本地模型大小选择
            self.model_size_combo.config(state="readonly")

            # 更新提示信息
            model_size = self.model_size_var.get()
            model_info = {
                "tiny": "39M参数, 速度最快, 精度较低, 需要~1GB显存",
                "base": "74M参数, 速度快, 精度适中, 需要~1GB显存 (推荐)",
                "small": "244M参数, 速度中等, 精度良好, 需要~2GB显存",
                "medium": "769M参数, 速度较慢, 精度很好, 需要~5GB显存",
                "large-v2": "1550M参数, 速度最慢, 精度最佳, 需要~10GB显存"
            }
            info_text = f"💡 本地模式: 离线运行, 免费使用\n   模型: {model_size} ({model_info.get(model_size, '未知')})"
            self.mode_info_label.config(text=info_text)

        else:  # api
            # 禁用本地模型大小选择
            self.model_size_combo.config(state=tk.DISABLED)

            # 更新提示信息
            self.mode_info_label.config(
                text="💡 API模式: 需要OpenAI API Key，在线调用，按量付费"
            )

    def start_capture(self):
        """开始捕获音频 (支持VAD配置 + 语言选择 + 本地/API模式)"""
        # 1. 获取转录模式和模型大小
        transcription_mode = self.transcription_mode_var.get()
        local_model_size = self.model_size_var.get()

        print(f"\n{'='*60}")
        print(f"[INFO] 启动转录模式: {transcription_mode.upper()}")
        if transcription_mode == "local":
            print(f"[INFO] 本地模型大小: {local_model_size}")
        print(f"{'='*60}\n")

        # 2. 读取API Keys (根据模式判断需要哪些Key)
        openai_key = os.getenv('OPENAI_API_KEY')
        deepl_key = os.getenv('DEEPL_API_KEY')

        # API模式需要 OpenAI Key
        if transcription_mode == "api" and not openai_key:
            messagebox.showerror(
                "配置错误",
                "API模式需要配置 OpenAI API Key\n\n请在 .env 文件中添加:\nOPENAI_API_KEY=your_key_here"
            )
            print("[ERROR] API模式需要配置 OPENAI_API_KEY")
            return

        # 两种模式都需要 DeepL Key (用于翻译)
        if not deepl_key:
            messagebox.showerror(
                "配置错误",
                "需要配置 DeepL API Key 用于翻译\n\n请在 .env 文件中添加:\nDEEPL_API_KEY=your_key_here"
            )
            print("[ERROR] 请在.env文件中配置 DEEPL_API_KEY")
            return

        # 3. 获取用户选择的语言
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

        # 5. 启动音频捕获线程 (支持VAD + 音频播放)
        # 音频播放默认启用，解决VB-CABLE无声问题
        enable_playback = parse_bool_config(os.getenv('ENABLE_PLAYBACK', 'true'), default=True)

        self.audio_thread = AudioCaptureThread(
            self.audio_queue,
            self.stop_event,
            enable_vad=vad_enabled,
            enable_playback=enable_playback  # 解决VB-CABLE无声问题
        )
        self.audio_thread.daemon = True
        self.audio_thread.start()

        # 6. 启动转录翻译线程 (支持本地/API模式)
        try:
            self.transcription_thread = TranscriptionThread(
                self.audio_queue,
                self.stop_event,
                self.on_subtitle_ready,
                openai_key,
                deepl_key,
                source_lang=source_lang_code,  # ← 传递用户选择的源语言
                target_lang=target_lang_code,  # ← 传递用户选择的目标语言
                audio_thread=self.audio_thread,  # ← 传递引用用于VAD检查
                mode=transcription_mode,  # ← 转录模式 (local/api)
                local_model_size=local_model_size  # ← 本地模型大小
            )
            self.transcription_thread.daemon = True
            self.transcription_thread.start()
        except Exception as e:
            messagebox.showerror(
                "启动失败",
                f"转录线程启动失败:\n{str(e)}\n\n请检查配置和依赖是否正确安装"
            )
            print(f"[ERROR] 转录线程启动失败: {e}")
            self.stop_event.set()
            return

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
        self.btn_start.config(state=tk.DISABLED, bg='#bdbdbd')
        self.btn_stop.config(state=tk.NORMAL, bg='#f44336')

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
        self.btn_start.config(state=tk.NORMAL, bg='#4caf50')
        self.btn_stop.config(state=tk.DISABLED, bg='#bdbdbd')

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
        更新状态指示灯（Material Design风格）

        参数:
            status (str): 状态 - "running", "stopped"
        """
        if status == "running":
            self.status_canvas.itemconfig(self.status_indicator, fill='#4caf50', outline='#2e7d32', width=2)
            self.status_label.config(text="运行中")
            self.status_bar_label.config(text="🎬 正在实时捕获音频并生成双语字幕...")
        elif status == "stopped":
            self.status_canvas.itemconfig(self.status_indicator, fill='#bdbdbd', outline='#757575', width=2)
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
