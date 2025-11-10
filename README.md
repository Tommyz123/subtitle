# 实时语音翻译字幕系统

## 项目状态

**当前版本**: 阶段1 - MVP基础版本 ✅
**完成日期**: 2025-11-06
**下一步**: 用户测试并准备阶段2优化

## 功能特性

### 阶段1 (已完成)
- ✅ VB-Cable音频捕获
- ✅ OpenAI Whisper语音转录
- ✅ DeepL自动翻译
- ✅ 双语字幕实时显示
- ✅ SRT字幕文件导出
- ✅ 6个P0级别修复已应用

### 阶段2 (计划中)
- ⏸️ Silero VAD语音检测 (节省30-50%成本)
- ⏸️ API错误重试机制
- ⏸️ 额外6个P0修复

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

1. **开始捕获**: 点击 "开始捕获" 按钮
2. **播放音频**: 播放YouTube视频或其他媒体
3. **查看字幕**: 原文和翻译会实时显示在窗口中
4. **导出字幕**: 点击 "导出SRT" 保存字幕文件
5. **停止捕获**: 点击 "停止" 按钮

## 项目结构

```
subtitle/
├── app/                          # 应用代码
│   ├── __init__.py              # Python包标记
│   ├── audio_capture.py         # 音频捕获 (118行)
│   ├── transcription.py         # 转录翻译 (130行)
│   ├── subtitle_storage.py      # 字幕存储 (112行)
│   └── main.py                  # GUI主程序 (260行)
├── .ai-rules/                   # 设计文档
│   ├── README.md               # 项目概览
│   ├── architecture.md         # 架构设计
│   ├── implementation-roadmap.md  # 实施路线图
│   ├── modules/                # 模块设计文档
│   └── technical/              # 技术专题文档
├── .env                        # API配置 (不提交到git)
├── .env.example               # 配置模板
├── requirements.txt           # Python依赖
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

### 音频参数
- **采样率**: 48kHz (VB-Cable默认)
- **通道数**: 2 (立体声)
- **采样位深**: 16-bit
- **分块时长**: 5秒
- **每块大小**: ~960KB

## 成本估算

### 阶段1 (无VAD)
- **Whisper API**: $0.006/分钟
- **DeepL API**: 免费500K字符/月
- **月度成本** (每天1小时): $10.80/月

### 阶段2 (有VAD) - 计划中
- **节省比例**: 30-50%
- **月度成本** (每天1小时): ~$6.48/月

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
- `openai>=1.0.0` - Whisper API客户端
- `deepl>=1.16.0` - DeepL翻译API
- `pyaudio>=0.2.13` - 音频捕获
- `python-dotenv>=1.0.0` - 环境变量管理

阶段2还需要:
- `torch>=2.0.0` - VAD模型
- `numpy>=1.24.0` - 音频处理
- `scipy>=1.11.0` - 音频重采样

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

**最后更新**: 2025-11-06
**版本**: v1.0 (阶段1-MVP)
