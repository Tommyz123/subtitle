# 实时语音翻译字幕系统

## 项目状态

**当前版本**: v2.1 - 阶段2完成+性能优化完成 ✅
**完成日期**: 2025-01-09
**总代码行数**: 2,286行（6个模块）
**实时延迟**: 6.5秒（优化前55秒，改善88%）
**支持语言**: 15种源语言 + 32种目标语言

> 📊 查看项目真实状态快照：[PROJECT_STATUS.md](PROJECT_STATUS.md)

## 功能特性

### 核心功能（已完成）✅

#### 音频捕获 + 语音检测
- ✅ VB-Cable虚拟音频设备捕获
- ✅ Silero VAD语音活动检测（节省30-50%成本）
- ✅ 优化音频格式：16kHz单声道（最优性能）
- ✅ 3秒音频块（平衡延迟和质量）

#### 转录 + 翻译
- ✅ OpenAI Whisper语音转录
- ✅ DeepL自动翻译
- ✅ 3次重试机制（成功率≥99.9%）
- ✅ 多语言支持：15种源语言 × 32种目标语言
- ✅ 性能监控和队列管理

#### Netflix风格桌面字幕窗口 ⭐
- ✅ 透明窗口 + 圆角背景框
- ✅ 淡入淡出动画效果
- ✅ 窗口拖动（Ctrl+鼠标左键）、缩放（Ctrl+滚轮）
- ✅ 右键菜单设置（字体、透明度）
- ✅ 广告过滤功能
- ✅ 原文/翻译同时显示

#### 现代化GUI主程序
- ✅ Material Design风格界面
- ✅ 双语字幕实时显示
- ✅ 多语言选择下拉菜单（15+32种语言）
- ✅ 控制按钮：开始/停止/导出
- ✅ 桌面字幕窗口开关

#### 字幕存储 + 导出
- ✅ 字幕存储和管理
- ✅ SRT格式导出
- ✅ 动态时长计算
- ✅ 线程安全（Lock保护）

#### 性能优化（2025-01-09）
- ✅ 延迟优化：55秒 → 6.5秒（↓88%）
- ✅ Whisper API耗时：30-40秒 → 2.4-3.2秒（↓91%）
- ✅ 文件大小减少：938KB → 156KB（↓83%）
- ✅ 队列稳定：0-1块（优化前10-17块）

## 快速开始

### 前置要求

