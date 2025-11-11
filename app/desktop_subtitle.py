"""
桌面字幕窗口模块 - 优化版

职责:
- 创建独立的置顶字幕窗口
- 支持拖动和调整位置
- 半透明背景
- 实时更新字幕显示
- 文字描边效果，提高可读性
- 可调节字体大小和透明度
"""

import tkinter as tk
from tkinter import ttk, font


class DesktopSubtitleWindow:
    """桌面字幕窗口 - 置顶、半透明、可拖动"""

    def __init__(self, parent):
        """
        初始化桌面字幕窗口

        参数:
            parent: 父窗口（主窗口）
        """
        self.parent = parent
        self.window = tk.Toplevel(parent)

        # 窗口配置
        self.window.title("🎬 桌面字幕")
        self.window.geometry("900x250+100+500")  # 默认位置在屏幕下方，增加高度以适应更大字体

        # 置顶显示
        self.window.attributes('-topmost', True)

        # 半透明背景 (0.0-1.0, 0.85表示85%不透明)
        self.alpha = 0.85
        self.window.attributes('-alpha', self.alpha)

        # 窗口样式 - 保留标题栏以便拖动
        # self.window.overrideredirect(True)  # 如果需要无边框可以启用

        # 使用渐变效果的深色背景
        self.window.configure(bg='#1a1a1a')

        # 字体大小（参考专业字幕标准：24-32号）
        self.font_size_translation = 26  # 翻译字体（主要内容，更大）
        self.font_size = 22  # 原文字体（次要内容）

        # 创建内容区域
        self._create_widgets()

        # 拖动支持变量
        self._drag_start_x = 0
        self._drag_start_y = 0

        # 绑定拖动事件
        self._bind_drag_events()

        # 存储最新字幕
        self.current_original = ""
        self.current_translation = ""

        # 绑定快捷键
        self._bind_shortcuts()

    def _create_widgets(self):
        """创建窗口内部组件"""
        # 主容器（带圆角效果的内边距）
        main_frame = tk.Frame(self.window, bg='#1a1a1a')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # 控制栏（小型按钮区域）
        control_frame = tk.Frame(main_frame, bg='#1a1a1a')
        control_frame.pack(fill=tk.X, pady=(0, 10))

        # 字体大小控制
        tk.Label(
            control_frame,
            text="字号:",
            font=("Microsoft YaHei", 9),
            fg="#999999",
            bg='#1a1a1a'
        ).pack(side=tk.LEFT, padx=5)

        btn_font_smaller = tk.Button(
            control_frame,
            text="A-",
            font=("Arial", 9, "bold"),
            bg='#333333',
            fg='white',
            activebackground='#444444',
            activeforeground='white',
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor='hand2',
            command=self._decrease_font_size
        )
        btn_font_smaller.pack(side=tk.LEFT, padx=2)

        btn_font_larger = tk.Button(
            control_frame,
            text="A+",
            font=("Arial", 9, "bold"),
            bg='#333333',
            fg='white',
            activebackground='#444444',
            activeforeground='white',
            relief=tk.FLAT,
            padx=8,
            pady=2,
            cursor='hand2',
            command=self._increase_font_size
        )
        btn_font_larger.pack(side=tk.LEFT, padx=2)

        # 透明度控制
        tk.Label(
            control_frame,
            text="透明度:",
            font=("Microsoft YaHei", 9),
            fg="#999999",
            bg='#1a1a1a'
        ).pack(side=tk.LEFT, padx=(20, 5))

        self.alpha_scale = tk.Scale(
            control_frame,
            from_=0.3,
            to=1.0,
            resolution=0.05,
            orient=tk.HORIZONTAL,
            length=120,
            bg='#333333',
            fg='white',
            troughcolor='#555555',
            activebackground='#666666',
            highlightthickness=0,
            showvalue=False,
            command=self._update_alpha
        )
        self.alpha_scale.set(self.alpha)
        self.alpha_scale.pack(side=tk.LEFT, padx=5)

        # 提示文本
        tk.Label(
            control_frame,
            text="[快捷键: Ctrl+↑/↓调整字号, Ctrl+鼠标滚轮调透明度]",
            font=("Microsoft YaHei", 8),
            fg="#666666",
            bg='#1a1a1a'
        ).pack(side=tk.RIGHT, padx=5)

        # 字幕显示区域
        subtitle_frame = tk.Frame(main_frame, bg='#1a1a1a')
        subtitle_frame.pack(fill=tk.BOTH, expand=True)

        # 翻译标签（带描边效果）- 放在上方，主要内容
        # 使用Canvas绘制文字描边效果
        self.translation_canvas = tk.Canvas(
            subtitle_frame,
            bg='#1a1a1a',
            highlightthickness=0,
            height=90  # 增大高度以适应更大字体
        )
        self.translation_canvas.pack(fill=tk.X, pady=(0, 5))

        # 分隔线（渐变效果）
        separator = tk.Frame(subtitle_frame, height=2, bg='#444444')
        separator.pack(fill=tk.X, pady=8)

        # 原文标签（带描边效果）- 放在下方，次要内容
        self.original_canvas = tk.Canvas(
            subtitle_frame,
            bg='#1a1a1a',
            highlightthickness=0,
            height=80  # 增大高度以适应更大字体
        )
        self.original_canvas.pack(fill=tk.X, pady=(5, 0))

    def _bind_drag_events(self):
        """绑定窗口拖动事件"""
        # 绑定到标题栏和整个窗口
        self.window.bind('<Button-1>', self._on_drag_start)
        self.window.bind('<B1-Motion>', self._on_drag_motion)

        # 也绑定到Canvas上，这样点击Canvas也能拖动
        self.original_canvas.bind('<Button-1>', self._on_drag_start)
        self.original_canvas.bind('<B1-Motion>', self._on_drag_motion)
        self.translation_canvas.bind('<Button-1>', self._on_drag_start)
        self.translation_canvas.bind('<B1-Motion>', self._on_drag_motion)

    def _on_drag_start(self, event):
        """
        开始拖动

        参数:
            event: 鼠标事件
        """
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag_motion(self, event):
        """
        拖动过程中

        参数:
            event: 鼠标事件
        """
        # 计算窗口新位置
        x = self.window.winfo_x() + event.x - self._drag_start_x
        y = self.window.winfo_y() + event.y - self._drag_start_y

        # 移动窗口
        self.window.geometry(f"+{x}+{y}")

    def _draw_text_with_outline(self, canvas, text, font_obj, text_color, outline_color):
        """
        在Canvas上绘制带描边的文字

        参数:
            canvas: Canvas对象
            text: 文本内容
            font_obj: 字体对象
            text_color: 文字颜色
            outline_color: 描边颜色
        """
        # 清空canvas
        canvas.delete('all')

        # 获取canvas尺寸
        canvas.update_idletasks()
        width = canvas.winfo_width()
        height = canvas.winfo_height()

        # 中心位置
        x, y = width // 2, height // 2

        # 绘制描边（在四个方向绘制黑色文字）
        offsets = [(-2, -2), (-2, 2), (2, -2), (2, 2), (-2, 0), (2, 0), (0, -2), (0, 2)]
        for dx, dy in offsets:
            canvas.create_text(
                x + dx, y + dy,
                text=text,
                font=font_obj,
                fill=outline_color,
                width=width - 40,
                justify=tk.CENTER
            )

        # 绘制主文字
        canvas.create_text(
            x, y,
            text=text,
            font=font_obj,
            fill=text_color,
            width=width - 40,
            justify=tk.CENTER
        )

    def update_subtitle(self, original, translation):
        """
        更新字幕显示（翻译在上，原文在下）

        参数:
            original (str): 原文
            translation (str): 翻译
        """
        self.current_original = original
        self.current_translation = translation

        # 更新显示 (只显示最新一条)，使用描边文字
        try:
            # 创建字体对象（翻译字体更大，因为是主要内容）
            translation_font = font.Font(family="Microsoft YaHei", size=self.font_size_translation, weight="bold")
            original_font = font.Font(family="Arial", size=self.font_size, weight="bold")

            # 绘制翻译（金黄色文字，黑色描边）- 在上方
            self._draw_text_with_outline(
                self.translation_canvas,
                translation,
                translation_font,
                '#FFD700',  # 金黄色文字（主要内容）
                '#000000'   # 黑色描边
            )

            # 绘制原文（白色文字，黑色描边）- 在下方
            self._draw_text_with_outline(
                self.original_canvas,
                original,
                original_font,
                '#FFFFFF',  # 白色文字（次要内容）
                '#000000'   # 黑色描边
            )
        except Exception as e:
            print(f"[ERROR] 更新字幕显示失败: {e}")

    def _increase_font_size(self):
        """增大字体（翻译字体更大）"""
        self.font_size_translation = min(self.font_size_translation + 2, 36)  # 翻译字体最大36
        self.font_size = min(self.font_size + 2, 32)  # 原文字体最大32
        self.update_subtitle(self.current_original, self.current_translation)

    def _decrease_font_size(self):
        """减小字体"""
        self.font_size_translation = max(self.font_size_translation - 2, 18)  # 翻译字体最小18
        self.font_size = max(self.font_size - 2, 14)  # 原文字体最小14
        self.update_subtitle(self.current_original, self.current_translation)

    def _update_alpha(self, value):
        """
        更新窗口透明度

        参数:
            value: 透明度值（0.0-1.0）
        """
        self.alpha = float(value)
        self.window.attributes('-alpha', self.alpha)

    def _bind_shortcuts(self):
        """绑定快捷键"""
        # Ctrl + 上箭头：增大字体
        self.window.bind('<Control-Up>', lambda e: self._increase_font_size())
        # Ctrl + 下箭头：减小字体
        self.window.bind('<Control-Down>', lambda e: self._decrease_font_size())
        # Ctrl + 鼠标滚轮：调整透明度
        self.window.bind('<Control-MouseWheel>', self._on_mouse_wheel_alpha)

    def _on_mouse_wheel_alpha(self, event):
        """
        鼠标滚轮调整透明度

        参数:
            event: 鼠标事件
        """
        delta = 0.05 if event.delta > 0 else -0.05
        new_alpha = max(0.3, min(1.0, self.alpha + delta))
        self.alpha_scale.set(new_alpha)

    def show(self):
        """显示窗口"""
        self.window.deiconify()  # 显示窗口
        self.window.lift()       # 提升到最前面
        print("[INFO] 桌面字幕窗口已显示")

    def hide(self):
        """隐藏窗口"""
        self.window.withdraw()   # 隐藏窗口
        print("[INFO] 桌面字幕窗口已隐藏")

    def destroy(self):
        """销毁窗口"""
        if self.window:
            self.window.destroy()
            self.window = None
            print("[INFO] 桌面字幕窗口已关闭")

    def is_visible(self):
        """
        检查窗口是否可见

        返回:
            bool: 窗口是否可见
        """
        try:
            return self.window.state() == 'normal'
        except:
            return False
