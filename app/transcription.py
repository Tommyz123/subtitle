"""
转录翻译模块 - 支持双模式（API + 本地）

职责:
- 从队列获取音频块
- 调用 Whisper 转录（支持 API 或本地模型）
- 调用 DeepL API 翻译
- 通过回调返回结果

支持模式:
- API 模式: OpenAI Whisper API（云端）
- Local 模式: faster-whisper（本地，速度快 4 倍，零成本）

阶段2新增:
- API调用3次重试 + 指数退避
- VAD静音段跳过
- 详细错误日志
"""

import threading
import queue
import io
import wave
import time
import os
import numpy as np
import deepl
from concurrent.futures import ThreadPoolExecutor

# 条件导入：根据模式导入对应的库
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    FASTER_WHISPER_AVAILABLE = True
except ImportError:
    FASTER_WHISPER_AVAILABLE = False


class TranscriptionThread(threading.Thread):
    """转录翻译线程 - 处理音频块并返回字幕 + 重试机制（支持双模式）"""

    def __init__(self, audio_queue, stop_event, callback, openai_key, deepl_key,
                 source_lang="zh", target_lang="EN-US", audio_thread=None,
                 whisper_mode="api", local_model="small", local_device="auto",
                 local_compute_type="float16"):
        """
        参数:
            audio_queue (queue.Queue): 音频数据队列
            stop_event (threading.Event): 停止信号
            callback (callable): 回调函数 callback(original, translation)
            openai_key (str): OpenAI API Key（whisper_mode=api 时需要）
            deepl_key (str): DeepL API Key
            source_lang (str): 源语言代码 (Whisper支持的语言代码)
            target_lang (str): 目标语言代码 (DeepL支持的语言代码)
            audio_thread (AudioCaptureThread): 音频捕获线程引用 (用于VAD检查)
            whisper_mode (str): Whisper 模式 ('api' 或 'local')
            local_model (str): 本地模型大小 (tiny/base/small/medium/large-v2/large-v3)
            local_device (str): 本地模型设备 (auto/cuda/cpu)
            local_compute_type (str): 本地模型计算精度 (int8/float16/float32)
        """
        super().__init__(daemon=True)
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.callback = callback
        self.audio_thread = audio_thread  # 阶段2: 传入音频线程引用用于VAD检查

        # 语言配置
        self.source_lang = source_lang
        self.target_lang = target_lang

        # Whisper 模式配置
        self.whisper_mode = whisper_mode.lower()
        self.local_model_name = local_model
        self.local_device = local_device
        self.local_compute_type = local_compute_type

        # 初始化 Whisper 后端
        self._init_whisper_backend(openai_key)

        # 初始化 DeepL API 客户端
        self.deepl_translator = deepl.Translator(deepl_key)

        # 方案U优化: DeepL连接预热，消除冷启动延迟
        try:
            self.deepl_translator.translate_text(".", target_lang="EN-US")
            print("[INFO] DeepL连接预热完成")
        except:
            pass  # 忽略预热失败

        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1.0  # 秒

        # 方案E优化: 增加线程池worker数量，提升处理速度
        # max_workers=6: 最多6个API并发请求（处理能力翻倍）
        self.executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="APIWorker")

    def _init_whisper_backend(self, openai_key):
        """初始化 Whisper 后端（API 或本地模型）"""
        if self.whisper_mode == "api":
            # API 模式
            if not OPENAI_AVAILABLE:
                raise ImportError("OpenAI 库未安装，请运行: pip install openai")
            if not openai_key:
                raise ValueError("API 模式需要提供 OPENAI_API_KEY")

            self.openai_client = OpenAI(api_key=openai_key)
            self.local_model = None
            print(f"[INFO] Whisper 模式: API (云端)")

        elif self.whisper_mode == "local":
            # 本地模式
            if not FASTER_WHISPER_AVAILABLE:
                raise ImportError("faster-whisper 库未安装，请运行: pip install faster-whisper")

            # 设备检测
            device = self._detect_device() if self.local_device == "auto" else self.local_device

            # CPU 模式下强制使用 int8
            compute_type = self.local_compute_type
            if device == "cpu":
                compute_type = "int8"
                print(f"[INFO] CPU 模式下自动使用 int8 量化以提升速度")

            print(f"[INFO] Whisper 模式: 本地")
            print(f"[INFO] 正在加载模型: {self.local_model_name} (设备: {device}, 精度: {compute_type})")
            print(f"[INFO] 首次加载需要下载模型，请稍候...")

            try:
                self.local_model = WhisperModel(
                    self.local_model_name,
                    device=device,
                    compute_type=compute_type
                )
                print(f"[INFO] 本地 Whisper 模型加载成功")
            except Exception as e:
                print(f"[ERROR] 本地模型加载失败: {e}")
                raise

            self.openai_client = None
        else:
            raise ValueError(f"不支持的 Whisper 模式: {self.whisper_mode}，请使用 'api' 或 'local'")

    def _detect_device(self):
        """自动检测可用设备（GPU 优先）"""
        try:
            import torch
            if torch.cuda.is_available():
                print(f"[INFO] 检测到 CUDA GPU: {torch.cuda.get_device_name(0)}")
                return "cuda"
        except:
            pass

        print(f"[INFO] 未检测到 GPU，将使用 CPU")
        return "cpu"

    def transcribe(self, audio_data):
        """
        调用 Whisper 转录（支持 API 或本地模型，带重试机制）

        参数:
            audio_data (bytes): 16kHz 单声道音频数据

        返回:
            str: 转录文本，失败返回 None
        """
        if self.whisper_mode == "api":
            return self._transcribe_api(audio_data)
        elif self.whisper_mode == "local":
            return self._transcribe_local(audio_data)
        else:
            raise ValueError(f"未知的 Whisper 模式: {self.whisper_mode}")

    def _transcribe_api(self, audio_data):
        """使用 OpenAI Whisper API 转录"""
        # 1. 转换为WAV格式
        audio_file = io.BytesIO()
        with wave.open(audio_file, 'wb') as wf:
            wf.setnchannels(1)           # 方案H优化: 单声道（匹配audio_capture.py）
            wf.setsampwidth(2)           # 16-bit (2字节)
            wf.setframerate(16000)       # 方案H优化: 16kHz（匹配audio_capture.py）
            wf.writeframes(audio_data)

        # 2. 重置指针并设置文件名
        audio_file.seek(0)
        audio_file.name = "audio.wav"  # 必须设置name属性

        # 3. 重试循环
        for attempt in range(self.max_retries):
            try:
                # 方案G修复：添加language参数，避免自动语言检测的巨大开销
                # 诊断发现：自动检测导致30-40秒延迟（正常应为3-5秒）
                # 明确指定语言可节省20-35秒/块
                # 方案T优化：使用text响应格式，比JSON格式快约2%
                response = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                    language=self.source_lang,  # 使用用户选择的源语言
                    response_format="text"  # 使用text格式，比JSON快
                )

                # 调试日志：验证转录结果
                print(f"[DEBUG] Whisper API 转录: '{response[:50]}...' (长度: {len(response)})")

                return response  # 直接返回字符串

            except Exception as e:
                print(f"[ERROR] Whisper API调用失败 (尝试{attempt+1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    # 指数退避: 1秒, 2秒, 4秒
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"[INFO] {delay}秒后重试...")
                    time.sleep(delay)

                    # 重置文件指针
                    audio_file.seek(0)
                else:
                    print(f"[ERROR] Whisper API调用失败 {self.max_retries} 次,放弃该音频块")
                    return None

    def _transcribe_local(self, audio_data):
        """使用本地 faster-whisper 模型转录"""
        try:
            # 1. 将 bytes 转换为 numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16)

            # 2. 归一化到 float32 [-1.0, 1.0]
            audio_float32 = audio_np.astype(np.float32) / 32768.0

            # 3. 调用本地模型（faster-whisper 直接接受 numpy array）
            segments, info = self.local_model.transcribe(
                audio_float32,
                language=self.source_lang,
                beam_size=5,  # 平衡准确率和速度
                vad_filter=False,  # 我们已经有自己的 VAD
                without_timestamps=True  # 不需要时间戳，提升速度
            )

            # 4. 合并所有片段
            text = " ".join([segment.text for segment in segments])

            # 调试日志
            print(f"[DEBUG] 本地 Whisper 转录: '{text[:50]}...' (长度: {len(text)})")
            print(f"[DEBUG] 检测语言: {info.language} (概率: {info.language_probability:.2f})")

            return text.strip()

        except Exception as e:
            print(f"[ERROR] 本地 Whisper 转录失败: {e}")
            return None

    def translate(self, text):
        """
        调用DeepL API翻译 (阶段2: 3次重试 + 指数退避)

        参数:
            text (str): 原文

        返回:
            str: 翻译文本，失败返回None
        """
        for attempt in range(self.max_retries):
            try:
                # 使用用户选择的目标语言
                result = self.deepl_translator.translate_text(
                    text,
                    target_lang=self.target_lang  # 使用用户选择的目标语言
                )
                return result.text

            except Exception as e:
                print(f"[ERROR] DeepL API调用失败 (尝试{attempt+1}/{self.max_retries}): {e}")

                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    print(f"[INFO] {delay}秒后重试...")
                    time.sleep(delay)
                else:
                    print(f"[ERROR] DeepL API调用失败 {self.max_retries} 次,放弃该翻译")
                    return None

    def run(self):
        """线程主循环 - 获取音频→转录→翻译→回调 (方案E: 取消批量处理)"""
        print("[INFO] 转录翻译线程已启动 (并发模式: 最多6个API同时调用)")

        while not self.stop_event.is_set():
            try:
                # 方案E优化: 取消批量处理，每次只获取1个音频块
                # 立即提交到线程池处理，不等待完成
                # 线程池会自动管理6个worker的并发调度
                audio_data = self.audio_queue.get(timeout=1)

                # 方案G诊断: 监控队列堆积情况
                audio_q_size = self.audio_queue.qsize()
                pool_q_size = self.executor._work_queue.qsize()
                total_pending = audio_q_size + pool_q_size + 6  # +6是正在6个worker中处理的块
                print(f"[📊 QUEUE] audio={audio_q_size} | pool={pool_q_size} | processing=6 | total≈{total_pending}")

                # 立即提交处理，不阻塞等待结果
                self.executor.submit(self._process_audio_chunk, audio_data)

            except queue.Empty:
                continue

        # 清理线程池
        print("[INFO] 转录翻译线程停止中，等待所有API调用完成...")
        self.executor.shutdown(wait=True, cancel_futures=False)
        print("[INFO] 转录翻译线程已停止")

    def _process_audio_chunk(self, audio_data):
        """
        处理单个音频块

        参数:
            audio_data (bytes): 音频数据
        """
        # 方案G诊断: 记录开始时间
        chunk_start = time.time()

        # 阶段2: VAD静音段检查
        if self.audio_thread and hasattr(self.audio_thread, 'is_silent_audio'):
            if self.audio_thread.is_silent_audio():
                print("[INFO] [VAD] 跳过静音段,节省API成本")
                return

        # 2. 转录 (带重试) - 记录耗时
        t1 = time.time()
        original_text = self.transcribe(audio_data)
        whisper_time = time.time() - t1

        if not original_text or not original_text.strip():
            return

        # 3. 翻译 (带重试) - 记录耗时
        t2 = time.time()
        translated_text = self.translate(original_text)
        deepl_time = time.time() - t2

        if not translated_text:
            return

        # 计算总耗时
        total_time = time.time() - chunk_start

        # 方案G诊断: 关键性能日志
        print(f"[⏱️ TIMING] Whisper: {whisper_time:.2f}s | DeepL: {deepl_time:.2f}s | Total: {total_time:.2f}s")

        # 4. 回调GUI主线程
        self.callback(original_text, translated_text)
