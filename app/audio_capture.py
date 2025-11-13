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

    def __init__(self, audio_queue, stop_event, enable_vad=False, enable_playback=False, enable_smart_segmentation=False):
        """
        参数:
            audio_queue (queue.Queue): 音频数据队列
            stop_event (threading.Event): 停止信号
            enable_vad (bool): 是否启用VAD检测, 默认False
            enable_playback (bool): 是否启用音频播放, 默认False
                                   注意：不要与Windows"侦听此设备"同时使用
            enable_smart_segmentation (bool): 是否启用智能分段, 默认False
        """
        super().__init__(daemon=True)
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.enable_vad = enable_vad
        self.enable_playback = enable_playback
        self.enable_smart_segmentation = enable_smart_segmentation

        # 音频参数
        self.CHUNK = 1024                    # 每次读取的帧数
        self.FORMAT = pyaudio.paInt16        # 16-bit采样
        self.CHANNELS = 1                    # 方案H优化: 单声道（语音识别足够，减少50%文件大小）
        self.RATE = 16000                    # 方案H优化: 16kHz（Whisper训练采样率，减少66%文件大小）
        self.CHUNK_DURATION = 5              # 每块5秒 (固定模式)

        # VAD相关
        self.vad_model = None
        self.vad_iterator = None
        self.is_silence = False              # 当前音频块是否为静音
        self.silence_count = 0               # 连续静音块计数
        self.total_chunks = 0                # 总音频块数
        self.skipped_chunks = 0              # 跳过的静音块数

        # 智能分段相关
        self.speech_buffer = []              # 语音缓冲区
        self.is_speaking = False             # 是否正在说话
        self.silence_frames = 0              # 连续静音帧数
        self.min_speech_duration_ms = float(os.getenv('MIN_SPEECH_DURATION', '500'))  # 最小语音段500ms
        self.max_speech_duration_ms = float(os.getenv('MAX_SPEECH_DURATION', '10000'))  # 最大语音段10秒
        self.silence_threshold_ms = float(os.getenv('SILENCE_THRESHOLD', '500'))  # 停顿阈值500ms
        self.vad_sensitivity = float(os.getenv('VAD_SENSITIVITY', '0.4'))  # VAD灵敏度

        # 初始化VAD
        if self.enable_vad or self.enable_smart_segmentation:
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

    def find_physical_playback_device(self, audio):
        """
        查找物理播放设备（排除虚拟设备）

        返回:
            int: 设备索引，未找到返回None（将使用默认设备）
        """
        # 需要排除的虚拟设备关键词
        virtual_keywords = ['cable', 'virtual', 'voicemeeter', 'vb-audio', 'loopback']

        default_output = audio.get_default_output_device_info()

        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)

            # 必须是输出设备
            if info['maxOutputChannels'] == 0:
                continue

            device_name_lower = info['name'].lower()

            # 排除虚拟设备
            is_virtual = any(keyword in device_name_lower for keyword in virtual_keywords)
            if is_virtual:
                continue

            # 找到物理设备
            print(f"[INFO] 找到物理播放设备: {info['name']} (索引: {i})")
            return i

        # 如果没找到物理设备，返回None（会使用默认设备）
        print(f"[WARNING] 未找到物理播放设备，将使用默认设备: {default_output['name']}")
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

    def detect_speech_activity(self, audio_chunk):
        """
        智能分段: 检测音频块是否包含语音活动

        参数:
            audio_chunk (bytes): 音频数据块

        返回:
            bool: True表示有语音, False表示静音
        """
        try:
            # 转换为numpy数组
            audio_np = np.frombuffer(audio_chunk, dtype=np.int16)
            audio_float = audio_np.astype(np.float32) / 32768.0

            # 使用VAD检测
            if self.vad_iterator:
                speech_dict = self.vad_iterator(audio_float, return_seconds=False)
                # None表示语音继续, 有dict表示检测到结束
                return speech_dict is None

            return False

        except Exception as e:
            print(f"[WARNING] 语音活动检测异常: {e}")
            return True  # 出错时默认认为有语音，避免丢失数据

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

    def _smart_segmentation_loop(self, stream, playback_stream=None):
        """
        智能分段循环：根据说话节奏动态切分音频

        参数:
            stream: 输入流
            playback_stream: 播放流（可选）
        """
        # 读取100ms的小块音频 (16000 Hz * 0.1s / 1024 ≈ 1.5个CHUNK)
        chunk_100ms_frames = int(self.RATE * 0.1 / self.CHUNK)  # 每100ms需要读取的CHUNK数量

        for _ in range(chunk_100ms_frames):
            if self.stop_event.is_set():
                return

            try:
                # 读取音频
                data = stream.read(self.CHUNK, exception_on_overflow=False)

                # 同时播放
                if self.enable_playback and playback_stream:
                    try:
                        playback_stream.write(data)
                    except:
                        pass

                # VAD检测语音活动
                has_speech = self.detect_speech_activity(data)

                if has_speech:
                    # 检测到语音 - 积累到缓冲区
                    self.speech_buffer.append(data)
                    self.is_speaking = True
                    self.silence_frames = 0

                else:
                    # 静音帧
                    if self.is_speaking:
                        # 正在说话 → 刚停顿
                        self.silence_frames += 1
                        silence_ms = self.silence_frames * 100  # 100ms per frame

                        # 检查是否达到停顿阈值
                        if silence_ms >= self.silence_threshold_ms:
                            # 停顿时间足够 → 发送语音段
                            self._flush_speech_buffer()
                    else:
                        # 一直静音，继续等待
                        pass

                # 防止语音段过长（超过最大时长强制切分）
                buffer_duration_ms = len(self.speech_buffer) * 100
                if buffer_duration_ms >= self.max_speech_duration_ms:
                    print(f"[智能分段] 语音段超过最大时长 {self.max_speech_duration_ms}ms，强制切分")
                    self._flush_speech_buffer()

            except Exception as e:
                print(f"[WARNING] 智能分段读取异常: {e}")
                # 填充静音
                silence = b'\x00' * (self.CHUNK * self.CHANNELS * 2)
                if self.enable_playback and playback_stream:
                    try:
                        playback_stream.write(silence)
                    except:
                        pass

    def _flush_speech_buffer(self):
        """
        发送缓冲区中的语音段到队列
        """
        if not self.speech_buffer:
            return

        # 检查最小时长
        buffer_duration_ms = len(self.speech_buffer) * 100
        if buffer_duration_ms < self.min_speech_duration_ms:
            print(f"[智能分段] 语音段过短 ({buffer_duration_ms}ms < {self.min_speech_duration_ms}ms)，忽略")
            self.speech_buffer = []
            self.is_speaking = False
            self.silence_frames = 0
            return

        # 合并音频块
        audio_data = b''.join(self.speech_buffer)
        duration_sec = buffer_duration_ms / 1000

        # 发送到队列
        try:
            self.audio_queue.put(audio_data, timeout=1)
            print(f"[智能分段] ✅ 检测到停顿，发送 {duration_sec:.1f}秒语音段")
            self.total_chunks += 1
        except queue.Full:
            print("[WARNING] 队列已满，丢弃语音段")

        # 重置缓冲区
        self.speech_buffer = []
        self.is_speaking = False
        self.silence_frames = 0

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

            # 3. 打开音频播放流（物理设备）- 解决VB-CABLE无声问题
            if self.enable_playback:
                try:
                    # 查找物理播放设备（避免音频循环）
                    playback_device_index = self.find_physical_playback_device(audio)

                    # 优化：使用更小的缓冲区降低播放延迟
                    # CHUNK=1024 @ 16kHz = ~64ms延迟
                    # 减小到 512 = ~32ms延迟（几乎无感）
                    playback_chunk = 512  # 更小的缓冲区，更低延迟

                    # 明确指定输出设备，避免输出到 CABLE Input 导致音频循环
                    playback_stream = audio.open(
                        format=self.FORMAT,
                        channels=self.CHANNELS,
                        rate=self.RATE,
                        output=True,
                        output_device_index=playback_device_index,  # 指定物理设备
                        frames_per_buffer=playback_chunk  # 使用更小的缓冲区
                    )
                    print("[INFO] 音频播放已启用（输出到物理设备，避免音频循环）")
                except Exception as e:
                    print(f"[WARNING] 无法打开播放流: {e}")
                    print("[WARNING] 将继续捕获但不播放音频")
                    playback_stream = None

            print("[INFO] 音频捕获线程已启动")
            if self.enable_smart_segmentation:
                print("[INFO] 智能分段模式已启用")

            # 4. 捕获循环
            while not self.stop_event.is_set():
                if self.enable_smart_segmentation:
                    # 智能分段模式：流式捕获，根据说话节奏动态切分
                    self._smart_segmentation_loop(stream, playback_stream)
                else:
                    # 固定分段模式：传统的5秒固定切分
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
