# 字幕存储模块设计

## 📝 模块概述

**文件**: `app/subtitle_storage.py`
**职责**: 内存存储字幕数据，导出SRT/VTT/TXT格式文件

**代码量**: ~80行（包含所有导出格式）

---

## 🎯 核心功能

1. **内存存储**: 维护字幕列表（原文+翻译+时间戳）
2. **SRT导出**: 标准字幕格式，支持视频播放器
3. **VTT导出**: Web字幕格式（可选）
4. **TXT导出**: 纯文本格式（可选）
5. **时间戳管理**: 自动计算字幕时长

---

## 🔧 类设计

### SubtitleStorage

```python
class SubtitleStorage:
    """
    字幕存储类

    职责:
    - 内存存储字幕列表
    - 计算时间戳
    - 导出多种格式
    """

    def __init__(self):
        """初始化"""
        self.subtitles = []              # 字幕列表
        self.start_time = time.time()    # 记录开始时间

    def add_subtitle(self, original, translation):
        """添加字幕"""

    def export_srt(self, filepath):
        """导出SRT格式"""

    def export_vtt(self, filepath):
        """导出VTT格式（可选）"""

    def export_txt(self, filepath):
        """导出TXT格式（可选）"""

    def format_srt_time(self, seconds):
        """格式化SRT时间戳"""

    def format_vtt_time(self, seconds):
        """格式化VTT时间戳（可选）"""

    def clear(self):
        """清空字幕"""
```

---

## 📦 数据结构

### 字幕条目

```python
{
    'timestamp': 12.5,              # 相对时间戳（秒）
    'original': "Hello, world!",    # 原文（英文）
    'translation': "你好，世界！"    # 翻译（中文）
}
```

### 字幕列表示例

```python
self.subtitles = [
    {
        'timestamp': 0.0,
        'original': "Welcome to the show.",
        'translation': "欢迎来到节目。"
    },
    {
        'timestamp': 5.3,
        'original': "Today we will discuss AI.",
        'translation': "今天我们将讨论人工智能。"
    },
    {
        'timestamp': 10.8,
        'original': "Let's get started.",
        'translation': "让我们开始吧。"
    }
]
```

---

## 🚀 核心方法实现

### 1. __init__()

```python
def __init__(self):
    """初始化字幕存储"""
    self.subtitles = []
    self.start_time = time.time()  # 记录程序启动时间
```

**注意**:
- `start_time` 用于计算相对时间戳
- 每次调用 `clear()` 会重置 `start_time`

---

### 2. add_subtitle()

**职责**: 添加一条字幕到列表

```python
def add_subtitle(self, original, translation):
    """
    添加字幕

    参数:
        original (str): 原文
        translation (str): 翻译
    """
    # 计算相对时间戳（从start_time开始）
    timestamp = time.time() - self.start_time

    # 添加到列表
    self.subtitles.append({
        'timestamp': timestamp,
        'original': original,
        'translation': translation
    })
```

**线程安全**:
- ⚠️ 此方法会被转录线程调用（通过回调）
- ⚠️ 导出时也会读取 `self.subtitles`
- ✅ **必须在外部使用 `threading.Lock` 保护**（在main.py中实现）

---

### 3. export_srt()

**职责**: 导出标准SRT字幕格式

```python
def export_srt(self, filepath):
    """
    导出SRT格式字幕

    SRT格式示例:
    1
    00:00:00,000 --> 00:00:05,300
    Welcome to the show.
    欢迎来到节目。

    2
    00:00:05,300 --> 00:00:10,800
    Today we will discuss AI.
    今天我们将讨论人工智能。
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        for i, sub in enumerate(self.subtitles, 1):
            # 起始时间
            start = self.format_srt_time(sub['timestamp'])

            # ⚠️ 关键: 时长根据下一条字幕时间戳计算
            if i < len(self.subtitles):
                # 使用下一条字幕的时间戳作为结束时间
                duration = self.subtitles[i]['timestamp'] - sub['timestamp']
            else:
                # 最后一条字幕默认5秒
                duration = 5.0

            end = self.format_srt_time(sub['timestamp'] + duration)

            # 写入SRT格式
            f.write(f"{i}\n")                          # 序号
            f.write(f"{start} --> {end}\n")            # 时间范围
            f.write(f"{sub['original']}\n")            # 原文
            f.write(f"{sub['translation']}\n")         # 翻译
            f.write("\n")                              # 空行分隔
```

