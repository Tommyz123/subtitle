# 实时语音翻译字幕系统 (Live Speech-to-Text Translator)

一个功能强大的桌面工具，可实时捕获系统音频，将其转录为文字，并翻译成您选择的语言，以现代化的悬浮窗样式显示双语字幕。

> **🚀 v2.1 更新**: 全新升级！新增流式处理（低延迟）、智能语音分段（抗干扰）、和多级速度模式。本地模式下延迟降低 50% 以上！

## ✨ 功能特性

### 核心功能
- **音频捕获与智能分段**:
  - 支持 `VB-Cable` 捕获系统声音。
  - **[NEW] 智能分段**: 不再是死板的固定切片，而是根据说话节奏动态切分音频，大幅提升识别准确率和响应速度。
  - **[NEW] VAD 语音检测**: 内置 Silero VAD，有效过滤静默和背景噪音，降低 API 成本。
- **多种转录与翻译模式**:
  - **在线 API 模式**: 集成 OpenAI Whisper 和 DeepL 云服务，精度最高。
  - **本地离线模式**: 运行 `faster-whisper` + `NLLB` 模型，**完全免费、离线、隐私安全**。
  - **[NEW] 流式处理**: 本地模式支持增量输出，说话的同时字幕即刻上屏。
- **Netflix 风格桌面字幕**:
  - 显示在所有窗口之上的透明悬浮窗。
  - 支持淡入淡出动画、拖动、缩放和样式设置。
  - 智能过滤广告和垃圾信息。
- **现代化 GUI**:
  - 简洁美观的 Material Design 风格界面。
  - 实时性能监控（CPU、队列、延迟）。
  - 支持导出 `.srt` 字幕文件。

## 🚀 运行模式

### 1. 本地模式 (离线 - 推荐)
在您的电脑上运行开源模型，无需联网，保护隐私。
- **转录**: `faster-whisper` (高效 CTranslate2 实现)
- **翻译**: Facebook NLLB (离线) 或 DeepL API (在线)
- **新特性**:
  - **速度模式**: 可选 `Fast` (极速), `Balanced` (平衡), `Quality` (高精)。
  - **流式输出**: 启用后延迟 < 1秒（首字上屏）。
- **硬件要求**: 推荐 NVIDIA 显卡 (4GB+ VRAM)，也支持 CPU 运行。

### 2. API 模式 (在线)
利用云服务进行处理，精度最高，对本地硬件无要求。
- **转录**: OpenAI Whisper API
- **翻译**: DeepL API
- **优点**: 极高的准确率。
- **缺点**: 需要 API Key，产生费用，受网络延迟影响。

## 🛠️ 快速开始

### 1. 前置要求
- **操作系统**: Windows 10/11
- **Python**: 3.9+
- **虚拟音频设备**: [VB-Cable](https://vb-audio.com/Cable/) (安装后**必须重启**)

### 2. 安装
```bash
# 1. 克隆项目
git clone https://github.com/yourusername/subtitle-translator.git
cd subtitle-translator

# 2. 安装依赖 (包含 torch, faster-whisper 等)
pip install -r requirements.txt
```

### 3. 配置 (.env)
复制模板并配置 API Key（如果使用 API 模式）：
```bash
copy .env.example .env
```
编辑 `.env` 文件：
```ini
# API 模式必需
OPENAI_API_KEY=sk-xxxx
DEEPL_API_KEY=xxxx

# 进阶配置 (默认已优化，通常无需修改)
ENABLE_VAD=true
VAD_SENSITIVITY=0.4
```

### 4. 运行
```bash
python app/main.py
```

## 🎮 使用说明

1. **设置音频**: 将系统音频输出设置为 `CABLE Input` (VB-Audio Virtual Cable)。
   - *提示*: 若要同时听到声音，请在 Windows 声音设置中将 `CABLE Output` 的"侦听此设备"打开，并指向您的扬声器。
2. **选择模式**: 
   - 推荐尝试 **本地模式** + **Base模型** + **Balanced速度**。
   - 勾选 **流式处理** 以获得最佳实时体验。
3. **开始**: 点击 `▶ 开始捕获`。
4. **悬浮窗**: 勾选 `显示桌面悬浮字幕`。
   - **移动**: Ctrl + 左键拖动
   - **缩放**: Ctrl + 滚轮
   - **菜单**: 右键点击

## ⚙️ 高级配置 (智能分段)

程序通过 `.env` 文件支持精细的 VAD（语音活动检测）调整，以适应不同的背景噪音环境（如游戏、电影）：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `VAD_SENSITIVITY` | `0.4` | VAD 灵敏度 (0.1-1.0)。值越低越灵敏，越高越抗噪。背景音乐大时调高此值。 |
| `SILENCE_THRESHOLD` | `500` | 停顿阈值 (ms)。静音多久后切分句子。包含背景音乐时建议设为 500ms+ 以防误切。 |
| `LOOKBACK_MS` | `300` | 预缓冲时长 (ms)。防止语音开头被截断。 |
| `MAX_SPEECH_DURATION`| `8000`| 强制切分阈值 (ms)。防止一句话过长导致字幕迟迟不显示。 |

## 📊 性能指标 (v2.1)

在 NVIDIA RTX 3060 Laptop 上测试：

| 模式 | 配置 | 首字延迟 | 处理速度 |
|------|------|----------|----------|
| **本地流式** | Base + Fast | **< 0.8s** | ~30x 实时 |
| **本地标准** | Base + Balanced | ~2.5s | ~20x 实时 |
| **API 模式** | OpenAI Whisper | ~4.5s | 取决于网络 |

## 📁 项目结构

```
subtitle/
├── app/
│   ├── main.py               # GUI 主程序
│   ├── audio_capture.py      # 音频捕获 & 智能分段 (VAD)
│   ├── local_whisper.py      # 本地 Whisper 引擎 (faster-whisper)
│   ├── streaming_whisper.py  # 流式增量处理逻辑
│   ├── transcription.py      # 核心调度线程
│   └── desktop_subtitle.py   # Netflix 风格悬浮窗
├── .env.example              # 配置文件模板
└── requirements.txt          # 依赖列表
```

## ❓ 常见问题

**Q: 为什么没有声音？**
A: 安装 VB-Cable 后，系统声音被发送到了虚拟设备。请在 Windows 声音设置 -> 录制 -> CABLE Output -> 属性 -> 侦听 -> 勾选"侦听此设备"。

**Q: 字幕断断续续？**
A: 可能是 VAD 过于灵敏。尝试在 `.env` 中提高 `VAD_SENSITIVITY` (例如 0.6) 或增加 `SILENCE_THRESHOLD`。

**Q: 本地模式启动慢？**
A: 首次运行需要下载模型（Base模型约 150MB，Large模型约 3GB）。之后启动是秒级的。

---
**License**: MIT