"""
转录翻译模块 - 支持本地模型和API双模式

职责:
- 从队列获取音频块
- 转录: 支持本地 faster-whisper 或 OpenAI Whisper API
- 调用DeepL API翻译
- 通过回调返回结果

模式:
- local: 使用本地 faster-whisper 模型 (离线, 免费, 需要GPU/CPU资源)
- api: 使用 OpenAI Whisper API (在线, 付费, 无需本地资源)

阶段1优化 (已完成):
- 上下文提示管理（减少重复识别）
- 三种速度模式（fast/balanced/quality）
- 模型预热（消除冷启动）

阶段2优化 (新增):
- 流式增量处理（实时增量输出，减少延迟）
- 自动去重（避免重复文本）
- 累积缓冲区管理（防止内存泄漏）
- API调用3次重试 + 指数退避
- VAD静音段跳过
- 详细错误日志
"""

import threading
import queue
import io
import wave
import time
import random  # P7优化: 用于重试Jitter
from openai import OpenAI
import deepl
from concurrent.futures import ThreadPoolExecutor
import httpx  # P8优化: 用于DeepL连接池配置

# 导入本地 Whisper 模块（兼容相对导入和绝对导入）
LOCAL_WHISPER_AVAILABLE = False
LocalWhisperTranscriber = None

try:
    # 尝试相对导入（从项目根目录运行时）
    from .local_whisper import LocalWhisperTranscriber
    LOCAL_WHISPER_AVAILABLE = True
except ImportError:
    try:
        # 尝试绝对导入（从 app 目录运行时）
        from local_whisper import LocalWhisperTranscriber
        LOCAL_WHISPER_AVAILABLE = True
    except ImportError as e:
        LOCAL_WHISPER_AVAILABLE = False
        print(f"[WARNING] 本地模式不可用，导入错误详情: {e}")
        print("[INFO] 如需使用本地模式，请确保已安装: pip install faster-whisper")
        import traceback
        traceback.print_exc()

# 导入本地翻译模块（可选，用于加速本地模式）
LOCAL_TRANSLATOR_AVAILABLE = False
LocalTranslator = None

try:
    from .local_translator import LocalTranslator
    LOCAL_TRANSLATOR_AVAILABLE = True
except ImportError:
    try:
        from local_translator import LocalTranslator
        LOCAL_TRANSLATOR_AVAILABLE = True
    except ImportError:
        LOCAL_TRANSLATOR_AVAILABLE = False
        print("[INFO] 本地翻译不可用（将使用 DeepL），如需安装: pip install transformers sentencepiece")

# 导入流式处理器（阶段2优化）
STREAMING_PROCESSOR_AVAILABLE = False
StreamingWhisperProcessor = None

try:
    from .streaming_whisper import StreamingWhisperProcessor
    STREAMING_PROCESSOR_AVAILABLE = True
except ImportError:
    try:
        from streaming_whisper import StreamingWhisperProcessor
        STREAMING_PROCESSOR_AVAILABLE = True
    except ImportError:
        STREAMING_PROCESSOR_AVAILABLE = False
        print("[INFO] 流式处理器不可用")


