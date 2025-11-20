"""
UI组件库 - 科技感自定义组件

包含组件:
1. TechColors - 统一配色方案
2. ModernFrame - 标准化背景容器
3. ModernLabel - 标准化文本标签
4. ModernTitledFrame - 带标题的标准化容器
5. GlowButton - 霓虹发光按钮
6. StatusIndicator - 呼吸灯状态指示器
7. NeonProgressBar - 霓虹渐变进度条
8. StatsCard - 统计信息卡片
"""

import tkinter as tk
from tkinter import ttk

# ========== 配色方案 ==========
class TechColors:
    """科技蓝黑主题配色 - 2025优化版"""
    # 背景色
    BG_PRIMARY = '#0a0e27'      # 深空蓝黑 (主背景)
    BG_SECONDARY = '#151b3d'    # 中层背景 (侧边栏/底栏)
    BG_CARD = '#1a2138'         # 卡片背景 (内容区块)
    BG_HOVER = '#232d4b'        # 悬停背景

    # 强调色（霓虹科技感）
    ACCENT_PRIMARY = '#00d9ff'  # 霓虹青 (主操作/高亮)
    ACCENT_SECONDARY = '#7b2cbf' # 科技紫 (次要/渐变)
    ACCENT_SUCCESS = '#00ff88'  # 霓虹绿 (成功/运行中)
    ACCENT_WARNING = '#ffba08'  # 霓虹黄 (警告/注意)
    ACCENT_ERROR = '#ff006e'    # 霓虹粉 (错误/停止)

    # 文字颜色
    TEXT_PRIMARY = '#ffffff'    # 主文字-纯白
    TEXT_SECONDARY = '#a0aec0'  # 次要文字-浅灰
    TEXT_TERTIARY = '#718096'   # 三级文字-深灰
    TEXT_DISABLED = '#4a5568'   # 禁用文字

    # 边框
    BORDER_PRIMARY = '#2d3748'  # 主边框
    BORDER_GLOW = '#00d9ff'     # 发光边框
    
    # 字体配置
    FONT_FAMILY = "Microsoft YaHei"
    FONT_H1 = (FONT_FAMILY, 18, "bold")
    FONT_H2 = (FONT_FAMILY, 14, "bold")
    FONT_BODY = (FONT_FAMILY, 10)
    FONT_BODY_BOLD = (FONT_FAMILY, 10, "bold")
    FONT_SMALL = (FONT_FAMILY, 9)
    FONT_CODE = ("Consolas", 11)


# ========== 基础组件 ==========

class ModernFrame(tk.Frame):
    """标准化背景容器"""
    def __init__(self, parent, bg=TechColors.BG_PRIMARY, **kwargs):
        super().__init__(parent, bg=bg, **kwargs)

class ModernLabel(tk.Label):
    """标准化文本标签"""
    def __init__(self, parent, text, style='body', color=None, **kwargs):
        """
        style: 'h1', 'h2', 'body', 'body_bold', 'small'
        """
        font_map = {
            'h1': TechColors.FONT_H1,
            'h2': TechColors.FONT_H2,
            'body': TechColors.FONT_BODY,
            'body_bold': TechColors.FONT_BODY_BOLD,
            'small': TechColors.FONT_SMALL
        }
        
        default_colors = {
            'h1': TechColors.TEXT_PRIMARY,
            'h2': TechColors.ACCENT_PRIMARY,
            'body': TechColors.TEXT_PRIMARY,
            'body_bold': TechColors.TEXT_PRIMARY,
            'small': TechColors.TEXT_SECONDARY
        }

        fg_color = color if color else default_colors.get(style, TechColors.TEXT_PRIMARY)
        
        super().__init__(
            parent,
            text=text,
            font=font_map.get(style, TechColors.FONT_BODY),
            bg=parent['bg'], # 自动继承父容器背景
            fg=fg_color,
            **kwargs
        )

