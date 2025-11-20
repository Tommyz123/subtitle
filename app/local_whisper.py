"""
本地 Faster-Whisper 转录模块

职责:
- 使用本地 faster-whisper 模型进行转录
- 支持多种模型大小 (tiny, base, small, medium, large)
- 提供与 API 模式相同的接口
- GPU/CPU 自动检测和优化
"""

import io
import wave
import numpy as np
from faster_whisper import WhisperModel
import threading
import os


class LocalWhisperTranscriber:
    """本地 Faster-Whisper 转录器"""

    # 模型大小和性能参考
    MODEL_INFO = {
        "tiny": {"params": "39M", "speed": "~32x", "vram": "~1GB"},
        "base": {"params": "74M", "speed": "~16x", "vram": "~1GB"},
        "small": {"params": "244M", "speed": "~6x", "vram": "~2GB"},
        "medium": {"params": "769M", "speed": "~2x", "vram": "~5GB"},
        "large-v2": {"params": "1550M", "speed": "~1x", "vram": "~10GB"},
    }

    # ✅ 新增: 三种速度预设（参考 WhisperLiveKit 参数配置）
    SPEED_PRESETS = {
        "fast": {  # 极速模式 - 适合实时字幕
            "beam_size": 1,
            "best_of": 1,
            "temperature": 0.0,
            "patience": 1.0,
            "compression_ratio_threshold": 2.4,
            "no_speech_threshold": 0.6,
            "description": "最快速度，质量略降（-10%），延迟-40%"
        },
        "balanced": {  # 平衡模式 - 推荐默认
            "beam_size": 3,
            "best_of": 1,
            "temperature": 0.0,
            "patience": 1.0,
            "compression_ratio_threshold": 2.4,
            "no_speech_threshold": 0.5,
            "description": "速度与质量平衡，延迟-20%"
        },
        "quality": {  # 质量模式 - 追求准确度
            "beam_size": 5,
            "best_of": 2,
            "temperature": [0.0, 0.2, 0.4],
            "patience": 2.0,
            "compression_ratio_threshold": 2.2,
            "no_speech_threshold": 0.4,
            "description": "最高质量，延迟+20%"
        }
    }

    def __init__(self, model_size="base", device="auto", compute_type="auto", speed_mode="fast"):
        """
        初始化本地 Whisper 模型

        参数:
            model_size (str): 模型大小 - tiny, base, small, medium, large-v2
            device (str): 设备 - auto, cuda, cpu
            compute_type (str): 计算类型 - auto, float16, int8
            speed_mode (str): 速度模式 - fast, balanced, quality
        """
        self.model_size = model_size
        self.device = self._detect_device(device)
        self.compute_type = self._detect_compute_type(compute_type, self.device)
        self.model = None
        self.model_lock = threading.Lock()  # 线程安全

        # ✅ 新增: 速度模式配置
        self.speed_mode = speed_mode if speed_mode in self.SPEED_PRESETS else "fast"
        self.transcribe_params = self.SPEED_PRESETS[self.speed_mode].copy()
        self.transcribe_params.pop("description", None)  # 移除描述字段

        # ✅ 新增: 上下文管理（参考 WhisperLiveKit）
        self.context_window = []  # 历史文本窗口
        self.max_context_chars = 50  # ✅ 修复：缩短到50字符，避免过度依赖历史导致背景音时重复识别
        self.max_context_items = 10  # 最多保留10条记录

        print(f"[INFO] 初始化本地 Whisper 模型:")
        print(f"       - 模型: {model_size} ({self.MODEL_INFO.get(model_size, {}).get('params', 'Unknown')})")
        print(f"       - 设备: {self.device}")
        print(f"       - 计算类型: {self.compute_type}")
        print(f"       - 速度模式: {speed_mode} ({self.SPEED_PRESETS.get(speed_mode, {}).get('description', 'Unknown')})")

        self._load_model()

    def _detect_device(self, device):
        """检测可用设备"""
        if device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    print("[INFO] 检测到 CUDA GPU，使用 GPU 加速")
                    return "cuda"
            except:
                pass
            print("[INFO] 未检测到 GPU，使用 CPU")
            return "cpu"
        return device

    def _detect_compute_type(self, compute_type, device):
        """检测最佳计算类型"""
        if compute_type == "auto":
            if device == "cuda":
                # GPU 使用 float16 获得最佳性能
                return "float16"
            else:
                # CPU 使用 int8 量化获得更好性能
                return "int8"
        return compute_type

    def _load_model(self):
        """加载模型（首次使用时会自动下载）"""
        try:
            with self.model_lock:
                print(f"[INFO] 正在加载 {self.model_size} 模型...")
                print(f"       提示: 首次使用会自动下载模型，可能需要几分钟")

                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=os.path.join(os.path.expanduser("~"), ".cache", "whisper")
                )

                print(f"[SUCCESS] 模型加载成功！")

                # ✅ 新增: 模型预热（参考 WhisperLiveKit warmup）
                print(f"[INFO] 正在预热模型（消除冷启动延迟）...")
                test_audio = np.zeros(16000, dtype=np.float32)  # 1秒静音
                self.model.transcribe(test_audio, language="zh", beam_size=1)
                print(f"[SUCCESS] 模型预热完成！")

        except Exception as e:
            print(f"[ERROR] 模型加载失败: {e}")
            raise

    def _generate_prompt(self):
        """
        生成上下文提示（参考 WhisperLiveKit）

        返回最近的历史文本作为提示，最多50字符
        这有助于提高连贯性，减少重复识别
        """
        if not self.context_window:
            return ""

        # 合并上下文窗口中的所有文本
        full_context = "".join(self.context_window)

        # 取最后N字符作为提示（避免过长导致背景音时重复识别）
        prompt = full_context[-self.max_context_chars:] if len(full_context) > self.max_context_chars else full_context

        return prompt

    def _update_context(self, new_text):
        """
        更新上下文窗口

        参数:
            new_text (str): 新转录的文本
        """
        if not new_text:
            return

        # 添加新文本到窗口
        self.context_window.append(new_text)

        # 保持窗口大小（最多10条记录）
        if len(self.context_window) > self.max_context_items:
            self.context_window.pop(0)  # 移除最早的记录

    def transcribe(self, audio_data, language="zh"):
        """
        转录音频数据

        参数:
            audio_data (bytes): 16kHz 单声道 16-bit PCM 音频数据
            language (str): 源语言代码 (例如: zh, en, ja, ko)

        返回:
            str: 转录文本，失败返回 None
        """
        try:
            # 1. 将 bytes 转换为 numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.int16)

            # 2. 归一化到 [-1.0, 1.0]
            audio_float = audio_np.astype(np.float32) / 32768.0

            # 3. 生成上下文提示（参考 WhisperLiveKit）
            prompt = self._generate_prompt()

            # 4. 调用 faster-whisper 转录
            # ✅ 优化: 使用动态参数配置（根据速度模式）
            with self.model_lock:
                segments, info = self.model.transcribe(
                    audio_float,
                    language=language,
                    initial_prompt=prompt,  # ✅ 新增: 使用历史文本作为提示
                    condition_on_previous_text=True,  # ✅ 改进: 启用上下文（原为False）
                    word_timestamps=False,  # 优化: 跳过词级时间戳，减少计算
                    vad_filter=True,  # 启用 VAD 过滤静音
                    vad_parameters={
                        "min_speech_duration_ms": 250,
                        "min_silence_duration_ms": 100,  # ✅ 优化: 缩短静音阈值（原500ms）
                        "speech_pad_ms": 200,  # ✅ 优化: 减少填充（原400ms）
                    },
                    # ✅ 新增: 使用速度预设参数
                    **self.transcribe_params
                )

                # 5. 合并所有片段
                text_parts = []
                for segment in segments:
                    text_parts.append(segment.text)

                full_text = "".join(text_parts).strip()

                # 6. 更新上下文窗口
                self._update_context(full_text)

                # 7. 日志
                if full_text:
                    print(f"[DEBUG] 本地 Whisper 转录: '{full_text[:50]}...' (长度: {len(full_text)})")
                    print(f"[INFO] 检测语言: {info.language} (置信度: {info.language_probability:.2f})")
                    if prompt:
                        print(f"[DEBUG] 使用上下文提示: '{prompt[:30]}...' (长度: {len(prompt)})")

                return full_text

        except Exception as e:
            print(f"[ERROR] 本地转录失败: {e}")
            return None

    def get_model_info(self):
        """获取模型信息"""
        return {
            "model_size": self.model_size,
            "device": self.device,
            "compute_type": self.compute_type,
            "info": self.MODEL_INFO.get(self.model_size, {})
        }

    def unload_model(self):
        """卸载模型释放内存"""
        with self.model_lock:
            if self.model:
                del self.model
                self.model = None
                print("[INFO] 模型已卸载")


def test_local_whisper():
    """测试函数"""
    print("=== 本地 Whisper 测试 ===\n")

    # 创建转录器
    transcriber = LocalWhisperTranscriber(model_size="base", device="auto")

    # 显示模型信息
    info = transcriber.get_model_info()
    print(f"\n模型信息: {info}")

    print("\n提示: 请使用真实音频数据进行测试")


if __name__ == "__main__":
    test_local_whisper()
