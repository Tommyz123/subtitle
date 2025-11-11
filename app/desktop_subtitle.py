"""
桌面字幕窗口模块 - YouTube风格版

职责:
- 创建独立的置顶字幕窗口
- YouTube风格：极简设计，高对比度，专注于字幕显示
- 半透明黑色背景，白色文字
- 支持拖动和调整位置
- 可通过右键菜单或快捷键调整设置
"""

import tkinter as tk
from tkinter import Menu, font


class DesktopSubtitleWindow:
    """桌面字幕窗口 - YouTube风格：极简、清晰、易读"""

    def __init__(self, parent):
        """
        初始化桌面字幕窗口

        参数:
            parent: 父窗口（主窗口）
        """
        self.parent = parent
        self.window = tk.Toplevel(parent)

        # 窗口配置
        self.window.title("字幕")
        self.window.geometry("900x180+100+600")  # 默认位置在屏幕下方

        # 设置窗口最小尺寸
        self.window.minsize(300, 80)

        # 无边框设计（YouTube风格）
        self.window.overrideredirect(True)

        # 置顶显示
        self.window.attributes('-topmost', True)

        # 半透明背景 (0.0-1.0, 0.92表示92%不透明)
        self.alpha = 0.92
        self.window.attributes('-alpha', self.alpha)

        # 半透明黑色背景（YouTube风格）
        self.bg_color = '#000000'
        self.window.configure(bg=self.bg_color)

        # 字体大小（YouTube标准：24-32px）
        self.font_size_translation = 28  # 翻译字体（主要内容）
        self.font_size_original = 18     # 原文字体（次要内容）

        # 是否显示原文（默认显示）
        self.show_original = True

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

        # 创建右键菜单
        self._create_context_menu()

        # 绑定快捷键
        self._bind_shortcuts()

        # 绑定窗口缩放事件
        self.window.bind('<Configure>', self._on_window_resize)

    def _create_widgets(self):
        """创建窗口内部组件 - YouTube极简风格"""
        # 主容器（无边距，极简设计）
        main_frame = tk.Frame(self.window, bg=self.bg_color)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        # 翻译字幕区域（主要内容，YouTube风格白色文字）
        self.translation_canvas = tk.Canvas(
            main_frame,
            bg=self.bg_color,
            highlightthickness=0
        )
        self.translation_canvas.pack(fill=tk.BOTH, expand=True)

        # 原文字幕区域（次要内容，灰色文字，小字）
        # 不设置固定height，让它根据内容自适应
        self.original_canvas = tk.Canvas(
            main_frame,
            bg=self.bg_color,
            highlightthickness=0
        )
        self.original_canvas.pack(fill=tk.X, pady=(8, 0))

        # 存储原文Canvas的frame引用，用于动态调整高度
        self.original_frame = main_frame

    def _create_context_menu(self):
        """创建右键菜单（隐藏的控制选项）"""
        self.context_menu = Menu(self.window, tearoff=0)

        # 字体大小子菜单
        font_menu = Menu(self.context_menu, tearoff=0)
        font_menu.add_command(label="增大 (Ctrl+↑)", command=self._increase_font_size)
        font_menu.add_command(label="减小 (Ctrl+↓)", command=self._decrease_font_size)
        self.context_menu.add_cascade(label="字体大小", menu=font_menu)

        # 透明度子菜单
        alpha_menu = Menu(self.context_menu, tearoff=0)
        for alpha_val in [1.0, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70]:
            alpha_menu.add_command(
                label=f"{int(alpha_val*100)}%",
                command=lambda a=alpha_val: self._set_alpha(a)
            )
        self.context_menu.add_cascade(label="透明度", menu=alpha_menu)

        # 显示选项
        self.context_menu.add_separator()
        self.context_menu.add_checkbutton(
            label="显示原文",
            command=self._toggle_original,
            variable=tk.BooleanVar(value=True)
        )

        # 窗口控制
        self.context_menu.add_separator()
        self.context_menu.add_command(label="关闭 (ESC)", command=self.hide)

        # 绑定右键菜单
        self.window.bind('<Button-3>', self._show_context_menu)
        self.translation_canvas.bind('<Button-3>', self._show_context_menu)
        self.original_canvas.bind('<Button-3>', self._show_context_menu)

    def _show_context_menu(self, event):
        """显示右键菜单"""
        try:
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

    def _bind_drag_events(self):
        """绑定窗口拖动事件"""
        # 绑定到整个窗口
        self.window.bind('<Button-1>', self._on_drag_start)
        self.window.bind('<B1-Motion>', self._on_drag_motion)

        # 也绑定到Canvas上
        self.translation_canvas.bind('<Button-1>', self._on_drag_start)
        self.translation_canvas.bind('<B1-Motion>', self._on_drag_motion)
        self.original_canvas.bind('<Button-1>', self._on_drag_start)
        self.original_canvas.bind('<B1-Motion>', self._on_drag_motion)

    def _on_drag_start(self, event):
        """开始拖动"""
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def _on_drag_motion(self, event):
        """拖动过程中"""
        x = self.window.winfo_x() + event.x - self._drag_start_x
        y = self.window.winfo_y() + event.y - self._drag_start_y
        self.window.geometry(f"+{x}+{y}")

    def _calculate_text_height(self, canvas, text, font_obj, available_width):
        """
        计算文本在给定宽度下需要的高度

        参数:
            canvas: Canvas对象
            text: 文本内容
            font_obj: 字体对象
            available_width: 可用宽度

        返回:
            int: 所需高度（像素）
        """
        if not text:
            return 0

        # 创建临时文本对象来测量
        temp_id = canvas.create_text(
            0, 0,
            text=text,
            font=font_obj,
            width=available_width,
            justify=tk.CENTER
        )

        # 获取文本边界框
        bbox = canvas.bbox(temp_id)
        canvas.delete(temp_id)

        if bbox:
            # 返回高度，加上一些边距
            return bbox[3] - bbox[1] + 20
        return 30  # 默认最小高度

    def _draw_text_with_outline(self, canvas, text, font_obj, text_color, outline_color):
        """
        在Canvas上绘制带描边的文字（YouTube风格）

        参数:
            canvas: Canvas对象
            text: 文本内容
            font_obj: 字体对象
            text_color: 文字颜色
            outline_color: 描边颜色
        """
        canvas.delete('all')

        if not text:  # 如果没有文本，不绘制
            return

        # 强制更新Canvas尺寸
        canvas.update_idletasks()
        width = canvas.winfo_width()
        height = canvas.winfo_height()

        if width <= 1 or height <= 1:
            return

        # 中心位置
        x, y = width // 2, height // 2

        # 计算可用宽度
        available_width = max(width - 40, 100)

        # 绘制描边（YouTube风格：粗黑色描边）
        offsets = [(-2, -2), (-2, 2), (2, -2), (2, 2), (-2, 0), (2, 0), (0, -2), (0, 2)]
        for dx, dy in offsets:
            canvas.create_text(
                x + dx, y + dy,
                text=text,
                font=font_obj,
                fill=outline_color,
                width=available_width,
                justify=tk.CENTER,
                anchor=tk.CENTER
            )

        # 绘制主文字
        canvas.create_text(
            x, y,
            text=text,
            font=font_obj,
            fill=text_color,
            width=available_width,
            justify=tk.CENTER,
            anchor=tk.CENTER
        )

    def update_subtitle(self, original, translation):
        """
        更新字幕显示（YouTube风格：翻译为主，原文为辅）

        参数:
            original (str): 原文
            translation (str): 翻译
        """
        self.current_original = original
        self.current_translation = translation

        try:
            # 创建字体对象（使用无衬线字体，类似YouTube的Roboto）
            translation_font = font.Font(family="Microsoft YaHei", size=self.font_size_translation, weight="bold")
            original_font = font.Font(family="Arial", size=self.font_size_original, weight="normal")

            # 绘制翻译（YouTube标准：白色文字 + 黑色描边）
            self._draw_text_with_outline(
                self.translation_canvas,
                translation,
                translation_font,
                '#FFFFFF',  # 白色文字（YouTube标准）
                '#000000'   # 黑色描边
            )

            # 绘制原文（灰色小字，次要内容）
            if self.show_original and original:
                # 先更新Canvas以获取当前宽度
                self.original_canvas.update_idletasks()
                canvas_width = self.original_canvas.winfo_width()
                available_width = max(canvas_width - 40, 100)

                # 计算原文所需高度
                required_height = self._calculate_text_height(
                    self.original_canvas,
                    original,
                    original_font,
                    available_width
                )

                # 动态调整原文Canvas高度
                self.original_canvas.config(height=required_height)

                # 绘制原文
                self._draw_text_with_outline(
                    self.original_canvas,
                    original,
                    original_font,
                    '#CCCCCC',  # 浅灰色文字
                    '#000000'   # 黑色描边
                )
            else:
                # 不显示原文时，设置最小高度并清空
                self.original_canvas.config(height=0)
                self.original_canvas.delete('all')

        except Exception as e:
            print(f"[ERROR] 更新字幕显示失败: {e}")

    def _increase_font_size(self):
        """增大字体"""
        self.font_size_translation = min(self.font_size_translation + 2, 40)
        self.font_size_original = min(self.font_size_original + 2, 24)
        self.update_subtitle(self.current_original, self.current_translation)

    def _decrease_font_size(self):
        """减小字体"""
        self.font_size_translation = max(self.font_size_translation - 2, 18)
        self.font_size_original = max(self.font_size_original - 2, 12)
        self.update_subtitle(self.current_original, self.current_translation)

    def _set_alpha(self, value):
        """设置窗口透明度"""
        self.alpha = float(value)
        self.window.attributes('-alpha', self.alpha)

    def _toggle_original(self):
        """切换原文显示"""
        self.show_original = not self.show_original
        self.update_subtitle(self.current_original, self.current_translation)

    def _bind_shortcuts(self):
        """绑定快捷键"""
        # Ctrl + 上箭头：增大字体
        self.window.bind('<Control-Up>', lambda e: self._increase_font_size())
        # Ctrl + 下箭头：减小字体
        self.window.bind('<Control-Down>', lambda e: self._decrease_font_size())
        # Ctrl + 鼠标滚轮：调整透明度
        self.window.bind('<Control-MouseWheel>', self._on_mouse_wheel_alpha)
        # ESC：隐藏窗口
        self.window.bind('<Escape>', lambda e: self.hide())
        # Ctrl+O：切换原文显示
        self.window.bind('<Control-o>', lambda e: self._toggle_original())

    def _on_mouse_wheel_alpha(self, event):
        """鼠标滚轮调整透明度"""
        delta = 0.05 if event.delta > 0 else -0.05
        new_alpha = max(0.5, min(1.0, self.alpha + delta))
        self._set_alpha(new_alpha)

    def _on_window_resize(self, event):
        """窗口缩放事件处理"""
        if event.widget == self.window:
            if hasattr(self, '_resize_timer'):
                self.window.after_cancel(self._resize_timer)
            self._resize_timer = self.window.after(100, self._redraw_subtitles)

    def _redraw_subtitles(self):
        """重新绘制字幕"""
        if self.current_original or self.current_translation:
            self.update_subtitle(self.current_original, self.current_translation)

    def show(self):
        """显示窗口"""
        self.window.deiconify()
        self.window.lift()
        print("[INFO] 桌面字幕窗口已显示（YouTube风格）")

    def hide(self):
        """隐藏窗口"""
        self.window.withdraw()
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