class ModernTitledFrame(tk.Frame):
    """带标题的标准化容器 (替代Labelframe)"""
    def __init__(self, parent, title, icon="", bg=TechColors.BG_CARD, **kwargs):
        super().__init__(
            parent, 
            bg=bg, 
            highlightbackground=TechColors.BORDER_PRIMARY, 
            highlightthickness=1, 
            **kwargs
        )
        
        # 标题栏
        self.header = tk.Frame(self, bg=bg)
        self.header.pack(fill=tk.X, padx=15, pady=(15, 10))
        
        title_text = f"{icon} {title}" if icon else title
        
        tk.Label(
            self.header,
            text=title_text,
            font=TechColors.FONT_H2,
            bg=bg,
            fg=TechColors.ACCENT_PRIMARY
        ).pack(side=tk.LEFT)
        
        # 内容容器
        self.content = tk.Frame(self, bg=bg)
        self.content.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

# ========== 1. 霓虹发光按钮 ==========
class GlowButton(tk.Button):
    """
    带发光效果的按钮（科技感）
    """
    def __init__(self, parent, text, style='primary', **kwargs):
        style_colors = {
            'success': TechColors.ACCENT_SUCCESS,
            'error': TechColors.ACCENT_ERROR,
            'primary': TechColors.ACCENT_PRIMARY
        }
        self.glow_color = style_colors.get(style, TechColors.ACCENT_PRIMARY)
        text_color = TechColors.BG_PRIMARY if style == 'success' else '#ffffff'

        super().__init__(
            parent,
            text=text,
            font=(TechColors.FONT_FAMILY, 11, "bold"),
            bg=self.glow_color,
            fg=text_color,
            activebackground=self._lighten_color(self.glow_color),
            activeforeground='#ffffff',
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2',
            borderwidth=0,
            **kwargs
        )

        self.normal_bg = self.glow_color
        self.bind('<Enter>', self._on_enter)
        self.bind('<Leave>', self._on_leave)

    def _on_enter(self, event):
        if self['state'] != tk.DISABLED:
            self.config(
                bg=self._lighten_color(self.glow_color),
                highlightbackground=self.glow_color,
                highlightthickness=1
            )

    def _on_leave(self, event):
        if self['state'] != tk.DISABLED:
            self.config(bg=self.normal_bg, highlightthickness=0)

    def _lighten_color(self, hex_color):
        try:
            r = min(int(hex_color[1:3], 16) + 30, 255)
            g = min(int(hex_color[3:5], 16) + 30, 255)
            b = min(int(hex_color[5:7], 16) + 30, 255)
            return f'#{r:02x}{g:02x}{b:02x}'
        except:
            return hex_color

# ========== 2. 状态指示灯 ==========
class StatusIndicator:
    """状态指示灯（带呼吸动画）"""
    def __init__(self, canvas, x, y, radius=6):
        self.canvas = canvas
        self.x = x
        self.y = y
        self.radius = radius
        self.current_color = TechColors.TEXT_TERTIARY
        self.animation_running = False
        self.alpha = 1.0
        self.direction = -1

        self.circle = canvas.create_oval(
            x - radius, y - radius,
            x + radius, y + radius,
            fill=self.current_color,
            outline=''
        )

    def set_status(self, status):
        color_map = {
            'running': TechColors.ACCENT_SUCCESS,
            'stopped': TechColors.TEXT_TERTIARY,
            'error': TechColors.ACCENT_ERROR
        }
        self.current_color = color_map.get(status, TechColors.TEXT_TERTIARY)
        
        if status == 'running':
            self.start_breathing()
        else:
            self.stop_breathing()
            self.canvas.itemconfig(self.circle, fill=self.current_color)

    def start_breathing(self):
        if not self.animation_running:
            self.animation_running = True
            self._breath()

    def stop_breathing(self):
        self.animation_running = False
        self.alpha = 1.0

    def _breath(self):
        if not self.animation_running: return
        self.alpha += self.direction * 0.05
        if self.alpha <= 0.4:
            self.alpha = 0.4
            self.direction = 1
        elif self.alpha >= 1.0:
            self.alpha = 1.0
            self.direction = -1
            
        color = self._apply_alpha(self.current_color, self.alpha)
        self.canvas.itemconfig(self.circle, fill=color)
        self.canvas.after(50, self._breath)

    def _apply_alpha(self, hex_color, alpha):
        try:
            r = int(int(hex_color[1:3], 16) * alpha)
            g = int(int(hex_color[3:5], 16) * alpha)
            b = int(int(hex_color[5:7], 16) * alpha)
            return f'#{r:02x}{g:02x}{b:02x}'
        except:
            return hex_color

