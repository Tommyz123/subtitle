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
from ui_components import (
    TechColors, GlowButton, StatusIndicator, StatsCard, 
    ModernFrame, ModernLabel, ModernTitledFrame
)
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
        self.root.geometry("1100x800")
        self.root.minsize(900, 700)

        # 允许窗口缩放
        self.root.resizable(True, True)

        # 设置窗口背景色
        self.root.configure(bg=TechColors.BG_PRIMARY)

        # 设置样式
        style = ttk.Style()
        style.theme_use('clam')
        
        # 配置Combobox样式
        style.configure('Modern.TCombobox', 
                       fieldbackground=TechColors.BG_CARD,
                       background=TechColors.BG_SECONDARY,
                       foreground=TechColors.TEXT_PRIMARY,
                       arrowcolor=TechColors.ACCENT_PRIMARY,
                       borderwidth=1,
                       relief='flat')
        style.map('Modern.TCombobox', fieldbackground=[('readonly', TechColors.BG_CARD)])

        # 配置Checkbutton样式
        style.configure('Modern.TCheckbutton', 
                       background=TechColors.BG_CARD,
                       foreground=TechColors.TEXT_PRIMARY,
                       font=TechColors.FONT_BODY)
        style.map('Modern.TCheckbutton', 
                 background=[('active', TechColors.BG_CARD)],
                 indicatorcolor=[('selected', TechColors.ACCENT_PRIMARY)])

        # === 主布局 (Grid) ===
        # 0: Header (Fixed height)
        # 1: Content (Expandable)
        # 2: Footer (Fixed height)
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)

        # === 1. 顶部标题栏 ===
        header_frame = ModernFrame(self.root, height=70)
        header_frame.grid(row=0, column=0, sticky='ew')
        header_frame.pack_propagate(False)

        # 标题
        title_box = tk.Frame(header_frame, bg=TechColors.BG_PRIMARY)
        title_box.pack(side=tk.LEFT, padx=30, pady=15)
        
        ModernLabel(title_box, text="🎬", style='h1').pack(side=tk.LEFT, padx=(0, 10))
        ModernLabel(title_box, text="实时语音翻译字幕系统", style='h1').pack(side=tk.LEFT)

        # 状态指示
        status_box = tk.Frame(header_frame, bg=TechColors.BG_PRIMARY)
        status_box.pack(side=tk.RIGHT, padx=30)

        self.status_canvas = tk.Canvas(status_box, width=16, height=16, bg=TechColors.BG_PRIMARY, highlightthickness=0)
        self.status_canvas.pack(side=tk.LEFT, padx=(0, 10))
        self.status_indicator_obj = StatusIndicator(self.status_canvas, 8, 8, radius=6)

        self.status_label = ModernLabel(status_box, text="未运行", style='body_bold', color=TechColors.TEXT_TERTIARY)
        self.status_label.pack(side=tk.LEFT)

        # 分割线
        tk.Frame(self.root, bg=TechColors.BORDER_PRIMARY, height=1).grid(row=0, column=0, sticky='sew')

        # === 2. 主内容区域 ===
        content_container = ModernFrame(self.root)
        content_container.grid(row=1, column=0, sticky='nsew', padx=20, pady=20)
        
        # 左右分栏 (Left: Settings/Controls, Right: Subtitles)
        content_container.grid_columnconfigure(1, weight=3) # 右侧字幕区占更多空间
        content_container.grid_columnconfigure(0, weight=1, minsize=320) # 左侧设置区固定最小宽度
        content_container.grid_rowconfigure(0, weight=1)

        # --- 左侧栏: 设置与控制 ---
        left_panel = ModernFrame(content_container)
        left_panel.grid(row=0, column=0, sticky='nsew', padx=(0, 20))
        
        # 语言设置
        lang_group = ModernTitledFrame(left_panel, "语言设置", "🌍")
        lang_group.pack(fill=tk.X, pady=(0, 15))
        
        # 源语言
        ModernLabel(lang_group.content, text="源语言 (说话):", style='small').pack(anchor=tk.W, pady=(0, 5))
        self.source_lang_var = tk.StringVar(value="中文")
        self.source_lang_combo = ttk.Combobox(
            lang_group.content, textvariable=self.source_lang_var, 
            values=list(WHISPER_LANGUAGES.keys()), state="readonly", style='Modern.TCombobox'
        )
        self.source_lang_combo.pack(fill=tk.X, pady=(0, 15))
        
        # 目标语言
        ModernLabel(lang_group.content, text="目标语言 (翻译):", style='small').pack(anchor=tk.W, pady=(0, 5))
        self.target_lang_var = tk.StringVar(value="英语（美式）")
        self.target_lang_combo = ttk.Combobox(
            lang_group.content, textvariable=self.target_lang_var, 
            values=list(DEEPL_LANGUAGES.keys()), state="readonly", style='Modern.TCombobox'
        )
        self.target_lang_combo.pack(fill=tk.X)

        # 模式设置
        mode_group = ModernTitledFrame(left_panel, "转录模式", "🤖")
        mode_group.pack(fill=tk.X, pady=(0, 15))
        
        self.transcription_mode_var = tk.StringVar(value="api")
        
        # 模式单选
        radio_frame = tk.Frame(mode_group.content, bg=TechColors.BG_CARD)
        radio_frame.pack(fill=tk.X, pady=(0, 10))
        
        tk.Radiobutton(
            radio_frame, text="API (在线)", variable=self.transcription_mode_var, value="api",
            bg=TechColors.BG_CARD, fg=TechColors.TEXT_PRIMARY, selectcolor=TechColors.BG_CARD,
            activebackground=TechColors.BG_CARD, font=TechColors.FONT_BODY, command=self.on_mode_change
        ).pack(side=tk.LEFT, expand=True)
        
        tk.Radiobutton(
            radio_frame, text="本地 (离线)", variable=self.transcription_mode_var, value="local",
            bg=TechColors.BG_CARD, fg=TechColors.TEXT_PRIMARY, selectcolor=TechColors.BG_CARD,
            activebackground=TechColors.BG_CARD, font=TechColors.FONT_BODY, command=self.on_mode_change
        ).pack(side=tk.LEFT, expand=True)

        # 本地模型选项
        self.local_options_frame = tk.Frame(mode_group.content, bg=TechColors.BG_CARD)
        self.local_options_frame.pack(fill=tk.X)
        
        ModernLabel(self.local_options_frame, text="模型大小:", style='small').pack(anchor=tk.W, pady=(5, 2))
        self.model_size_var = tk.StringVar(value="base")
        self.model_size_combo = ttk.Combobox(
            self.local_options_frame, textvariable=self.model_size_var,
            values=["tiny", "base", "small", "medium", "large-v2"], state="readonly", style='Modern.TCombobox'
        )
        self.model_size_combo.pack(fill=tk.X, pady=(0, 10))
        
        ModernLabel(self.local_options_frame, text="速度模式:", style='small').pack(anchor=tk.W, pady=(0, 2))
        self.speed_mode_var = tk.StringVar(value="fast")
        self.speed_mode_combo = ttk.Combobox(
            self.local_options_frame, textvariable=self.speed_mode_var,
            values=["fast", "balanced", "quality"], state="readonly", style='Modern.TCombobox'
        )
        self.speed_mode_combo.pack(fill=tk.X, pady=(0, 10))

        self.enable_streaming_var = tk.BooleanVar(value=True)  # P2优化: 默认启用流式处理
        self.enable_streaming_check = ttk.Checkbutton(
            self.local_options_frame, text="流式处理 (低延迟)", variable=self.enable_streaming_var, style='Modern.TCheckbutton'
        )
        self.enable_streaming_check.pack(anchor=tk.W)

        # 桌面字幕开关
        self.desktop_subtitle_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            left_panel, text="📺 显示桌面悬浮字幕", variable=self.desktop_subtitle_var, style='Modern.TCheckbutton'
        ).pack(anchor=tk.W, pady=(0, 15))

        # 控制按钮
        control_frame = tk.Frame(left_panel, bg=TechColors.BG_PRIMARY)
        control_frame.pack(fill=tk.X, pady=(10, 20))
        
        self.btn_start = GlowButton(control_frame, text="▶ 开始捕获", style='success', command=self.start_capture)
        self.btn_start.pack(fill=tk.X, pady=(0, 10))
        
        self.btn_stop = GlowButton(control_frame, text="⏹ 停止", style='error', command=self.stop_capture, state=tk.DISABLED)
        self.btn_stop.pack(fill=tk.X, pady=(0, 10))
        
        self.btn_export = GlowButton(control_frame, text="💾 导出SRT", style='primary', command=self.export_srt)
        self.btn_export.pack(fill=tk.X)

        # 统计卡片 (放在左侧栏底部)
        self.stats_frame = tk.Frame(left_panel, bg=TechColors.BG_PRIMARY)
        self.stats_frame.pack(fill=tk.X, side=tk.BOTTOM)
        
        self.audio_card = StatsCard(self.stats_frame, "🔊", "音频捕获")
        self.audio_card.pack(fill=tk.X, pady=(0, 10))
        
        self.queue_card = StatsCard(self.stats_frame, "📊", "队列积压")
        self.queue_card.pack(fill=tk.X)


        # --- 右侧栏: 字幕显示 ---
        right_panel = ModernFrame(content_container)
        right_panel.grid(row=0, column=1, sticky='nsew')
        right_panel.grid_rowconfigure(0, weight=1)
        right_panel.grid_rowconfigure(1, weight=1)
        right_panel.grid_columnconfigure(0, weight=1)

        # 原文区域
        original_group = ModernTitledFrame(right_panel, "识别原文", "📝")
        original_group.grid(row=0, column=0, sticky='nsew', pady=(0, 15))
        
        self.original_text = tk.Text(
            original_group.content, wrap=tk.WORD, font=("Consolas", 12),
            bg=TechColors.BG_PRIMARY, fg=TechColors.TEXT_PRIMARY,
            insertbackground=TechColors.ACCENT_PRIMARY, relief=tk.FLAT,
            padx=15, pady=15, spacing1=5, spacing3=5
        )
        self.original_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        orig_scroll = ttk.Scrollbar(original_group.content, command=self.original_text.yview)
        orig_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.original_text.config(yscrollcommand=orig_scroll.set)

        # 译文区域
        translated_group = ModernTitledFrame(right_panel, "翻译结果", "🌍")
        translated_group.grid(row=1, column=0, sticky='nsew')
        
        self.translated_text = tk.Text(
            translated_group.content, wrap=tk.WORD, font=("Microsoft YaHei", 12),
            bg=TechColors.BG_PRIMARY, fg=TechColors.TEXT_PRIMARY,
            insertbackground=TechColors.ACCENT_PRIMARY, relief=tk.FLAT,
            padx=15, pady=15, spacing1=5, spacing3=5
        )
        self.translated_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        trans_scroll = ttk.Scrollbar(translated_group.content, command=self.translated_text.yview)
        trans_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.translated_text.config(yscrollcommand=trans_scroll.set)

        # === 3. 底部状态栏 ===
        footer_frame = tk.Frame(self.root, bg=TechColors.BG_SECONDARY, height=30)
        footer_frame.grid(row=2, column=0, sticky='ew')
        footer_frame.pack_propagate(False)
        
        self.status_bar_label = ModernLabel(
            footer_frame, 
            text="💡 提示：选择语言后点击'开始捕获'，勾选'显示桌面字幕'可启用置顶字幕窗口", 
            style='small'
        )
        self.status_bar_label.pack(side=tk.LEFT, padx=20)
        
        self.mode_info_label = ModernLabel(
            footer_frame, text="", style='small', color=TechColors.TEXT_TERTIARY
        )
        self.mode_info_label.pack(side=tk.RIGHT, padx=20)

        # 初始化状态
        self.on_mode_change()



    def on_mode_change(self):
        """处理转录模式切换"""
        mode = self.transcription_mode_var.get()

        if mode == "local":
            # 启用本地模型大小选择
            self.model_size_combo.config(state="readonly")
            # ✅ 启用速度模式选择
            self.speed_mode_combo.config(state="readonly")
            # ✅ 阶段2: 启用流式处理开关
            self.enable_streaming_check.config(state="normal")

            # 更新提示信息
            model_size = self.model_size_var.get()
            speed_mode = self.speed_mode_var.get()
            enable_streaming = self.enable_streaming_var.get()

            model_info = {
                "tiny": "39M参数, 速度最快, 精度较低, 需要~1GB显存",
                "base": "74M参数, 速度快, 精度适中, 需要~1GB显存 (推荐)",
                "small": "244M参数, 速度中等, 精度良好, 需要~2GB显存",
                "medium": "769M参数, 速度较慢, 精度很好, 需要~5GB显存",
                "large-v2": "1550M参数, 速度最慢, 精度最佳, 需要~10GB显存"
            }
            speed_info = {
                "fast": "极速 (延迟-40%, 质量-10%)",
                "balanced": "平衡 (延迟-20%, 推荐)",
                "quality": "质量 (延迟+20%, 精度最佳)"
            }

            # ✅ 阶段2: 添加流式处理状态到提示信息
            streaming_status = "启用 (增量输出, 延迟-50%)" if enable_streaming else "禁用 (批量处理)"
            info_text = f"💡 本地模式: 离线运行 | 模型: {model_size} | 速度: {speed_mode} | 流式: {streaming_status}"
            self.mode_info_label.config(text=info_text, fg=TechColors.TEXT_SECONDARY)

        else:  # api
            # 禁用本地模型大小选择
            self.model_size_combo.config(state=tk.DISABLED)
            # ✅ 禁用速度模式选择
            self.speed_mode_combo.config(state=tk.DISABLED)
            # ✅ 阶段2: 禁用流式处理开关
            self.enable_streaming_check.config(state=tk.DISABLED)

            # 更新提示信息
            self.mode_info_label.config(
                text="💡 API模式: 需要OpenAI API Key，在线调用，按量付费",
                fg=TechColors.TEXT_SECONDARY
            )

    def start_capture(self):
        """开始捕获音频 (支持VAD配置 + 语言选择 + 本地/API模式)"""
        # 1. 获取转录模式、模型大小、速度模式和流式处理开关
        transcription_mode = self.transcription_mode_var.get()
        local_model_size = self.model_size_var.get()
        speed_mode = self.speed_mode_var.get()  # ✅ 获取速度模式
        enable_streaming = self.enable_streaming_var.get()  # ✅ 阶段2: 获取流式模式

        print(f"\n{'='*60}")
        print(f"[INFO] 启动转录模式: {transcription_mode.upper()}")
        if transcription_mode == "local":
            print(f"[INFO] 本地模型大小: {local_model_size}")
            print(f"[INFO] 速度模式: {speed_mode}")  # ✅ 显示速度模式
            print(f"[INFO] 流式处理: {'启用' if enable_streaming else '禁用'}")  # ✅ 阶段2: 显示流式模式
        print(f"{ '='*60}\n")

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

        # DeepL Key检查 (本地模式+本地翻译时可选)
        use_local_translation_raw = os.getenv('USE_LOCAL_TRANSLATION', 'true')
        use_local_translation = parse_bool_config(use_local_translation_raw, default=True)

        # 只有在非本地翻译时才需要DeepL Key
        need_deepl = transcription_mode == "api" or not use_local_translation
        if need_deepl and not deepl_key:
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

        # 显示翻译方式信息
        if transcription_mode == "local" and use_local_translation:
            print(f"[INFO] 本地翻译: 启用 (NLLB模型, 速度 < 100ms)")
        elif transcription_mode == "local":
            print(f"[INFO] 本地翻译: 禁用 (使用 DeepL API)")
        else:
            print(f"[INFO] 翻译方式: DeepL API")

        # 3. 清除停止信号
        self.stop_event.clear()

        # 4. 清空字幕存储（使用锁保护）
        with self.storage_lock:
            self.subtitle_storage.clear()

        # 清空文本框
        self.original_text.delete(1.0, tk.END)
        self.translated_text.delete(1.0, tk.END)

        # 5. 启动音频捕获线程 (支持VAD + 音频播放 + 智能分段)
        # 音频播放默认禁用（避免与Windows"侦听此设备"冲突导致回声）
        # 如需使用程序内播放，请在.env中设置 ENABLE_PLAYBACK=true 并关闭Windows侦听
        enable_playback = parse_bool_config(os.getenv('ENABLE_PLAYBACK', 'false'), default=False)

        # 智能分段配置（默认启用，VAD检测语音结束后立即处理）
        enable_smart_segmentation = parse_bool_config(os.getenv('ENABLE_SMART_SEGMENTATION', 'true'), default=True)

        # 本地模式自动启用智能分段（如果环境变量未明确禁用）
        if transcription_mode == "local" and os.getenv('ENABLE_SMART_SEGMENTATION') is None:
            enable_smart_segmentation = True
            print(f"[INFO] 本地模式自动启用智能分段（根据说话节奏动态切分）")

        self.audio_thread = AudioCaptureThread(
            self.audio_queue,
            self.stop_event,
            enable_vad=vad_enabled,
            enable_playback=enable_playback,  # 解决VB-CABLE无声问题
            enable_smart_segmentation=enable_smart_segmentation  # 智能分段
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
                local_model_size=local_model_size,  # ← 本地模型大小
                speed_mode=speed_mode,  # ✅ 速度模式 (fast/balanced/quality)
                use_local_translation=use_local_translation,  # ← 是否使用本地翻译
                enable_streaming=enable_streaming  # ✅ 阶段2: 流式处理开关
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
        self.btn_start.config(state=tk.DISABLED)
        self.btn_start.config(bg=TechColors.TEXT_DISABLED)
        self.btn_stop.config(state=tk.NORMAL)
        self.btn_stop.config(bg=TechColors.ACCENT_ERROR)

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
        self.btn_start.config(bg=TechColors.ACCENT_SUCCESS)
        self.btn_stop.config(state=tk.DISABLED)
        self.btn_stop.config(bg=TechColors.TEXT_DISABLED)

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
            filetypes=[("SRT files", "*.srt"), ("All files", "*.* אמיתי")]
        )

        if filepath:
            # P9优化: 锁粒度优化 - 锁内只复制数据（微秒级），文件IO在锁外（毫秒级）
            # 原来：整个导出操作在锁内 → 阻塞新字幕写入
            # 优化后：锁持有时间减少99%
            with self.storage_lock:
                subtitles_copy = self.subtitle_storage.get_subtitles_copy()

            # 文件IO在锁外执行（不阻塞其他线程）
            self._write_srt_file(filepath, subtitles_copy)
            print(f"[INFO] 字幕已导出到: {filepath}")
            messagebox.showinfo("导出成功", f"字幕已成功导出到:\n{filepath}")

    def _write_srt_file(self, filepath, subtitles):
        """
        P9优化: 写入SRT文件（在锁外执行）

        参数:
            filepath (str): 导出文件路径
            subtitles (list): 字幕数据副本
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(subtitles, 1):
                # 起始时间
                start = self._format_srt_time(sub['timestamp'])

                # 时长根据下一条字幕时间戳计算
                if i < len(subtitles):
                    duration = subtitles[i]['timestamp'] - sub['timestamp']
                else:
                    duration = 5.0  # 最后一条字幕默认5秒

                end = self._format_srt_time(sub['timestamp'] + duration)

                # 写入SRT格式
                f.write(f"{i}\n")
                f.write(f"{start} --> {end}\n")
                f.write(f"{sub['original']}\n")
                f.write(f"{sub['translation']}\n")
                f.write("\n")

        print(f"[INFO] 已导出 {len(subtitles)} 条字幕")

    def _format_srt_time(self, seconds):
        """格式化为SRT时间格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

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
        """
        更新状态监控区数据
        P5优化: 仅在值变化时更新，降低更新频率到2秒
        """
        if not self.stop_event.is_set():
            # P5优化: 初始化上次值缓存（如果不存在）
            if not hasattr(self, '_last_audio_status'):
                self._last_audio_status = None
                self._last_queue_size = None

            # 1. 更新音频捕获状态（仅在变化时更新）
            audio_status = "✓ 正常运行" if (self.audio_thread and self.audio_thread.is_alive()) else "✗ 未运行"
            if audio_status != self._last_audio_status:
                self.audio_card.set_value(audio_status)
                self._last_audio_status = audio_status

            # 2. 更新队列状态（仅在变化时更新）
            queue_size = self.audio_queue.qsize()
            if queue_size != self._last_queue_size:
                self.queue_card.set_value(f"{queue_size} 块")
                queue_progress = min(queue_size / 20.0, 1.0)
                self.queue_card.set_progress(queue_progress, f"{queue_size}")
                self._last_queue_size = queue_size

            # P5优化: 每2秒更新一次（从1秒降低）
            self.root.after(2000, self._update_monitor_stats)


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
