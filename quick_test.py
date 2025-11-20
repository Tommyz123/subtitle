#!/usr/bin/env python3
"""
阶段1优化快速测试脚本
用于验证优化是否正确应用
"""

import sys
import os

def check_environment():
    """检查环境和依赖"""
    print("=" * 60)
    print("🔍 检查测试环境")
    print("=" * 60)

    # 检查Python版本
    print(f"\n1. Python版本: {sys.version}")
    if sys.version_info < (3, 9):
        print("   ❌ 需要Python 3.9+")
        return False
    print("   ✅ Python版本满足要求")

    # 检查必要依赖
    dependencies = [
        ("numpy", "NumPy"),
        ("faster_whisper", "faster-whisper"),
        ("torch", "PyTorch"),
    ]

    print("\n2. 依赖检查:")
    all_installed = True
    for module, name in dependencies:
        try:
            __import__(module)
            print(f"   ✅ {name} 已安装")
        except ImportError:
            print(f"   ❌ {name} 未安装 - 运行: pip install {module.replace('_', '-')}")
            all_installed = False

    # 检查GPU
    print("\n3. GPU检查:")
    try:
        import torch
        if torch.cuda.is_available():
            print(f"   ✅ GPU可用: {torch.cuda.get_device_name(0)}")
            print(f"   显存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
        else:
            print("   ⚠️  GPU不可用，将使用CPU（速度较慢但功能正常）")
    except:
        print("   ⚠️  无法检测GPU状态")

    return all_installed


def check_code_modifications():
    """检查代码修改是否正确应用"""
    print("\n" + "=" * 60)
    print("🔍 检查代码修改")
    print("=" * 60)

    checks = []

    # 检查1: local_whisper.py - 上下文提示
    print("\n1. 检查 local_whisper.py - 上下文提示功能")
    try:
        with open("app/local_whisper.py", "r", encoding="utf-8") as f:
            content = f.read()

        if "context_window" in content:
            print("   ✅ 找到 context_window")
            checks.append(True)
        else:
            print("   ❌ 未找到 context_window")
            checks.append(False)

        if "_generate_prompt" in content:
            print("   ✅ 找到 _generate_prompt 方法")
            checks.append(True)
        else:
            print("   ❌ 未找到 _generate_prompt 方法")
            checks.append(False)

        if "initial_prompt=prompt" in content:
            print("   ✅ 找到 initial_prompt 使用")
            checks.append(True)
        else:
            print("   ❌ 未找到 initial_prompt 使用")
            checks.append(False)

        if "模型预热" in content or "预热模型" in content:
            print("   ✅ 找到模型预热功能")
            checks.append(True)
        else:
            print("   ❌ 未找到模型预热功能")
            checks.append(False)

    except FileNotFoundError:
        print("   ❌ 找不到 app/local_whisper.py 文件")
        checks.append(False)

    # 检查2: local_whisper.py - 速度预设
    print("\n2. 检查 local_whisper.py - 速度模式")
    try:
        with open("app/local_whisper.py", "r", encoding="utf-8") as f:
            content = f.read()

        if "SPEED_PRESETS" in content:
            print("   ✅ 找到 SPEED_PRESETS")
            checks.append(True)

            if '"fast"' in content and '"balanced"' in content and '"quality"' in content:
                print("   ✅ 找到三种速度模式")
                checks.append(True)
            else:
                print("   ❌ 速度模式不完整")
                checks.append(False)
        else:
            print("   ❌ 未找到 SPEED_PRESETS")
            checks.append(False)

    except FileNotFoundError:
        print("   ❌ 找不到 app/local_whisper.py 文件")
        checks.append(False)

    # 检查3: main.py - GUI控件
    print("\n3. 检查 main.py - GUI速度模式选择器")
    try:
        with open("app/main.py", "r", encoding="utf-8") as f:
            content = f.read()

        if "speed_mode_var" in content:
            print("   ✅ 找到 speed_mode_var")
            checks.append(True)
        else:
            print("   ❌ 未找到 speed_mode_var")
            checks.append(False)

        if "speed_mode_combo" in content:
            print("   ✅ 找到 speed_mode_combo 控件")
            checks.append(True)
        else:
            print("   ❌ 未找到 speed_mode_combo 控件")
            checks.append(False)

    except FileNotFoundError:
        print("   ❌ 找不到 app/main.py 文件")
        checks.append(False)

    # 检查4: transcription.py - 参数传递
    print("\n4. 检查 transcription.py - 参数传递")
    try:
        with open("app/transcription.py", "r", encoding="utf-8") as f:
            content = f.read()

        if "speed_mode" in content:
            print("   ✅ 找到 speed_mode 参数")
            checks.append(True)
        else:
            print("   ❌ 未找到 speed_mode 参数")
            checks.append(False)

    except FileNotFoundError:
        print("   ❌ 找不到 app/transcription.py 文件")
        checks.append(False)

    # 总结
    print("\n" + "=" * 60)
    passed = sum(checks)
    total = len(checks)
    print(f"检查结果: {passed}/{total} 项通过")

    if passed == total:
        print("✅ 所有修改都已正确应用！")
        return True
    else:
        print(f"❌ 有 {total - passed} 项修改未正确应用")
        return False


def show_test_instructions():
    """显示测试说明"""
    print("\n" + "=" * 60)
    print("📋 测试说明")
    print("=" * 60)

    print("\n接下来请按照以下步骤测试：")
    print("\n1. 确保 VB-Cable 已安装并重启电脑")
    print("2. 启动程序：python app/main.py")
    print("3. 选择【本地模式】")
    print("4. 选择【速度模式】（fast/balanced/quality）")
    print("5. 点击【开始捕获】")
    print("6. 播放测试音频（YouTube视频或在线会议）")
    print("7. 观察以下内容：")
    print("   - 控制台是否显示'模型预热完成'")
    print("   - 控制台是否显示'使用上下文提示'")
    print("   - 字幕响应速度（应该比之前快）")
    print("   - 是否有重复识别（应该减少）")
    print("\n详细测试步骤请查看: 测试指南_阶段1优化.md")


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🚀 阶段1优化 - 快速测试脚本")
    print("=" * 60)

    # 检查环境
    env_ok = check_environment()

    # 检查代码修改
    code_ok = check_code_modifications()

    # 显示测试说明
    if env_ok and code_ok:
        show_test_instructions()
        print("\n✅ 环境和代码检查通过，可以开始测试！")
        return 0
    else:
        print("\n❌ 请先解决上述问题后再进行测试")
        return 1


if __name__ == "__main__":
    sys.exit(main())
