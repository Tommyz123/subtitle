"""
UI组件库 - 科技感自定义组件

包含组件:
1. GlowButton - 霓虹发光按钮
2. StatusIndicator - 呼吸灯状态指示器
3. NeonProgressBar - 霓虹渐变进度条
4. StatsCard - 统计信息卡片
"""

import tkinter as tk
from tkinter import font


# ========== 配色方案 ==========
class TechColors:
    """科技蓝黑主题配色"""
    # 背景色
    BG_PRIMARY = '#0a0e27'      # 深空蓝黑
    BG_SECONDARY = '#151b3d'    # 中层背景
    BG_CARD = '#1a2138'         # 卡片背景

    # 强调色（霓虹科技感）
    ACCENT_PRIMARY = '#00d9ff'  # 霓虹青
    ACCENT_SECONDARY = '#7b2cbf' # 科技紫
    ACCENT_SUCCESS = '#00ff88'  # 霓虹绿
    ACCENT_WARNING = '#ffba08'  # 霓虹黄
    ACCENT_ERROR = '#ff006e'    # 霓虹粉

    # 文字颜色
    TEXT_PRIMARY = '#e8f1f5'    # 主文字-冷白色
    TEXT_SECONDARY = '#9ca3af'  # 次要文字-灰色
    TEXT_TERTIARY = '#6b7280'   # 三级文字-深灰

    # 边框
    BORDER_PRIMARY = '#2d3748'  # 主边框
    BORDER_GLOW = '#00d9ff'     # 发光边框


# ========== 1. 霓虹发光按钮 ==========
class GlowButton(tk.Button):
    """
    带发光效果的按钮（科技感）

    特性:
    - 悬停时颜色变亮 + 发光边框
    - 支持3种预设样式: success(绿), error(粉), primary(青)
    """

    def __init__(self, parent, text, style='primary', **kwargs):
        """
        参数:
            parent: 父容器
            text: 按钮文字
            style: 样式 - 'success'(绿), 'error'(粉), 'primary'(青)
            **kwargs: 其他tk.Button参数
        """
        # 根据样式选择颜色
        style_colors = {
            'success': TechColors.ACCENT_SUCCESS,
            'error': TechColors.ACCENT_ERROR,
            'primary': TechColors.ACCENT_PRIMARY
        }
        self.glow_color = style_colors.get(style, TechColors.ACCENT_PRIMARY)

        # 文字颜色（绿色按钮用深色文字，其他用白色）
        text_color = TechColors.BG_PRIMARY if style == 'success' else '#ffffff'

        super().__init__(
            parent,
            text=text,
            font=("Microsoft YaHei", 13, "bold"),  # 11 → 13 更大更清晰
            bg=self.glow_color,
            fg=text_color,
            activebackground=self._lighten_color(self.glow_color),
            activeforeground='#ffffff',
            relief=tk.FLAT,
            padx=30,  # 25 → 30 更宽松
            pady=14,  # 12 → 14 更高
            cursor='hand2',
            borderwidth=0,
            **kwargs
        )

        self.normal_bg = self.glow_color
        self.text_color = text_color

        # 绑定悬停效果
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_enter(self, event):
        """鼠标进入 - 模拟发光（高亮边框）"""
        if self['state'] != tk.DISABLED:
            self.config(
                bg=self._lighten_color(self.glow_color),
                highlightbackground=self.glow_color,
                highlightthickness=2
            )

    def _on_leave(self, event):
        """鼠标离开 - 恢复正常"""
        if self['state'] != tk.DISABLED:
            self.config(
                bg=self.normal_bg,
                highlightthickness=0
            )

    def _lighten_color(self, hex_color):
        """使颜色变亮（模拟悬停效果）"""
        try:
            r = min(int(hex_color[1:3], 16) + 20, 255)
            g = min(int(hex_color[3:5], 16) + 20, 255)
            b = min(int(hex_color[5:7], 16) + 20, 255)
            return f'#{r:02x}{g:02x}{b:02x}'
        except:
            return hex_color


# ========== 2. 状态指示灯 ==========
class StatusIndicator:
    """
    状态指示灯（带呼吸动画）

    状态:
    - running: 运行中（绿色呼吸）
    - stopped: 已停止（灰色静态）
    - error: 错误（粉色呼吸）
    """

    def __init__(self, canvas, x, y, radius=8):
        """
        参数:
            canvas: Canvas对象
            x, y: 中心坐标
            radius: 半径（默认8px）
        """
        self.canvas = canvas
        self.x = x
        self.y = y
        self.radius = radius
        self.circle = None
        self.current_color = TechColors.TEXT_TERTIARY
        self.animation_running = False
        self.alpha = 1.0
        self.direction = -1  # -1递减，1递增

        # 创建圆圈
        self.circle = canvas.create_oval(
            x - radius, y - radius,
            x + radius, y + radius,
            fill=self.current_color,
            outline=''
        )

    def set_status(self, status):
        """
        设置状态
        status: 'running', 'stopped', 'error'
        """
        color_map = {
            'running': TechColors.ACCENT_SUCCESS,
            'stopped': TechColors.TEXT_TERTIARY,
            'error': TechColors.ACCENT_ERROR
        }
        self.current_color = color_map.get(status, TechColors.TEXT_TERTIARY)

        # 停止时不呼吸，运行时呼吸
        if status == 'running':
            self.start_breathing()
        else:
            self.stop_breathing()
            self.canvas.itemconfig(self.circle, fill=self.current_color)

    def start_breathing(self):
        """启动呼吸动画"""
        if not self.animation_running:
            self.animation_running = True
            self._breath()

    def stop_breathing(self):
        """停止呼吸动画"""
        self.animation_running = False
        self.alpha = 1.0

    def _breath(self):
        """呼吸动画循环"""
        if not self.animation_running:
            return

        # 更新透明度（通过颜色深浅模拟）
        self.alpha += self.direction * 0.05

        if self.alpha <= 0.5:
            self.alpha = 0.5
            self.direction = 1
        elif self.alpha >= 1.0:
            self.alpha = 1.0
            self.direction = -1

        # 计算颜色
        color = self._apply_alpha(self.current_color, self.alpha)
        self.canvas.itemconfig(self.circle, fill=color)

        # 50ms后继续
        self.canvas.after(50, self._breath)

    def _apply_alpha(self, hex_color, alpha):
        """模拟透明度效果（混合黑色）"""
        try:
            r = int(int(hex_color[1:3], 16) * alpha)
            g = int(int(hex_color[3:5], 16) * alpha)
            b = int(int(hex_color[5:7], 16) * alpha)
            return f'#{r:02x}{g:02x}{b:02x}'
        except:
            return hex_color


