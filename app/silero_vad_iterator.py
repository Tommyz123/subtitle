"""
Silero VAD 迭代器 - 语音活动检测

职责:
- 封装Silero VAD模型
- 支持任意长度音频流式检测
- 检测语音片段的开始和结束时间戳

阶段2特性:
- P0修复: speech_start必须是实例变量(不是类变量)
- 支持可配置的阈值和静音时长
- 固定窗口大小处理(512样本)

参考: example/WhisperLiveKit-main/whisperlivekit/silero_vad_iterator.py
"""

import numpy as np


class VADIterator:
    """
    VAD迭代器基类 - 检测语音片段

    工作原理:
    1. 接收音频块(float32, [-1, 1])
    2. 调用Silero VAD模型获取语音概率
    3. 使用状态机检测语音开始/结束
    4. 返回语音片段的时间戳
    """

    def __init__(
        self,
        model,
        threshold: float = 0.5,
        sampling_rate: int = 16000,
        min_silence_duration_ms: int = 500,
        speech_pad_ms: int = 30
    ):
        """
        初始化VAD迭代器

        参数:
            model: Silero VAD模型
            threshold: 语音检测阈值 (0.0-1.0), 默认0.5
            sampling_rate: 采样率(Hz), 默认16000
            min_silence_duration_ms: 最小静音时长(毫秒), 默认500
            speech_pad_ms: 语音填充时长(毫秒), 默认30
        """
        self.model = model
        self.threshold = threshold
        self.sampling_rate = sampling_rate
        self.min_silence_duration_ms = min_silence_duration_ms
        self.speech_pad_ms = speech_pad_ms

        # P0修复: 必须是实例变量,不是类变量!
        # 原因: 类变量会导致多个实例共享状态,造成VAD检测错误
        self.triggered = False          # 是否已触发语音检测
        self.temp_end = 0               # 临时静音结束位置
        self.current_sample = 0         # 当前样本索引
        self.speech_start = None        # ← 关键修复: 必须是self.speech_start

    def __call__(self, x: np.ndarray, return_seconds: bool = False):
        """
        处理音频块,检测语音片段

        参数:
            x: 音频数据 (float32, [-1, 1])
            return_seconds: 是否返回秒数(True)或样本数(False)

        返回:
            dict: {'start': int, 'end': int} 或 None
        """
        import torch

        # 1. 调用VAD模型获取语音概率
        if not isinstance(x, torch.Tensor):
            x_tensor = torch.from_numpy(x)
        else:
            x_tensor = x

        speech_prob = self.model(x_tensor, self.sampling_rate).item()

        # 2. 状态机: 检测语音开始/结束

        # 情况1: 检测到语音,重置临时结束位置
        if speech_prob >= self.threshold and self.temp_end:
            self.temp_end = 0

        # 情况2: 语音开始(从未触发 → 触发)
        if speech_prob >= self.threshold and not self.triggered:
            self.triggered = True
            self.speech_start = self.current_sample

        # 情况3: 语音结束检测
        if speech_prob < self.threshold and self.triggered:
            # 记录第一次低于阈值的位置
            if not self.temp_end:
                self.temp_end = self.current_sample

            # 检查静音是否足够长
            silence_duration = self.current_sample - self.temp_end
            min_silence_samples = self.min_silence_duration_ms * self.sampling_rate / 1000

            if silence_duration >= min_silence_samples:
                # 静音足够长,确认语音片段结束
                speech_end = self.temp_end

                # 重置状态
                self.triggered = False
                self.temp_end = 0

                # 返回语音片段
                if return_seconds:
                    return {
                        'start': self.speech_start / self.sampling_rate,
                        'end': speech_end / self.sampling_rate
                    }
                else:
                    return {'start': self.speech_start, 'end': speech_end}

        # 更新当前位置
        self.current_sample += len(x)

        return None

    def reset(self):
        """重置VAD状态"""
        self.triggered = False
        self.temp_end = 0
        self.current_sample = 0
        self.speech_start = None


class FixedVADIterator(VADIterator):
    """
    固定窗口VAD迭代器 - 处理任意长度音频

    工作原理:
    1. 维护内部缓冲区
    2. 每512样本调用一次父类VADIterator
    3. 合并连续的语音片段

    用途:
    - 父类VADIterator要求固定窗口大小(512样本)
    - 本类可以处理任意长度的音频块
    """

    def __init__(self, *args, **kwargs):
        """初始化,继承父类参数"""
        super().__init__(*args, **kwargs)

        # 音频缓冲区
        self.buffer = np.array([], dtype=np.float32)

        # 固定窗口大小(Silero VAD要求)
        self.window_size_samples = 512

    def __call__(self, x: np.ndarray, return_seconds: bool = False):
        """
        处理任意长度音频块

        参数:
            x: 音频数据 (float32, [-1, 1], 任意长度)
            return_seconds: 是否返回秒数

        返回:
            dict: {'start': int/float, 'end': int/float} 或 None
        """
        # 1. 添加到缓冲区
        self.buffer = np.concatenate([self.buffer, x])

        speech_segments = []

        # 2. 每512样本处理一次
        while len(self.buffer) >= self.window_size_samples:
            # 取出512样本
            chunk = self.buffer[:self.window_size_samples]
            self.buffer = self.buffer[self.window_size_samples:]

            # 调用父类处理
            result = super().__call__(chunk, return_seconds=return_seconds)

            if result:
                speech_segments.append(result)

        # 3. 合并连续语音片段
        if speech_segments:
            # 返回第一个片段的开始 + 最后一个片段的结束
            return {
                'start': speech_segments[0]['start'],
                'end': speech_segments[-1]['end']
            }

        return None

    def reset(self):
        """重置状态和缓冲区"""
        super().reset()
        self.buffer = np.array([], dtype=np.float32)


def validate_vad_params(threshold: float, min_silence_ms: int) -> tuple:
    """
    P0修复: VAD参数验证

    验证:
    - threshold必须在0-1之间
    - min_silence_ms必须 > 0

    返回:
        (bool, str): (是否有效, 错误信息)
    """
    if not (0 <= threshold <= 1):
        return False, f"VAD阈值必须在0-1之间,当前值: {threshold}"

    if min_silence_ms <= 0:
        return False, f"最小静音时长必须 > 0,当前值: {min_silence_ms}"

    return True, ""
