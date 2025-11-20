"""
本地翻译模块 - 使用 NLLB 模型

职责:
- 使用本地 NLLB (No Language Left Behind) 模型进行翻译
- 支持 GPU 加速
- 速度快（< 100ms），完全离线
"""

import threading
from typing import Optional


class LocalTranslator:
    """本地翻译器（使用 NLLB 模型）"""

    # 支持的语言映射
    LANGUAGE_MAP = {
        "zh": "zho_Hans",  # 中文简体
        "en": "eng_Latn",  # 英语
        "ja": "jpn_Jpan",  # 日语
        "ko": "kor_Hang",  # 韩语
        "fr": "fra_Latn",  # 法语
        "de": "deu_Latn",  # 德语
        "es": "spa_Latn",  # 西班牙语
        "ru": "rus_Cyrl",  # 俄语
        "it": "ita_Latn",  # 意大利语
        "pt": "por_Latn",  # 葡萄牙语
    }

    def __init__(self, model_size="distilled-600M", device="auto"):
        """
        初始化本地翻译模型

        参数:
            model_size (str): 模型大小
                - distilled-600M: 轻量级，速度快（推荐）
                - 1.3B: 更高质量，速度较慢
            device (str): 设备 - auto, cuda, cpu
        """
        self.model_size = model_size
        self.device = self._detect_device(device)
        self.model = None
        self.tokenizer = None
        self.model_lock = threading.Lock()

        print(f"[INFO] 初始化本地翻译模型:")
        print(f"       - 模型: NLLB-{model_size}")
        print(f"       - 设备: {self.device}")

        self._load_model()

    def _detect_device(self, device):
        """检测可用设备"""
        if device == "auto":
            try:
                import torch
                if torch.cuda.is_available():
                    print("[INFO] 检测到 CUDA GPU，翻译将使用 GPU 加速")
                    return "cuda"
            except:
                pass
            print("[INFO] 翻译使用 CPU")
            return "cpu"
        return device

    def _load_model(self):
        """加载 NLLB 翻译模型"""
        try:
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            import torch

            model_name = f"facebook/nllb-200-{self.model_size}"

            print(f"[INFO] 正在加载 NLLB 翻译模型...")
            print(f"       提示: 首次使用会自动下载模型（约 1.2GB）")

            with self.model_lock:
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)

                # 移动到 GPU（如果可用）
                if self.device == "cuda":
                    self.model = self.model.to("cuda")
                    self.model = self.model.half()  # 使用 FP16 加速

                print(f"[SUCCESS] 翻译模型加载成功！")

        except Exception as e:
            print(f"[ERROR] 翻译模型加载失败: {e}")
            print(f"[INFO] 请安装 transformers: pip install transformers sentencepiece")
            raise

    def translate(self, text: str, source_lang: str = "zh", target_lang: str = "en") -> Optional[str]:
        """
        翻译文本

        参数:
            text (str): 原文
            source_lang (str): 源语言代码（zh, en, ja等）
            target_lang (str): 目标语言代码

        返回:
            str: 翻译结果，失败返回 None
        """
        try:
            # 转换语言代码
            src_lang = self.LANGUAGE_MAP.get(source_lang, "zho_Hans")
            tgt_lang = self.LANGUAGE_MAP.get(target_lang, "eng_Latn")

            with self.model_lock:
                # 设置源语言
                self.tokenizer.src_lang = src_lang

                # 编码
                inputs = self.tokenizer(text, return_tensors="pt")

                # 移动到 GPU
                if self.device == "cuda":
                    inputs = {k: v.cuda() for k, v in inputs.items()}

                # 生成翻译
                # 性能优化: num_beams=1 使用贪心解码，速度提升50%
                translated_tokens = self.model.generate(
                    **inputs,
                    forced_bos_token_id=self.tokenizer.lang_code_to_id[tgt_lang],
                    max_length=200,
                    num_beams=1,  # 优化: 从3改为1，贪心解码最快
                    do_sample=False,  # 优化: 确定性输出
                    early_stopping=True,
                    use_cache=True  # 优化: 启用KV缓存加速
                )

                # 解码
                translation = self.tokenizer.batch_decode(
                    translated_tokens,
                    skip_special_tokens=True
                )[0]

                return translation.strip()

        except Exception as e:
            print(f"[ERROR] 本地翻译失败: {e}")
            return None

    def unload_model(self):
        """卸载模型释放内存"""
        with self.model_lock:
            if self.model:
                del self.model
                del self.tokenizer
                self.model = None
                self.tokenizer = None
                print("[INFO] 翻译模型已卸载")


def test_local_translator():
    """测试函数"""
    print("=== 本地翻译测试 ===\n")

    # 创建翻译器
    translator = LocalTranslator(model_size="distilled-600M", device="auto")

    # 测试翻译
    test_texts = [
        "你好，世界！",
        "今天天气真好。",
        "我想学习人工智能。"
    ]

    for text in test_texts:
        translation = translator.translate(text, source_lang="zh", target_lang="en")
        print(f"原文: {text}")
        print(f"译文: {translation}\n")


if __name__ == "__main__":
    test_local_translator()
