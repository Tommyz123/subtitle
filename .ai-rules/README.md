# 实时语音翻译字幕系统 - 开发指南

> 💡 **Claude Code 专用提示**：
> 这是项目的详细技术指南。如果需要快速了解当前任务和状态，
> 请**优先阅读根目录的 `claude.md`**，它提供了简洁的导航和当前进度。
> 本文档包含完整的技术细节和实施指导。

---

## 📌 项目概述

**功能**: Windows桌面应用，捕获系统音频 → 实时语音转录 → 自动翻译 → 双语字幕显示

**技术栈**:
- **语言**: Python 3.9+
- **GUI**: Tkinter (内置)
- **音频捕获**: PyAudio + VB-Cable虚拟音频设备
- **语音转录**: OpenAI Whisper API ($0.006/分钟)
- **文本翻译**: DeepL API (免费500K字符/月)
- **语音检测**: Silero VAD (节省30-50%成本)

---

## 🗂️ 文档导航

### 核心文档
- **[architecture.md](architecture.md)** - 系统架构、线程模型、数据流设计
- **[implementation-roadmap.md](implementation-roadmap.md)** - 分阶段实施路线图和验收标准

### 模块详细设计
- **[modules/audio-capture.md](modules/audio-capture.md)** - 音频捕获模块 + VAD集成
- **[modules/transcription.md](modules/transcription.md)** - 转录翻译模块 + 错误重试
- **[modules/storage.md](modules/storage.md)** - 字幕存储和导出
- **[modules/gui-main.md](modules/gui-main.md)** - GUI主程序设计

### 技术专题指南
- **[technical/threading-concurrency.md](technical/threading-concurrency.md)** - 线程管理、队列、锁机制
- **[technical/vad-optimization.md](technical/vad-optimization.md)** - VAD优化和成本节省策略
- **[technical/critical-fixes.md](technical/critical-fixes.md)** - 必须修复的Bug清单（P0级别）

---

## 🚀 快速开始指南

### 前置条件
- ✅ Windows 10/11
- ✅ Python 3.9+ 已安装
- ✅ VB-Cable 虚拟音频驱动已安装并重启
- ✅ OpenAI API Key 已获取
- ✅ DeepL API Key 已获取

### 开发流程

```
第1步: 阅读架构文档
  ├─ architecture.md (了解系统设计)
  └─ implementation-roadmap.md (了解实施计划)

第2步: 阶段1开发（MVP基础版本）
  ├─ 阅读 modules/*.md 了解各模块设计
  ├─ 实现 audio_capture.py (基础版)
  ├─ 实现 transcription.py (基础版)
  ├─ 实现 subtitle_storage.py
  └─ 实现 main.py (GUI)

第3步: 测试验证
  └─ 确认字幕能正常显示和导出

第4步: 阶段2开发（优化版本）
  ├─ 阅读 technical/vad-optimization.md
  ├─ 阅读 technical/critical-fixes.md
  ├─ 集成 Silero VAD
  ├─ 添加错误重试机制
  └─ 应用所有P0级别的修复

第5步: 最终验证
  ├─ VAD成功跳过静音段
  ├─ API失败自动重试
  └─ 长时间运行无内存泄漏
```

---

## 📊 分阶段实施概览

### 阶段1: MVP基础版本 (1-2天)
**目标**: 实现完整的功能链路

**实现文件**:
- `app/audio_capture.py` (基础版，无VAD)
- `app/transcription.py` (基础版，无重试)
- `app/subtitle_storage.py`
- `app/main.py`

**验收标准**:
- ✅ 能捕获VB-Cable音频
- ✅ 字幕正确显示在窗口
- ✅ 能导出SRT文件

### 阶段2: 优化版本 (1-2天)
**目标**: 添加VAD节省成本 + 错误重试提升稳定性