1. **Windows 10/11**
2. **Python 3.9+** 已安装
3. **VB-Cable虚拟音频驱动** ([下载地址](https://vb-audio.com/Cable/))
   - 安装后必须重启电脑
   - 将系统音频输出设置为 "CABLE Input"
4. **API Keys**:
   - OpenAI API Key ([获取地址](https://platform.openai.com/api-keys))
   - DeepL API Key ([获取地址](https://www.deepl.com/pro-api))

### 安装步骤

1. **克隆/下载项目**
   ```bash
   cd subtitle
   ```

2. **安装Python依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **配置API Keys**

   复制配置模板:
   ```bash
   copy .env.example .env
   ```

   编辑 `.env` 文件,填入你的API Keys:
   ```env
   # OpenAI API配置
   OPENAI_API_KEY=sk-your-openai-api-key-here

   # DeepL API配置
   DEEPL_API_KEY=your-deepl-api-key-here
   ```

### 运行程序

```bash
python app/main.py
```

### 使用说明

1. **选择语言**: 在下拉菜单中选择源语言和目标语言
2. **开始捕获**: 点击 "开始捕获" 按钮
3. **播放音频**: 播放YouTube视频或其他媒体
4. **查看字幕**:
   - 主窗口：双语字幕实时显示
   - 桌面窗口：勾选"显示桌面字幕"开启Netflix风格浮动窗口
5. **桌面字幕操作**:
   - Ctrl+鼠标左键：拖动窗口位置
   - Ctrl+滚轮：缩放字幕大小（50%-200%）
   - 右键：打开设置菜单
   - ESC：关闭桌面字幕窗口
6. **导出字幕**: 点击 "导出SRT" 保存字幕文件
7. **停止捕获**: 点击 "停止" 按钮

## 项目结构

```
subtitle/
├── app/                          # 应用代码（2,286行）
│   ├── __init__.py              # Python包标记
│   ├── main.py                  # GUI主程序 (789行)
│   ├── desktop_subtitle.py      # Netflix风格桌面字幕窗口 (657行)
│   ├── audio_capture.py         # 音频捕获 + VAD (276行)
│   ├── transcription.py         # 转录翻译 + 重试 (224行)
│   ├── silero_vad_iterator.py   # VAD语音活动检测 (219行)
│   └── subtitle_storage.py      # 字幕存储 (121行)
├── .ai-rules/                   # 设计文档
│   ├── README.md               # 项目概览
│   ├── architecture.md         # 架构设计
│   ├── implementation-roadmap.md  # 实施路线图
│   ├── modules/                # 模块设计文档
│   └── technical/              # 技术专题文档
├── .env                        # API配置 (不提交到git)
├── .env.example               # 配置模板
├── requirements.txt           # Python依赖
├── PROJECT_STATUS.md          # 项目真实状态快照
├── OPTIMIZATION_LOG.md        # 性能优化日志
├── claude.md                  # Claude开发规范
└── README.md                  # 本文件
```

## 阶段1已实现的P0修复

### 1. ✅ Queue设置maxsize=10
**位置**: [main.py:36](app/main.py#L36)
**作用**: 防止队列无限增长导致内存泄漏

### 2. ✅ Queue.put()使用timeout=1
**位置**: [audio_capture.py:111](app/audio_capture.py#L111)
**作用**: 队列满时丢弃音频块,不阻塞线程

### 3. ✅ SubtitleStorage并发访问使用Lock
**位置**: [main.py:147,237,250](app/main.py#L147)
**作用**: 保护字幕列表的并发访问,防止数据竞争

### 4. ✅ 字幕时长根据下一条计算
**位置**: [subtitle_storage.py:76](app/subtitle_storage.py#L76)
**作用**: 动态计算字幕显示时长,不固定5秒

### 5. ✅ 线程清理时清空队列
**位置**: [main.py:191](app/main.py#L191)
**作用**: 加速转录线程退出,停止响应更快

### 6. ✅ PyAudio流读取捕获异常
**位置**: [audio_capture.py:71](app/audio_capture.py#L71)
**作用**: 系统负载高时避免线程崩溃

## 技术架构

### 线程模型
- **主线程**: Tkinter GUI事件循环
- **音频捕获线程**: 持续从VB-Cable捕获音频 (5秒分块)
- **转录翻译线程**: 调用Whisper + DeepL API处理音频

### 数据流
```
VB-Cable → 音频捕获线程 → Queue(maxsize=10) → 转录翻译线程 → GUI回调 → 字幕显示
                                                                    ↓
                                                              SubtitleStorage
                                                                    ↓
                                                                导出SRT文件
```

### 音频参数（优化后）
- **采样率**: 16kHz（Whisper最优配置，优化前48kHz）
- **通道数**: 1（单声道，优化前立体声）
- **采样位深**: 16-bit
- **分块时长**: 3秒（优化前5秒）
- **每块大小**: ~156KB（优化前960KB，减少83%）

## 成本估算

### Whisper API
- **计费**: $0.006/分钟
- **月度成本** (每天1小时):
  - 无VAD: $10.80/月
  - 有VAD: ~$6.48/月（节省30-50%）✅

### DeepL API
- **免费额度**: 500K字符/月
- **预计使用**: 约200K字符/月（免费额度内）

### 性能指标
- **实时延迟**: 6.5秒
- **Whisper API耗时**: 2.4-3.2秒
- **队列堆积**: 0-1块（稳定）
- **文件大小**: 156KB/块（优化前938KB）

详细优化记录见：[OPTIMIZATION_LOG.md](OPTIMIZATION_LOG.md)

## 常见问题

### Q1: "未找到VB-Cable设备"
**原因**: VB-Cable未安装或安装后未重启
**解决**:
1. 下载并安装 VB-Cable
2. 重启电脑
3. 系统音频输出设置为 "CABLE Input"

### Q2: "请在.env文件中配置API Keys"
**原因**: .env文件不存在或API Keys未配置
**解决**:
1. 复制 `.env.example` 为 `.env`
2. 填入有效的API Keys

### Q3: 听不到音频
**原因**: VB-Cable会接管音频输出
**解决**: 在"声音设置"中配置"监听"功能,将音频同时输出到扬声器

### Q4: API调用失败
**原因**:
- API Key错误
- 网络连接问题
- 配额耗尽

**解决**:
1. 检查API Key是否正确
2. 确认网络可访问 api.openai.com
3. 检查API配额

## 调试技巧

### 列出所有音频设备
```python
import pyaudio
audio = pyaudio.PyAudio()
for i in range(audio.get_device_count()):
    info = audio.get_device_info_by_index(i)
    print(f"{i}: {info['name']}")
```

### 查看日志
程序运行时会在控制台输出详细日志:
- `[INFO]`: 正常信息
- `[WARNING]`: 警告 (如队列已满)
- `[ERROR]`: 错误 (如API调用失败)

## 依赖项

详见 [requirements.txt](requirements.txt):
- `openai>=1.0.0,<2.0.0` - Whisper API客户端
- `deepl>=1.16.0,<2.0.0` - DeepL翻译API
- `pyaudio>=0.2.13` - 音频捕获
- `python-dotenv>=1.0.0` - 环境变量管理
- `torch>=2.0.0,<3.0.0` - VAD模型（Silero）✅
- `numpy>=1.24.0,<2.0.0` - 音频处理 ✅
- `scipy>=1.11.0,<2.0.0` - 音频重采样 ✅

## 开发文档

详细的开发文档位于 `.ai-rules/` 目录:

- **[README.md](.ai-rules/README.md)** - 项目概览和进度追踪
- **[architecture.md](.ai-rules/architecture.md)** - 系统架构设计
- **[implementation-roadmap.md](.ai-rules/implementation-roadmap.md)** - 分阶段实施指南
- **[technical/critical-fixes.md](.ai-rules/technical/critical-fixes.md)** - 12个P0必修问题
- **[modules/](.ai-rules/modules/)** - 各模块详细设计

## 贡献指南

在开发前请阅读:
1. [claude.md](claude.md) - Claude开发规范
2. [.ai-rules/WORKFLOW.md](.ai-rules/WORKFLOW.md) - 标准开发流程

## 许可证

本项目用于学习和研究目的。

## 联系方式

如有问题,请查阅 `.ai-rules/` 目录下的文档。

---

**最后更新**: 2025-01-09
**版本**: v2.1 (阶段2完成+性能优化完成)
**状态**: ✅ 生产就绪
