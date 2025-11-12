# Whisper 双模式使用指南

## 📌 概述

本项目现已支持两种 Whisper 转录模式：
- **API 模式**：使用 OpenAI Whisper API（云端）
- **本地模式**：使用 faster-whisper 本地模型（离线）

## 🚀 快速开始

### 方式 1：通过 GUI 选择（推荐）

启动程序后，在界面上直接选择：
- **⚡ Whisper: API（云端）** - 使用 OpenAI API
- **⚡ Whisper: 本地模型** - 使用本地模型

### 方式 2：通过配置文件

在 `.env` 文件中设置：

```bash
# API 模式（默认）
WHISPER_MODE=api
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# 或者：本地模式
WHISPER_MODE=local
LOCAL_WHISPER_MODEL=small
LOCAL_WHISPER_DEVICE=auto
LOCAL_WHISPER_COMPUTE_TYPE=float16
```

## 📊 性能对比

### API 模式（云端）
- ✅ 准确率最高
- ✅ 无需本地资源
- ❌ 需要网络连接
- ❌ 有使用成本（$0.006/分钟）
- ⏱️ 延迟：3-5秒/块（5秒音频）

### 本地模式（GPU）
- ✅ 速度更快（快 50-70%）
- ✅ 零成本
- ✅ 离线可用
- ✅ 数据隐私
- ❌ 需要 GPU（推荐）
- ⏱️ 延迟：0.25-1秒/块（small/medium 模型）

### 本地模式（CPU）
- ✅ 零成本
- ✅ 离线可用
- ⚠️ 速度较慢
- ⏱️ 延迟：1-2.5秒/块（tiny/base 模型）

## 🔧 安装依赖

### API 模式
```bash
pip install openai deepl python-dotenv
```

### 本地模式
```bash
pip install faster-whisper deepl python-dotenv
```

### 完整安装（支持两种模式）
```bash
pip install -r requirements.txt
```

## ⚙️ 配置说明

### 本地模型选择

| 模型 | 大小 | 准确率 | GPU 推荐 | CPU 推荐 |
|------|------|--------|----------|----------|
| **tiny** | 39 MB | ⭐⭐ | ❌ | ✅ |
| **base** | 74 MB | ⭐⭐⭐ | ❌ | ✅ |
| **small** | 244 MB | ⭐⭐⭐⭐ | ✅ | ⚠️ |
| **medium** | 769 MB | ⭐⭐⭐⭐⭐ | ✅ | ❌ |
| **large-v2** | 1.5 GB | ⭐⭐⭐⭐⭐ | ✅ | ❌ |

### 设备配置

```bash
# 自动检测（优先使用 GPU）
LOCAL_WHISPER_DEVICE=auto

# 强制使用 GPU
LOCAL_WHISPER_DEVICE=cuda

# 强制使用 CPU
LOCAL_WHISPER_DEVICE=cpu
```

### 计算精度（仅 GPU）

```bash
# INT8 量化（速度最快，显存最小）
LOCAL_WHISPER_COMPUTE_TYPE=int8

# FP16 半精度（平衡，推荐）
LOCAL_WHISPER_COMPUTE_TYPE=float16

# FP32 全精度（准确率最高）
LOCAL_WHISPER_COMPUTE_TYPE=float32
```

## 💡 推荐配置

### 场景 1：有 NVIDIA GPU（RTX 3060+）
```bash
WHISPER_MODE=local
LOCAL_WHISPER_MODEL=small
LOCAL_WHISPER_DEVICE=auto
LOCAL_WHISPER_COMPUTE_TYPE=float16
```
**预期性能**：5秒音频 → 0.25秒处理，比 API 快 60-70%

### 场景 2：仅有 CPU
```bash
WHISPER_MODE=local
LOCAL_WHISPER_MODEL=tiny
LOCAL_WHISPER_DEVICE=cpu
LOCAL_WHISPER_COMPUTE_TYPE=int8
```
**预期性能**：5秒音频 → 1秒处理，比 API 快 30-50%

### 场景 3：追求最高准确率
```bash
WHISPER_MODE=api
OPENAI_API_KEY=sk-xxxxxxxx
```
**预期性能**：5秒音频 → 3-5秒处理

## 🐛 故障排除

### 问题 1：本地模式提示缺少依赖
```bash
# 安装 faster-whisper
pip install faster-whisper
```

### 问题 2：GPU 不可用
```bash
# 检查 CUDA 是否可用
python -c "import torch; print(torch.cuda.is_available())"

# 如果返回 False，使用 CPU 模式
LOCAL_WHISPER_DEVICE=cpu
LOCAL_WHISPER_MODEL=tiny
```

### 问题 3：首次启动很慢
- 本地模式首次运行会自动下载模型
- tiny: ~39 MB
- small: ~244 MB
- medium: ~769 MB
- 模型下载后会缓存，后续启动很快

### 问题 4：API 模式提示 Key 错误
```bash
# 检查 .env 文件中的配置
OPENAI_API_KEY=sk-xxxxxxxx
```

## 📝 示例配置文件

完整的 `.env` 配置示例：

```bash
# ===========================================
# Whisper 模式配置
# ===========================================
# 模式选择: api 或 local
WHISPER_MODE=local

# ===========================================
# API 模式配置（仅当 WHISPER_MODE=api）
# ===========================================
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# ===========================================
# 本地模式配置（仅当 WHISPER_MODE=local）
# ===========================================
LOCAL_WHISPER_MODEL=small
LOCAL_WHISPER_DEVICE=auto
LOCAL_WHISPER_COMPUTE_TYPE=float16

# ===========================================
# DeepL 翻译（必需）
# ===========================================
DEEPL_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx
```

## 🎯 性能测试

运行测试脚本验证两种模式：

```bash
python test_whisper_modes.py
```

这将测试：
- 依赖库安装情况
- API 模式初始化
- 本地模式初始化

## 📞 技术支持

- 问题反馈：GitHub Issues
- 文档：README.md
- 配置示例：.env.example