**新增/更新**:
- `app/silero_vad_iterator.py` (新增)
- 更新 `audio_capture.py` (集成VAD)
- 更新 `transcription.py` (添加重试)
- 更新 `main.py` (添加锁和配置)

**验收标准**:
- ✅ VAD跳过静音段（日志显示节省比例）
- ✅ API失败自动重试
- ✅ 无内存泄漏

### 阶段3: 完善版本 (可选)
**优化项**:
- 日志系统（logging模块）
- 线程清理优化
- GUI增强（状态栏、统计信息）

---

## 🎯 当前项目状态

**当前阶段**: 准备阶段完成 ✅
**下一步**: 开始阶段1开发（基础MVP版本）
**最后更新**: 2025-11-06

### 📊 项目进度追踪

#### 准备阶段 ✅
- [x] 创建项目目录结构（`.ai-rules/`, `app/`）
- [x] 创建核心文档（README, architecture, implementation-roadmap）
- [x] 创建模块文档（audio-capture, transcription, storage, gui-main）
- [x] 创建技术专题（threading, vad-optimization, critical-fixes）
- [x] 创建配置文件（.env.example, requirements.txt, .gitignore）
- [x] 创建 Claude 入口文件（claude.md）

#### 阶段1：基础MVP版本
- [ ] 实现 `app/audio_capture.py`（基础版，~80行）
- [ ] 实现 `app/transcription.py`（基础版，~60行）
- [ ] 实现 `app/subtitle_storage.py`（~50行）
- [ ] 实现 `app/main.py`（~150行）
- [ ] 功能测试验收
- [ ] 应用阶段1相关的P0修复（6个）

#### 阶段2：优化版本
- [ ] 实现 `app/silero_vad_iterator.py`（~150行）
- [ ] 更新 `audio_capture.py`（集成VAD）
- [ ] 更新 `transcription.py`（添加重试）
- [ ] 更新 `main.py`（配置验证+锁）
- [ ] 性能测试验收
- [ ] 应用所有12个P0修复

#### 阶段3：完善版本（可选）
- [ ] 日志系统（logging模块）
- [ ] 线程健康监控
- [ ] GUI增强（状态栏、统计）

---

## ⚠️ 重要提醒

### 开发前必读
1. **先读 `technical/critical-fixes.md`** - 了解必须避免的12个关键错误
2. **先读 `architecture.md`** - 理解线程模型和数据流
3. **严格按照阶段顺序实施** - 不要跳过阶段1直接实现优化功能

### 核心原则
- ✅ 使用 `scipy.signal.resample_poly()` 进行重采样，不要用简单抽取
- ✅ 立体声转单声道时先转 int32 避免溢出
- ✅ Queue 必须设置 maxsize=10 防止内存泄漏
- ✅ SubtitleStorage 并发访问必须使用 threading.Lock
- ✅ VADIterator 的 speech_start 必须是实例变量

---

## 📚 参考资源

- **原始详细设计**: `plan.md` (2188行完整设计文档)
- **OpenAI API文档**: https://platform.openai.com/docs/api-reference/audio
- **DeepL API文档**: https://www.deepl.com/docs-api
- **Silero VAD**: https://github.com/snakers4/silero-vad

---

## 💡 成本估算

**无VAD版本**: 每天1小时 = $10.80/月
**有VAD版本**: 每天1小时 = $6.48/月 (节省40%)

**建议**: 阶段1快速验证可行性，阶段2添加VAD降低成本

---

## 🔧 故障排查

遇到问题时的检查清单：
- [ ] VB-Cable驱动已安装并重启电脑
- [ ] 系统音频输出设置为 "CABLE Input"
- [ ] 配置了监听输出（否则听不到声音）
- [ ] `.env` 文件已创建并填写正确的API Keys
- [ ] Python依赖已全部安装
- [ ] 网络连接正常，可访问 api.openai.com

---

**最后更新**: 2025-11-06
**文档版本**: v1.1 (添加Claude提示和进度追踪)