# ========== 3. 霓虹进度条 ==========
class NeonProgressBar:
    """霓虹风格进度条"""
    def __init__(self, parent, width=200, height=6):
        self.canvas = tk.Canvas(
            parent,
            width=width,
            height=height,
            bg=TechColors.BG_SECONDARY,
            highlightthickness=0
        )
        self.width = width
        self.height = height
        self.progress = 0.0

        # 背景
        self.canvas.create_rectangle(
            0, 0, width, height,
            fill=TechColors.BG_SECONDARY,
            outline=''
        )
        # 进度
        self.bar = self.canvas.create_rectangle(
            0, 0, 0, height,
            fill=TechColors.ACCENT_SUCCESS,
            outline=''
        )

    def set_progress(self, value):
        self.progress = max(0.0, min(1.0, value))
        bar_width = int(self.width * self.progress)
        self.canvas.coords(self.bar, 0, 0, bar_width, self.height)
        
        if self.progress < 0.5: color = TechColors.ACCENT_SUCCESS
        elif self.progress < 0.8: color = TechColors.ACCENT_PRIMARY
        else: color = TechColors.ACCENT_SECONDARY
        
        self.canvas.itemconfig(self.bar, fill=color)

    def pack(self, **kwargs): self.canvas.pack(**kwargs)
    def grid(self, **kwargs): self.canvas.grid(**kwargs)

# ========== 4. 统计信息卡片 ==========
class StatsCard(ModernFrame):
    """统计信息卡片"""
    def __init__(self, parent, icon, title, show_progress=True, **kwargs):
        super().__init__(
            parent,
            bg=TechColors.BG_CARD,
            highlightbackground=TechColors.BORDER_PRIMARY,
            highlightthickness=1,
            **kwargs
        )

        content = tk.Frame(self, bg=TechColors.BG_CARD)
        content.pack(fill=tk.BOTH, expand=True, padx=15, pady=12)

        # 标题
        title_frame = tk.Frame(content, bg=TechColors.BG_CARD)
        title_frame.pack(fill=tk.X)
        
        ModernLabel(
            title_frame, 
            text=f"{icon} {title}", 
            style='body_bold', 
            color=TechColors.TEXT_SECONDARY
        ).pack(side=tk.LEFT)

        # 进度条
        if show_progress:
            progress_frame = tk.Frame(content, bg=TechColors.BG_CARD)
            progress_frame.pack(fill=tk.X, pady=(8, 8))
            
            self.progress_bar = NeonProgressBar(progress_frame, width=150, height=6)
            self.progress_bar.pack(side=tk.LEFT)
            
            self.progress_label = ModernLabel(
                progress_frame, text="0%", style='small', color=TechColors.ACCENT_SUCCESS
            )
            self.progress_label.pack(side=tk.LEFT, padx=(10, 0))
        else:
            self.progress_bar = None
            self.progress_label = None

        # 数值
        self.value_label = ModernLabel(
            content, text="--", style='code', color=TechColors.TEXT_PRIMARY
        )
        self.value_label.pack(anchor=tk.W)

    def set_progress(self, value, text=None):
        if self.progress_bar:
            self.progress_bar.set_progress(value)
            if self.progress_label:
                display_text = text if text else f"{int(value * 100)}%"
                self.progress_label.config(text=display_text)

    def set_value(self, text):
        self.value_label.config(text=text)