# ========== 3. 霓虹进度条 ==========
class NeonProgressBar:
    """
    霓虹风格进度条（渐变+发光效果）

    渐变逻辑:
    - 0-50%: 绿色 (#00ff88)
    - 50-80%: 青色 (#00d9ff)
    - 80-100%: 紫色 (#7b2cbf)
    """

    def __init__(self, parent, width=300, height=12):
        """
        参数:
            parent: 父容器
            width: 宽度（默认300px）
            height: 高度（默认12px）
        """
        self.canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            bg=TechColors.BG_SECONDARY,
            highlightthickness=0
        )
        self.width = width
        self.height = height
        self.progress = 0.0  # 0.0 - 1.0

        # 绘制背景轨道
        self.track = self.canvas.create_rectangle(
            0, 0, width, height,
            fill=TechColors.BG_SECONDARY,
            outline=TechColors.BORDER_PRIMARY,
            width=1
        )

        # 进度条（初始为0）
        self.bar = self.canvas.create_rectangle(
            0, 0, 0, height,
            fill=TechColors.ACCENT_SUCCESS,
            outline=''
        )

    def set_progress(self, value):
        """
        设置进度
        value: 0.0 - 1.0
        """
        self.progress = max(0.0, min(1.0, value))
        bar_width = int(self.width * self.progress)

        # 更新进度条宽度
        self.canvas.coords(self.bar, 0, 0, bar_width, self.height)

        # 根据进度改变颜色（渐变效果）
        if self.progress < 0.5:
            color = TechColors.ACCENT_SUCCESS  # 绿色
        elif self.progress < 0.8:
            color = TechColors.ACCENT_PRIMARY  # 青色
        else:
            color = TechColors.ACCENT_SECONDARY  # 紫色

        self.canvas.itemconfig(self.bar, fill=color)

    def pack(self, **kwargs):
        self.canvas.pack(**kwargs)

    def grid(self, **kwargs):
        self.canvas.grid(**kwargs)


# ========== 4. 统计信息卡片 ==========
class StatsCard(tk.Frame):
    """
    统计信息卡片

    格式:
    ┌──────────────┐
    │ 🔊 音频捕获  │
    │ ████░░  92%  │
    │ ↗ 实时监控   │
    └──────────────┘
    """

    def __init__(self, parent, icon, title, show_progress=True, **kwargs):
        """
        参数:
            parent: 父容器
            icon: 图标（emoji）
            title: 标题
            show_progress: 是否显示进度条
        """
        super().__init__(
            parent,
            bg=TechColors.BG_CARD,
            highlightbackground=TechColors.BORDER_PRIMARY,
            highlightthickness=1,
            **kwargs
        )

        # 内容容器
        content = tk.Frame(self, bg=TechColors.BG_CARD)
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=12)

        # 标题行（图标 + 文字）
        title_frame = tk.Frame(content, bg=TechColors.BG_CARD)
        title_frame.pack(fill=tk.X)

        self.title_label = tk.Label(
            title_frame,
            text=f"{icon} {title}",
            font=("Microsoft YaHei", 10, "bold"),
            bg=TechColors.BG_CARD,
            fg=TechColors.TEXT_SECONDARY
        )
        self.title_label.pack(side=tk.LEFT)

        # 进度条（可选）
        if show_progress:
            progress_frame = tk.Frame(content, bg=TechColors.BG_CARD)
            progress_frame.pack(fill=tk.X, pady=(8, 8))

            self.progress_bar = NeonProgressBar(progress_frame, width=200, height=8)
            self.progress_bar.pack(side=tk.LEFT)

            self.progress_label = tk.Label(
                progress_frame,
                text="0%",
                font=("Consolas", 10, "bold"),
                bg=TechColors.BG_CARD,
                fg=TechColors.ACCENT_SUCCESS
            )
            self.progress_label.pack(side=tk.LEFT, padx=(10, 0))
        else:
            self.progress_bar = None
            self.progress_label = None

        # 数值标签
        self.value_label = tk.Label(
            content,
            text="--",
            font=("Consolas", 11),
            bg=TechColors.BG_CARD,
            fg=TechColors.TEXT_PRIMARY
        )
        self.value_label.pack(anchor=tk.W)

    def set_progress(self, value, text=None):
        """
        设置进度
        value: 0.0 - 1.0
        text: 百分比文字（可选）
        """
        if self.progress_bar:
            self.progress_bar.set_progress(value)
            if self.progress_label:
                display_text = text if text else f"{int(value * 100)}%"
                self.progress_label.config(text=display_text)

    def set_value(self, text):
        """设置数值文字"""
        self.value_label.config(text=text)

    def set_title(self, text):
        """更新标题"""
        self.title_label.config(text=text)
