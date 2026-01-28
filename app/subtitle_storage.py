"""
字幕存储模块

职责:
- 内存存储字幕数据（原文+翻译+时间戳）
- 导出SRT格式文件
- 时间戳管理

注意:
- 此类的方法会被多个线程访问，必须在外部使用Lock保护
- P0修复: 字幕时长根据下一条字幕时间戳计算
"""

import time


class SubtitleStorage:
    """字幕存储类 - 内存存储和SRT导出"""

    def __init__(self):
        """初始化字幕存储"""
        self.subtitles = []              # 字幕列表
        self.start_time = time.time()    # 记录开始时间

    def add_subtitle(self, original, translation):
        """
        添加字幕

        参数:
            original (str): 原文
            translation (str): 翻译

        注意:
            - 此方法会被转录线程调用
            - 必须在外部使用Lock保护
        """
        # 计算相对时间戳（从start_time开始）
        timestamp = time.time() - self.start_time

        # 添加到列表
        self.subtitles.append({
            'timestamp': timestamp,
            'original': original,
            'translation': translation
        })

    def export_srt(self, filepath):
        """
        导出SRT格式字幕

        参数:
            filepath (str): 导出文件路径

        SRT格式示例:
            1
            00:00:00,000 --> 00:00:05,300
            Welcome to the show.
            欢迎来到节目。

            2
            00:00:05,300 --> 00:00:10,800
            Today we will discuss AI.
            今天我们将讨论人工智能。

        注意:
            - 必须在外部使用Lock保护
        """
        with open(filepath, 'w', encoding='utf-8') as f:
            for i, sub in enumerate(self.subtitles, 1):
                # 起始时间
                start = self.format_srt_time(sub['timestamp'])

                # P0修复: 时长根据下一条字幕时间戳计算，不固定5秒
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

        print(f"[INFO] 已导出 {len(self.subtitles)} 条字幕到: {filepath}")

    def format_srt_time(self, seconds):
        """
        格式化为SRT时间格式

        参数:
            seconds (float): 秒数 (例如: 65.123)

        返回:
            str: SRT时间格式 (例如: "00:01:05,123")

        注意:
            - SRT格式使用逗号分隔毫秒，不是点
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)

        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def get_subtitles_copy(self):
        """
        P9优化: 获取字幕列表的浅拷贝

        用于锁粒度优化：锁内快速复制（微秒级），文件IO在锁外

        返回:
            list: 字幕列表的副本

        注意:
            - 必须在外部使用Lock保护
        """
        return self.subtitles.copy()

    def clear(self):
        """
        清空字幕列表并重置时间

        注意:
            - 必须在外部使用Lock保护
        """
        self.subtitles = []
        self.start_time = time.time()
        print("[INFO] 字幕已清空")
