"""
音频捕获模块 - 阶段2优化版本

职责:
- 捕获VB-Cable虚拟音频设备的系统音频
- 固定5秒分块
- 将音频块放入队列传递给转录线程
- 集成VAD检测跳过静音段

阶段2新增:
- 集成Silero VAD语音活动检测
- P0修复: 立体声转单声道使用int32, scipy重采样, VAD模型3次重试, VAD参数验证
"""

import pyaudio
import threading
import queue
import time
import os
import numpy as np


class AudioCaptureThread(threading.Thread):
    """音频捕获线程 - 从VB-Cable捕获音频并分块 + VAD检测"""

    def __init__(self, audio_queue, stop_event, enable_vad=False, enable_playback=True):
        """
        参数:
            audio_queue (queue.Queue): 音频数据队列
            stop_event (threading.Event): 停止信号
            enable_vad (bool): 是否启用VAD检测, 默认False
            enable_playback (bool): 是否启用音频播放（解决VB-CABLE无声问题）, 默认True
        """
        super().__init__(daemon=True)
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.enable_vad = enable_vad
        self.enable_playback = enable_playback

        # 音频参数
        self.CHUNK = 1024                    # 每次读取的帧数
        self.FORMAT = pyaudio.paInt16        # 16-bit采样
        self.CHANNELS = 1                    # 方案H优化: 单声道（语音识别足够，减少50%文件大小）
        self.RATE = 16000                    # 方案H优化: 16kHz（Whisper训练采样率，减少66%文件大小）
        self.CHUNK_DURATION = 5              # 每块5秒

        # VAD相关
        self.vad_model = None
        self.vad_iterator = None
        self.is_silence = False              # 当前音频块是否为静音
        self.silence_count = 0               # 连续静音块计数
        self.total_chunks = 0                # 总音频块数
        self.skipped_chunks = 0              # 跳过的静音块数

        # 初始化VAD
        if self.enable_vad:
            self._init_vad()

    def _init_vad(self):
        """
        P0修复: VAD模型3次重试加载

        原因: 网络不稳定可能导致torch.hub.load失败
        """
        from silero_vad_iterator import FixedVADIterator, validate_vad_params

        for attempt in range(3):
            try:
                import torch

                # 加载Silero VAD模型
                self.vad_model, _ = torch.hub.load(
                    repo_or_dir="snakers4/silero-vad",
                    model="silero_vad",
                    force_reload=False,
                    onnx=False
                )

                # P0修复: VAD参数验证
                threshold = float(os.getenv('VAD_THRESHOLD', '0.5'))
                min_silence_ms = int(os.getenv('VAD_MIN_SILENCE_MS', '500'))

                is_valid, error_msg = validate_vad_params(threshold, min_silence_ms)
                if not is_valid:
                    print(f"[WARNING] {error_msg}, 使用默认值")
                    threshold = 0.5
                    min_silence_ms = 500

                # 创建VAD迭代器
                self.vad_iterator = FixedVADIterator(
                    model=self.vad_model,
                    threshold=threshold,
                    sampling_rate=16000,
                    min_silence_duration_ms=min_silence_ms,
                    speech_pad_ms=30
                )

                print(f"[INFO] VAD模型加载成功 (阈值: {threshold}, 最小静音: {min_silence_ms}ms)")
                return

            except Exception as e:
                print(f"[WARNING] VAD加载失败 (尝试{attempt+1}/3): {e}")
                if attempt == 2:
                    # 3次全部失败,禁用VAD
                    print("[WARNING] VAD加载失败,禁用VAD功能")
                    self.enable_vad = False
                    return
                time.sleep(1)  # 等待1秒后重试

    def find_cable_device(self, audio):
        """
        查找VB-Cable输出设备

        返回:
            int: 设备索引，未找到返回None
        """
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            # 关键词匹配: "cable output"
            if 'cable output' in info['name'].lower():
                print(f"[INFO] 找到VB-Cable设备: {info['name']} (索引: {i})")
                return i

        return None

    def capture_chunk(self, stream, playback_stream=None):
        """
        捕获固定5秒的音频块，同时播放（如果启用）

        参数:
            stream: 输入流（VB-CABLE）
            playback_stream: 播放流（默认音频设备），可选

        返回:
            bytes: 音频数据 (16kHz, 单声道, 16-bit)
        """
        frames = []

        # 计算需要读取的次数: 16000 / 1024 * 5 ≈ 78次
        num_chunks = int(self.RATE / self.CHUNK * self.CHUNK_DURATION)

        for _ in range(num_chunks):
            try:
                # P0修复: exception_on_overflow=False 避免缓冲区溢出异常
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                frames.append(data)

                # 同时播放音频（解决VB-CABLE无声问题）
                if self.enable_playback and playback_stream:
                    try:
                        playback_stream.write(data)
                    except Exception as e:
                        # 播放失败不影响捕获
                        if _ == 0:  # 只打印一次，避免刷屏
                            print(f"[WARNING] 音频播放异常: {e}")

            except Exception as e:
                # P0修复: 捕获异常，填充静音数据保持时序
                print(f"[WARNING] 音频流读取异常: {e}")
                # 填充静音: CHUNK帧 * CHANNELS * 2字节/帧
                silence = b'\x00' * (self.CHUNK * self.CHANNELS * 2)
                frames.append(silence)

                # 播放静音
                if self.enable_playback and playback_stream:
                    try:
                        playback_stream.write(silence)
                    except:
                        pass

        # 合并所有帧
        audio_data = b''.join(frames)

        # VAD检测 (如果启用)
        if self.enable_vad and self.vad_iterator:
            self._run_vad(audio_data)

        return audio_data

    def _run_vad(self, audio_data):
        """
        运行VAD检测

        P0修复:
        - 立体声转单声道使用int32避免溢出
        - 使用scipy.signal.resample_poly进行重采样

        参数:
            audio_data (bytes): 48kHz立体声音频数据
        """
        try:
            # 1. P0修复: 立体声 → 单声道 (必须用int32避免溢出!)
            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            stereo = audio_np.reshape(-1, 2)

            # ← 关键: 先转int32再取平均,避免两个int16相加溢出
            mono = stereo.astype(np.int32).mean(axis=1).astype(np.int16)

            # 2. P0修复: 48kHz → 16kHz (必须用scipy重采样!)
            # 原因: 简单抽取 mono[::3] 会导致混叠失真
            from scipy import signal
            audio_16k = signal.resample_poly(mono, up=1, down=3)

            # 3. 归一化到 float32 [-1, 1]
            audio_float32 = audio_16k.astype(np.float32) / 32768.0

            # 4. VAD检测
            result = self.vad_iterator(audio_float32, return_seconds=False)

            # 5. 静音判断: 连续2次静音(10秒)才标记为静音
            if result and 'end' in result:
                self.silence_count += 1
                if self.silence_count >= 2:
                    self.is_silence = True
            else:
                self.is_silence = False
                self.silence_count = 0

        except Exception as e:
            print(f"[WARNING] VAD检测异常: {e}")
            self.is_silence = False

    def is_silent_audio(self):
        """
        判断当前音频是否为静音

        返回:
            bool: True表示静音, False表示有语音
        """
        return self.is_silence and self.silence_count >= 2

    def get_vad_statistics(self):
        """
        获取VAD统计信息

        返回:
            dict: {'total': int, 'skipped': int, 'savings_percent': float}
        """
        if self.total_chunks == 0:
            return {'total': 0, 'skipped': 0, 'savings_percent': 0.0}

        savings = (self.skipped_chunks / self.total_chunks) * 100
        return {
            'total': self.total_chunks,
            'skipped': self.skipped_chunks,
            'savings_percent': savings
        }

    def run(self):
        """线程主循环 - 持续捕获音频并放入队列 + 音频播放"""
        audio = pyaudio.PyAudio()
        playback_stream = None

        try:
            # 1. 查找VB-Cable设备
            device_index = self.find_cable_device(audio)
            if device_index is None:
                raise Exception("未找到VB-Cable设备，请确保驱动已安装并重启电脑")

            # 2. 打开音频捕获流（VB-CABLE）
            stream = audio.open(
                format=self.FORMAT,
                channels=self.CHANNELS,
                rate=self.RATE,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.CHUNK
            )

            # 3. 打开音频播放流（默认设备）- 解决VB-CABLE无声问题
            if self.enable_playback:
                try:
                    playback_stream = audio.open(
                        format=self.FORMAT,
                        channels=self.CHANNELS,
                        rate=self.RATE,
                        output=True,
                        frames_per_buffer=self.CHUNK
                    )
                    print("[INFO] 音频播放已启用（解决VB-CABLE无声问题）")
                except Exception as e:
                    print(f"[WARNING] 无法打开播放流: {e}")
                    print("[WARNING] 将继续捕获但不播放音频")
                    playback_stream = None

            print("[INFO] 音频捕获线程已启动")

            # 4. 捕获循环
            while not self.stop_event.is_set():
                # 捕获5秒音频（同时播放）
                audio_chunk = self.capture_chunk(stream, playback_stream)

                # 统计
                self.total_chunks += 1

                # VAD静音检查
                if self.enable_vad and self.is_silent_audio():
                    self.skipped_chunks += 1
                    if self.total_chunks % 10 == 0:  # 每10块打印一次统计
                        stats = self.get_vad_statistics()
                        print(f"[VAD统计] 已跳过 {stats['skipped']}/{stats['total']} 块, "
                              f"节省 {stats['savings_percent']:.1f}% 成本")
                    continue  # 跳过静音块

                # P0修复: 使用timeout=1避免队列满时永久阻塞
                try:
                    self.audio_queue.put(audio_chunk, timeout=1)
                except queue.Full:
                    print("[WARNING] 队列已满，丢弃音频块")

            # 5. 清理
            stream.stop_stream()
            stream.close()

            if playback_stream:
                playback_stream.stop_stream()
                playback_stream.close()

            print("[INFO] 音频捕获线程已停止")

        finally:
            audio.terminate()