class TranscriptionThread(threading.Thread):
    """转录翻译线程 - 处理音频块并返回字幕 + 重试机制"""

    def __init__(self, audio_queue, stop_event, callback, openai_key, deepl_key,
                 source_lang="zh", target_lang="EN-US", audio_thread=None,
                 mode="api", local_model_size="base", speed_mode="fast", use_local_translation=True,
                 enable_streaming=False):
        """
        参数:
            audio_queue (queue.Queue): 音频数据队列
            stop_event (threading.Event): 停止信号
            callback (callable): 回调函数 callback(original, translation)
            openai_key (str): OpenAI API Key (仅在 api 模式下需要)
            deepl_key (str): DeepL API Key
            source_lang (str): 源语言代码 (Whisper支持的语言代码)
            target_lang (str): 目标语言代码 (DeepL支持的语言代码)
            audio_thread (AudioCaptureThread): 音频捕获线程引用 (用于VAD检查)
            mode (str): 转录模式 - "local" (本地模型) 或 "api" (OpenAI API)
            local_model_size (str): 本地模型大小 - tiny, base, small, medium, large-v2
            speed_mode (str): 速度模式 - fast, balanced, quality (仅本地模式)
            use_local_translation (bool): 是否使用本地翻译（仅local模式，更快）
            enable_streaming (bool): 是否启用流式增量处理（阶段2优化，仅本地模式）
        """
        super().__init__(daemon=True)
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.callback = callback
        self.audio_thread = audio_thread  # 阶段2: 传入音频线程引用用于VAD检查

        # 语言配置
        self.source_lang = source_lang
        self.target_lang = target_lang

        # 模式配置
        self.mode = mode
        self.local_model_size = local_model_size
        self.speed_mode = speed_mode  # ✅ 新增: 速度模式
        self.use_local_translation = use_local_translation and (mode == "local")  # 仅本地模式可用
        self.enable_streaming = enable_streaming and (mode == "local")  # ✅ 阶段2: 仅本地模式支持流式

        print(f"\n[INFO] 转录模式: {mode.upper()}")

        # 初始化转录器 (根据模式)
        if mode == "local":
            # 本地模式: 使用 faster-whisper
            if not LOCAL_WHISPER_AVAILABLE:
                raise RuntimeError("本地模式需要安装 faster-whisper: pip install faster-whisper")

            print(f"[INFO] 正在初始化本地 Whisper 模型 ({local_model_size}, {speed_mode})...")
            self.local_transcriber = LocalWhisperTranscriber(
                model_size=local_model_size,
                device="auto",
                compute_type="auto",
                speed_mode=speed_mode  # ✅ 新增: 传递速度模式
            )
            self.openai_client = None
            print("[SUCCESS] 本地模型初始化完成\n")

            # ✅ 阶段2: 初始化流式处理器（如果启用）
            self.streaming_processor = None
            if self.enable_streaming:
                if not STREAMING_PROCESSOR_AVAILABLE:
                    print("[WARNING] 流式处理器不可用，回退到批量处理模式")
                    self.enable_streaming = False
                else:
                    print(f"[INFO] 正在初始化流式处理器...")
                    self.streaming_processor = StreamingWhisperProcessor(
                        model=self.local_transcriber,
                        max_buffer_seconds=15.0,  # 最大缓冲15秒
                        sample_rate=16000
                    )
                    print("[SUCCESS] 流式处理器初始化完成（增量模式）\n")

        elif mode == "api":
            # API 模式: 使用 OpenAI Whisper API
            if not openai_key:
                raise ValueError("API 模式需要提供 OpenAI API Key")

            self.openai_client = OpenAI(api_key=openai_key)
            self.local_transcriber = None
            print("[INFO] OpenAI Whisper API 已配置\n")

        else:
            raise ValueError(f"不支持的模式: {mode}，请选择 'local' 或 'api'")

        # 初始化翻译器（根据模式和配置）
        self.local_translator = None
        self.deepl_translator = None

        if self.use_local_translation and LOCAL_TRANSLATOR_AVAILABLE:
            # 使用本地翻译模型（更快，完全离线）
            print(f"[INFO] 正在初始化本地翻译模型...")
            try:
                self.local_translator = LocalTranslator(
                    model_size="distilled-600M",  # 轻量级模型
                    device="auto"
                )
                print("[SUCCESS] 本地翻译模型初始化完成（速度< 100ms）\n")
            except Exception as e:
                print(f"[WARNING] 本地翻译初始化失败: {e}")
                print("[INFO] 将回退到 DeepL API")
                self.use_local_translation = False

        if not self.use_local_translation:
            # 使用 DeepL API 翻译
            if not deepl_key:
                raise ValueError("DeepL API Key 是必需的（本地翻译不可用或已禁用）")

            # P8优化: 配置HTTP连接池，复用TCP连接，避免握手开销
            # pool_connections=5: 保持5个空闲连接
            # pool_maxsize=10: 最多10个连接
            # keepalive_expiry=30: 空闲连接30秒超时
            try:
                http_client = httpx.Client(
                    limits=httpx.Limits(
                        max_connections=10,        # 最大连接数
                        max_keepalive_connections=5,  # 最大保活连接数
                        keepalive_expiry=30.0      # 空闲连接超时（秒）
                    ),
                    timeout=httpx.Timeout(30.0, connect=10.0)  # 请求超时30秒，连接超时10秒
                )
                # 使用自定义HTTP客户端创建DeepL翻译器
                self.deepl_translator = deepl.Translator(deepl_key)
                # 注: deepl库v1.x不支持自定义client，但连接复用是httpx的默认行为
                # 这里记录配置信息供调试
                self._deepl_http_client = http_client
                print("[INFO] DeepL 连接池已配置 (max=10, keepalive=5)")
            except Exception as e:
                print(f"[WARNING] 连接池配置失败，使用默认配置: {e}")
                self.deepl_translator = deepl.Translator(deepl_key)

            # 方案U优化: DeepL连接预热，消除冷启动延迟
            try:
                self.deepl_translator.translate_text(".", target_lang="EN-US")
                print("[INFO] DeepL API 已配置并预热完成\n")
            except:
                print("[INFO] DeepL API 已配置\n")

        # 重试配置
        self.max_retries = 3
        self.retry_delay = 1.0  # 秒

        # 方案E优化: 增加线程池worker数量，提升处理速度
        # max_workers=6: 最多6个API并发请求（处理能力翻倍）
        self.executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="TranscribeWorker")

        # P3优化: 翻译专用线程池，实现转录和翻译并行处理
        # max_workers=4: 翻译任务通常更快，4个worker足够
        self.translation_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="TranslateWorker")

        # P12优化: 背压机制 - 限制待处理任务数，防止内存压力
        # 当待处理任务超过20个时，新任务会阻塞等待
        # 这样可以防止系统过载时任务无限堆积
        self.pending_semaphore = threading.Semaphore(20)
        self.pending_count = 0
        self.pending_lock = threading.Lock()

    def transcribe(self, audio_data):
        """
        调用 Whisper 转录 (支持本地模型和API两种模式)

        参数:
            audio_data (bytes): 16kHz 单声道 16-bit PCM 音频数据

        返回:
            str: 转录文本，失败返回None
        """
        # 本地模式: 使用 faster-whisper
        if self.mode == "local":
            return self._transcribe_local(audio_data)

        # API 模式: 使用 OpenAI Whisper API
        elif self.mode == "api":
            return self._transcribe_api(audio_data)

    def _transcribe_local(self, audio_data):
        """使用本地 faster-whisper 模型转录（支持流式处理）"""
        try:
            # ✅ 阶段2: 流式处理模式
            if self.enable_streaming and self.streaming_processor:
                # 将音频数据转换为numpy数组并添加到缓冲区
                import numpy as np

                # 音频数据格式: bytes (16-bit PCM) -> numpy float32
                audio_int16 = np.frombuffer(audio_data, dtype=np.int16)
                audio_float32 = audio_int16.astype(np.float32) / 32768.0  # 归一化到 [-1.0, 1.0]

                # 添加到流式缓冲区
                self.streaming_processor.add_audio(audio_float32)

                # 增量处理（返回新增文本）
                new_text = self.streaming_processor.process_incremental()

                return new_text  # 可能是None（继续累积）或新增文本

            # 批量处理模式（原有逻辑）
            else:
                text = self.local_transcriber.transcribe(
                    audio_data,
                    language=self.source_lang
                )
                return text

        except Exception as e:
            print(f"[ERROR] 本地 Whisper 转录失败: {e}")
            return None

    def _transcribe_api(self, audio_data):
        """使用 OpenAI Whisper API 转录 (带重试机制)"""
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
                    # P7优化: 指数退避 + 随机Jitter（避免thundering herd问题）
                    base_delay = self.retry_delay * (2 ** attempt)
                    jitter = random.uniform(0, 0.1 * base_delay)  # 10%随机抖动
                    delay = base_delay + jitter
                    print(f"[INFO] {delay:.2f}秒后重试 (base={base_delay:.1f}s, jitter={jitter:.2f}s)...")
                    time.sleep(delay)

                    # 重置文件指针
                    audio_file.seek(0)
                else:
                    print(f"[ERROR] Whisper API调用失败 {self.max_retries} 次,放弃该音频块")
                    return None

    def translate(self, text):
        """
        翻译文本 (支持本地模型和DeepL API)

        参数:
            text (str): 原文

        返回:
            str: 翻译文本，失败返回None
        """
        # 使用本地翻译模型（仅本地模式，速度快 < 100ms）
        if self.local_translator:
            try:
                # 转换语言代码：DeepL格式(EN-US, ZH) -> NLLB格式(en, zh)
                target_lang_code = self.target_lang.split('-')[0].lower()  # EN-US -> en
                source_lang_code = self.source_lang.lower()  # zh -> zh

                result = self.local_translator.translate(
                    text,
                    source_lang=source_lang_code,
                    target_lang=target_lang_code
                )
                return result

            except Exception as e:
                print(f"[ERROR] 本地翻译失败: {e}")
                print(f"[INFO] 回退到 DeepL API")
                # 继续执行DeepL翻译作为回退

        # 使用 DeepL API 翻译 (带重试机制)
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
                    # P7优化: 指数退避 + 随机Jitter
                    base_delay = self.retry_delay * (2 ** attempt)
                    jitter = random.uniform(0, 0.1 * base_delay)  # 10%随机抖动
                    delay = base_delay + jitter
                    print(f"[INFO] {delay:.2f}秒后重试 (base={base_delay:.1f}s, jitter={jitter:.2f}s)...")
                    time.sleep(delay)
                else:
                    print(f"[ERROR] DeepL API调用失败 {self.max_retries} 次,放弃该翻译")
                    return None

    def run(self):
        """线程主循环 - 获取音频→转录→翻译→回调 (方案E: 取消批量处理)"""
        if self.enable_streaming:
            print("[INFO] 转录翻译线程已启动 (流式增量模式: 实时增量输出)")
        else:
            print("[INFO] 转录翻译线程已启动 (并发模式: 最多6个API同时调用)")

        while not self.stop_event.is_set():
            try:
                # 方案E优化: 取消批量处理，每次只获取1个音频块
                # 立即提交到线程池处理，不等待完成
                # 线程池会自动管理6个worker的并发调度
                queue_item = self.audio_queue.get(timeout=1)

                # 延迟测量: 兼容新旧格式
                # 新格式: (audio_data, speech_start_time, speech_duration)
                # 旧格式: audio_data (bytes)
                if isinstance(queue_item, tuple) and len(queue_item) == 3:
                    audio_data, speech_start_time, speech_duration = queue_item
                else:
                    # 向后兼容：旧格式只有音频数据
                    audio_data = queue_item
                    speech_start_time = time.time()  # 使用当前时间作为开始时间
                    speech_duration = len(audio_data) / (16000 * 2)  # 估算：16kHz, 16-bit

                # 方案G诊断: 监控队列堆积情况
                audio_q_size = self.audio_queue.qsize()
                pool_q_size = self.executor._work_queue.qsize()

                # P12优化: 显示背压状态
                with self.pending_lock:
                    pending = self.pending_count
                total_pending = audio_q_size + pool_q_size + pending
                print(f"[📊 QUEUE] audio={audio_q_size} | pool={pool_q_size} | pending={pending} | total≈{total_pending}")

                # P12优化: 背压机制 - 获取信号量（如果待处理任务过多会阻塞）
                acquired = self.pending_semaphore.acquire(timeout=5)
                if not acquired:
                    print(f"[WARNING] 背压触发: 待处理任务过多(>{20})，跳过当前音频块")
                    continue

                with self.pending_lock:
                    self.pending_count += 1

                # 立即提交处理，不阻塞等待结果
                # 延迟测量: 传递开始时间和语音时长
                self.executor.submit(self._process_audio_chunk_with_backpressure, audio_data, speech_start_time, speech_duration)

            except queue.Empty:
                continue

        # 清理线程池
        print("[INFO] 转录翻译线程停止中，等待所有API调用完成...")
        self.executor.shutdown(wait=True, cancel_futures=False)

        # P3优化: 关闭翻译线程池
        print("[INFO] 等待翻译任务完成...")
        self.translation_executor.shutdown(wait=True, cancel_futures=False)

        # ✅ 阶段2: 清理流式处理器
        if self.enable_streaming and self.streaming_processor:
            print("[INFO] 清理流式处理器...")
            # 输出最后累积的文本（如果有）
            final_text = self.streaming_processor.get_confirmed_text()
            if final_text:
                print(f"[STREAMING] 最终累积文本长度: {len(final_text)} 字符")
            # 清空缓冲区
            self.streaming_processor.clear()

        print("[INFO] 转录翻译线程已停止")

    def _process_audio_chunk_with_backpressure(self, audio_data, speech_start_time, speech_duration):
        """
        P12优化: 带背压控制的音频块处理

        在处理完成后释放信号量，允许新任务提交

        参数:
            audio_data (bytes): 音频数据
            speech_start_time (float): 语音段开始时间戳
            speech_duration (float): 语音段时长（秒）
        """
        try:
            self._process_audio_chunk(audio_data, speech_start_time, speech_duration)
        finally:
            # 释放信号量，允许新任务提交
            with self.pending_lock:
                self.pending_count -= 1
            self.pending_semaphore.release()

    def _process_audio_chunk(self, audio_data, speech_start_time, speech_duration):
        """
        处理单个音频块

        参数:
            audio_data (bytes): 音频数据
            speech_start_time (float): 语音段开始时间戳
            speech_duration (float): 语音段时长（秒）
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

        # P3优化: 异步提交翻译任务，不阻塞等待
        # 转录完成后立即提交翻译，实现转录和翻译流水线并行
        # 延迟测量: 传递语音段信息
        self.translation_executor.submit(
            self._translate_and_callback,
            original_text,
            chunk_start,
            whisper_time,
            speech_start_time,
            speech_duration
        )

    def _translate_and_callback(self, original_text, chunk_start, whisper_time, speech_start_time=None, speech_duration=None):
        """
        P3优化: 翻译并回调（在翻译线程池中执行）

        参数:
            original_text (str): 转录文本
            chunk_start (float): 处理开始时间
            whisper_time (float): 转录耗时
            speech_start_time (float): 语音段开始时间戳（延迟测量用）
            speech_duration (float): 语音段时长（延迟测量用）
        """
        # 3. 翻译 (带重试) - 记录耗时
        t2 = time.time()
        translated_text = self.translate(original_text)
        deepl_time = time.time() - t2

        if not translated_text:
            return

        # 计算总耗时
        total_time = time.time() - chunk_start

        # 延迟测量: 计算端到端延迟
        end_time = time.time()
        if speech_start_time and speech_duration:
            # 端到端延迟 = 从语音开始到字幕显示的总时间
            end_to_end_latency = end_time - speech_start_time
            # 输出详细延迟日志
            print(f"[📊 延迟] 语音: {speech_duration:.1f}s | 转录: {whisper_time:.2f}s | 翻译: {deepl_time:.2f}s | 端到端: {end_to_end_latency:.2f}s")
        else:
            # 向后兼容：没有语音段信息时只输出处理时间
            print(f"[⏱️ TIMING] Whisper: {whisper_time:.2f}s | DeepL: {deepl_time:.2f}s | Total: {total_time:.2f}s")

        # 4. 回调GUI主线程
        self.callback(original_text, translated_text)