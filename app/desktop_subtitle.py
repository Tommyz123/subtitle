"""
桌面字幕窗口模块

职责:
- 创建独立的置顶字幕窗口
- 支持拖动和调整位置
- 半透明背景
- 实时更新字幕显示
"""

import tkinter as tk
from tkinter import ttk


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
        self.window.title("桌面字幕")
        self.window.geometry("800x150+100+500")  # 默认位置在屏幕下方

        # 置顶显示
        self.window.attributes('-topmost', True)

        # 半透明背景 (0.0-1.0, 0.9表示90%不透明)
        self.window.attributes('-alpha', 0.9)

        # 窗口样式 - 保留标题栏以便拖动
        # self.window.overrideredirect(True)  # 如果需要无边框可以启用

        # 背景颜色
        self.window.configure(bg='black')

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

    def _create_widgets(self):
        """创建窗口内部组件"""
        # 主容器
        main_frame = tk.Frame(self.window, bg='black')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 原文标签
        self.original_label = tk.Label(
            main_frame,
            text="",
            font=("Arial", 16, "bold"),
            fg="white",
            bg="black",
            wraplength=750,
            justify=tk.CENTER
        )
        self.original_label.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # 分隔线
        separator = tk.Frame(main_frame, height=2, bg='gray')
        separator.pack(fill=tk.X, pady=5)

        # 翻译标签
        self.translation_label = tk.Label(
            main_frame,
            text="",
            font=("Microsoft YaHei", 14),
            fg="yellow",
            bg="black",
            wraplength=750,
            justify=tk.CENTER
        )
        self.translation_label.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

    def _bind_drag_events(self):
        """绑定窗口拖动事件"""
        # 绑定到标题栏和整个窗口
        self.window.bind('<Button-1>', self._on_drag_start)
        self.window.bind('<B1-Motion>', self._on_drag_motion)

        # 也绑定到标签上，这样点击标签也能拖动
        self.original_label.bind('<Button-1>', self._on_drag_start)
        self.original_label.bind('<B1-Motion>', self._on_drag_motion)
        self.translation_label.bind('<Button-1>', self._on_drag_start)
        self.translation_label.bind('<B1-Motion>', self._on_drag_motion)

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

    def update_subtitle(self, original, translation):
        """
        更新字幕显示

        参数:
            original (str): 原文
            translation (str): 翻译
        """
        self.current_original = original
        self.current_translation = translation

        # 更新显示 (只显示最新一条)
        self.original_label.config(text=original)
        self.translation_label.config(text=translation)

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