**关键设计决策**:

1. **时长计算方式**:
   ```python
   # ❌ 错误: 所有字幕都是5秒
   duration = 5.0

   # ✅ 正确: 根据下一条字幕计算实际时长
   duration = self.subtitles[i]['timestamp'] - sub['timestamp']
   ```

2. **为什么这样计算？**
   - 每条字幕的实际持续时间不同
   - 根据下一条字幕的出现时间，自动调整当前字幕的显示时长
   - 最后一条字幕无法计算，默认5秒

**SRT格式规范**:
- 序号从1开始
- 时间格式: `HH:MM:SS,mmm` (使用逗号分隔毫秒)
- 双语字幕: 原文和翻译分两行
- 字幕之间用空行分隔

---

### 4. format_srt_time()

**职责**: 将秒数转换为SRT时间格式

```python
def format_srt_time(self, seconds):
    """
    格式化为SRT时间格式

    参数:
        seconds (float): 秒数 (例如: 65.123)

    返回:
        str: SRT时间格式 (例如: "00:01:05,123")
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)

    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
```

**格式说明**:
- `{hours:02d}`: 小时（2位数，前导零）
- `{minutes:02d}`: 分钟（2位数，前导零）
- `{secs:02d}`: 秒（2位数，前导零）
- `{millis:03d}`: 毫秒（3位数，前导零）
- ⚠️ 使用逗号 `,` 分隔毫秒（不是点 `.`）

**测试示例**:
```python
format_srt_time(0.0)     # "00:00:00,000"
format_srt_time(5.3)     # "00:00:05,300"
format_srt_time(65.123)  # "00:01:05,123"
format_srt_time(3665.5)  # "01:01:05,500"
```

---

### 5. clear()

**职责**: 清空字幕列表，重置时间戳

```python
def clear(self):
    """清空字幕"""
    self.subtitles = []
    self.start_time = time.time()  # 重置起始时间
```

**使用场景**:
- 用户点击"清空"按钮
- 重新开始捕获时清空旧数据

---

## 🎨 可选功能（阶段2/3）

### export_vtt()

**VTT格式**: WebVTT (Web Video Text Tracks)，用于HTML5视频

```python
def export_vtt(self, filepath):
    """
    导出VTT格式字幕

    VTT格式示例:
    WEBVTT

    1
    00:00:00.000 --> 00:00:05.300
    Welcome to the show.
    欢迎来到节目。

    2
    00:00:05.300 --> 00:00:10.800
    Today we will discuss AI.
    今天我们将讨论人工智能。
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        # VTT文件头
        f.write("WEBVTT\n\n")

        for i, sub in enumerate(self.subtitles, 1):
            start = self.format_vtt_time(sub['timestamp'])

            if i < len(self.subtitles):
                duration = self.subtitles[i]['timestamp'] - sub['timestamp']
            else:
                duration = 5.0

            end = self.format_vtt_time(sub['timestamp'] + duration)

            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{sub['original']}\n")
            f.write(f"{sub['translation']}\n")
            f.write("\n")

def format_vtt_time(self, seconds):
    """
    格式化为VTT时间格式

    VTT格式与SRT的区别:
    - 使用点 (.) 分隔毫秒，而不是逗号 (,)
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)

    # ⚠️ 使用点 (.) 分隔毫秒
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"
```

**SRT vs VTT 区别**:
- VTT文件开头有 `WEBVTT` 标记
- VTT使用点 `.` 分隔毫秒（SRT使用逗号 `,`）
- VTT支持样式标签（如 `<b>`, `<i>`）

---

### export_txt()

**纯文本格式**: 仅导出原文和翻译，不含时间戳

```python
def export_txt(self, filepath):
    """
    导出纯文本格式

    TXT格式示例:
    Welcome to the show.
    欢迎来到节目。

    Today we will discuss AI.
    今天我们将讨论人工智能。

    Let's get started.
    让我们开始吧。
    """
    with open(filepath, 'w', encoding='utf-8') as f:
        for sub in self.subtitles:
            f.write(f"{sub['original']}\n")
            f.write(f"{sub['translation']}\n")
            f.write("\n")
```

**使用场景**:
- 会议记录
- 学习笔记
- 文本分析

