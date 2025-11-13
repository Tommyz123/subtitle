"""
诊断脚本 - 检查 faster-whisper 和 local_whisper 导入问题
"""

print("=" * 60)
print("开始诊断导入问题...")
print("=" * 60)

# 测试 1: 检查 faster-whisper 是否已安装
print("\n[测试 1] 检查 faster-whisper 包...")
try:
    import faster_whisper
    print(f"✅ faster-whisper 已安装")
    print(f"   版本: {faster_whisper.__version__ if hasattr(faster_whisper, '__version__') else '未知'}")
    print(f"   路径: {faster_whisper.__file__}")
except ImportError as e:
    print(f"❌ faster-whisper 未安装: {e}")
    print("   请运行: pip install faster-whisper")

# 测试 2: 检查 WhisperModel 是否可导入
print("\n[测试 2] 检查 WhisperModel 类...")
try:
    from faster_whisper import WhisperModel
    print(f"✅ WhisperModel 可导入")
except ImportError as e:
    print(f"❌ WhisperModel 导入失败: {e}")

# 测试 3: 检查 local_whisper.py 是否存在
print("\n[测试 3] 检查 local_whisper.py 文件...")
import os
local_whisper_path = os.path.join("app", "local_whisper.py")
if os.path.exists(local_whisper_path):
    print(f"✅ 文件存在: {os.path.abspath(local_whisper_path)}")
else:
    print(f"❌ 文件不存在: {os.path.abspath(local_whisper_path)}")

# 测试 4: 检查 app/__init__.py 是否存在
print("\n[测试 4] 检查 app/__init__.py...")
init_path = os.path.join("app", "__init__.py")
if os.path.exists(init_path):
    print(f"✅ __init__.py 存在")
else:
    print(f"⚠️  __init__.py 不存在（可能导致相对导入失败）")

# 测试 5: 尝试直接导入 local_whisper（绝对导入）
print("\n[测试 5] 尝试绝对导入 app.local_whisper...")
try:
    from app.local_whisper import LocalWhisperTranscriber
    print(f"✅ 绝对导入成功")
except ImportError as e:
    print(f"❌ 绝对导入失败: {e}")
    import traceback
    traceback.print_exc()

# 测试 6: 检查依赖库
print("\n[测试 6] 检查必需的依赖库...")
dependencies = {
    "numpy": "数值计算",
    "torch": "VAD 模型",
    "ctranslate2": "CTranslate2 推理引擎",
    "huggingface_hub": "模型下载",
}

for module, desc in dependencies.items():
    try:
        __import__(module)
        print(f"✅ {module:20s} - {desc}")
    except ImportError:
        print(f"❌ {module:20s} - {desc} (未安装)")

# 测试 7: 测试实例化 LocalWhisperTranscriber（如果导入成功）
print("\n[测试 7] 尝试实例化 LocalWhisperTranscriber...")
try:
    from app.local_whisper import LocalWhisperTranscriber
    print("   注意: 首次使用会下载模型，可能需要几分钟")
    transcriber = LocalWhisperTranscriber(model_size="tiny", device="cpu")
    print(f"✅ 实例化成功")
    print(f"   模型信息: {transcriber.get_model_info()}")
except Exception as e:
    print(f"❌ 实例化失败: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("诊断完成！")
print("=" * 60)