---

## 📊 内存优化（可选，阶段3）

### 限制字幕数量

```python
class SubtitleStorage:
    def __init__(self):
        self.subtitles = []
        self.start_time = time.time()
        self.max_subtitles = 500  # 最多保留500条字幕

    def add_subtitle(self, original, translation):
        timestamp = time.time() - self.start_time
        self.subtitles.append({
            'timestamp': timestamp,
            'original': original,
            'translation': translation
        })

        # 内存保护: 超过限制时删除最旧的字幕
        if len(self.subtitles) > self.max_subtitles:
            self.subtitles.pop(0)
```

**为什么需要限制？**
- 长时间运行时，字幕列表无限增长
- 500条字幕 ≈ 50KB内存（估算）
- 限制后最大内存占用可控

---

## ⚠️ 并发访问保护

### 问题场景

```
线程1 (转录线程):
    add_subtitle(original, translation)  # 写入

线程2 (GUI主线程):
    export_srt(filepath)                 # 读取
```

### 解决方案（在main.py中实现）

```python
# main.py
storage_lock = threading.Lock()

# 写入时加锁
def update_subtitle(original, translation):
    with storage_lock:
        subtitle_storage.add_subtitle(original, translation)

# 导出时加锁
def export_srt():
    filepath = # ... 文件选择对话框 ...
    if filepath:
        with storage_lock:
            subtitle_storage.export_srt(filepath)
```

**优化建议（阶段3）**:
```python
# 导出时复制数据副本，避免长时间持锁
def export_srt():
    with storage_lock:
        data_copy = subtitle_storage.subtitles.copy()

    # 文件IO在锁外执行
    with open(filepath, 'w', encoding='utf-8') as f:
        for i, sub in enumerate(data_copy, 1):
            # ... 写入逻辑 ...
```

---

## 🔍 调试技巧

### 打印字幕列表

```python
def add_subtitle(self, original, translation):
    timestamp = time.time() - self.start_time
    self.subtitles.append({
        'timestamp': timestamp,
        'original': original,
        'translation': translation
    })

    # 调试输出
    print(f"[DEBUG] 已添加字幕 #{len(self.subtitles)}: {timestamp:.1f}s - {original[:30]}...")
```

### 验证导出文件

```bash
# 检查SRT文件格式
cat output.srt

# 使用VLC播放器测试
vlc video.mp4 --sub-file=output.srt
```

---

## 📚 依赖项

```python
import time
```

**无需额外安装依赖**

---

## 🎯 扩展功能（可选）

### 1. 自定义时长

```python
def export_srt(self, filepath, default_duration=5.0):
    """允许自定义最后一条字幕的默认时长"""
    # ... 导出逻辑 ...
    duration = default_duration if i == len(self.subtitles) else ...
```

### 2. 导出单语字幕

```python
def export_srt_original_only(self, filepath):
    """仅导出原文"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for i, sub in enumerate(self.subtitles, 1):
            # ... 时间计算 ...
            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{sub['original']}\n")  # 仅原文
            f.write("\n")
```

### 3. 字幕统计

```python
def get_stats(self):
    """获取字幕统计信息"""
    total_duration = self.subtitles[-1]['timestamp'] if self.subtitles else 0
    total_chars = sum(len(sub['original']) + len(sub['translation']) for sub in self.subtitles)

    return {
        'total_subtitles': len(self.subtitles),
        'total_duration': total_duration,
        'total_characters': total_chars,
        'avg_duration': total_duration / len(self.subtitles) if self.subtitles else 0
    }
```

---

## ✅ 测试清单

### 基础功能测试

- [ ] 添加字幕后，列表长度正确增加
- [ ] 时间戳计算正确
- [ ] 导出SRT文件格式正确
- [ ] 清空后，列表为空且时间戳重置

### 格式测试

- [ ] SRT时间格式使用逗号分隔毫秒
- [ ] VTT时间格式使用点分隔毫秒
- [ ] 双语字幕正确显示在两行
- [ ] 字幕序号从1开始

### 边界测试

- [ ] 空列表导出不报错
- [ ] 单条字幕导出正确
- [ ] 最后一条字幕时长为5秒
- [ ] Unicode字符（中文、表情）正确保存

---

**最后更新**: 2025-11-05
**文档版本**: v1.0
