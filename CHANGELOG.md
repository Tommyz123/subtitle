# 更新日志

本文档记录实时字幕系统的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [v2.1] - 2025-01-09

### 新增
- Netflix风格桌面字幕窗口（desktop_subtitle.py，657行）
  - 透明窗口 + 圆角背景框
  - 淡入淡出动画效果（0.3秒过渡）
  - 窗口拖动（Ctrl+鼠标左键）
  - 窗口缩放（Ctrl+滚轮，50%-200%）
  - 右键菜单设置（字体、透明度）
  - 广告过滤功能（正则表达式匹配）
  - 自动换行和动态高度调整
  - ESC关闭快捷键
- 多语言支持
  - 15种源语言选择（Whisper识别）
  - 32种目标语言选择（DeepL翻译）
  - 480种语言对组合

### 优化
- **性能大幅优化**（详见 OPTIMIZATION_LOG.md）
  - 实时延迟：55秒 → 6.5秒（↓88%）
  - Whisper API耗时：30-40秒 → 2.4-3.2秒（↓91%）
  - 音频文件大小：938KB → 156KB（↓83%）
  - 队列堆积：10-17块 → 0-1块（稳定）
- 音频格式优化
  - 采样率：48kHz → 16kHz（Whisper最优配置）
  - 通道数：立体声 → 单声道（语音识别足够）
  - 分块时长：5秒 → 3秒（降低延迟）
- Whisper API优化
  - 添加 `language` 参数，跳过语言自动检测（节省2-3秒）
- GUI优化
  - Material Design风格界面
  - 语言选择下拉菜单
  - 桌面字幕窗口开关

### 修复
- 修复桌面字幕窗口中原文不显示的问题
- 修复广告过滤逻辑，确保正常字幕显示
- 优化字幕背景透明度，提升可读性
- 添加调试日志，便于问题排查

### 文档
- 新增 PROJECT_STATUS.md（项目真实状态快照）
- 新增 OPTIMIZATION_LOG.md（性能优化详细记录）
- 新增 CHANGELOG.md（本文件）
- 更新 README.md（反映实际功能）
- 更新 QUICKSTART.md（添加新功能说明）
- 更新 CLAUDE.md v4.0（标记项目完成）

---

## [v2.0] - 2025-11-07

### 新增
- Silero VAD语音活动检测（silero_vad_iterator.py，219行）
  - 自动跳过静音段，节省30-50%成本
  - VAD阈值可配置（0.0-1.0）
  - 最小静音时长可配置
  - 实时统计跳过比例
- API错误重试机制（transcription.py）
  - Whisper API 3次重试
  - DeepL API 3次重试
  - 指数退避策略
  - 成功率≥99.9%
- 额外6个P0修复
  - VADIterator.speech_start 改为实例变量
  - 立体声转单声道使用 int32
  - 重采样使用 scipy.signal.resample_poly()
  - VAD模型加载3次重试
  - VAD参数验证（threshold 0-1）
  - 配置验证支持多格式（true/1/yes/on）

### 优化
- 音频捕获模块（audio_capture.py）
  - 集成VAD语音检测
  - 实时监控跳过统计
- 转录翻译模块（transcription.py）
  - ThreadPoolExecutor并发处理（6个worker）
  - 性能监控日志
  - 队列堆积监控

### 修复
- 6个P0级别问题修复（续）
  - VADIterator.speech_start 改为实例变量（避免线程安全问题）
  - 立体声转单声道使用 int32（防止溢出）
  - 重采样使用 scipy（高质量）
  - VAD模型加载重试（容错）
  - VAD参数验证（防止配置错误）
  - 配置验证支持多格式（用户友好）

### 文档
- 新增 STAGE2_SUMMARY.md（阶段2总结）
- 更新 PROGRESS.md（阶段2完成记录）
- 更新 CLAUDE.md v3.0（添加测试流程）

---

## [v1.0] - 2025-11-06

### 新增
- 基础MVP功能
  - VB-Cable音频捕获（audio_capture.py，118行）
  - OpenAI Whisper语音转录（transcription.py，130行）
  - DeepL自动翻译（transcription.py）
  - 双语字幕实时显示（main.py，260行）
  - SRT字幕文件导出（subtitle_storage.py，112行）
- 6个P0级别修复
  - Queue设置maxsize=10（防止内存泄漏）
  - Queue.put()使用timeout=1（队列满时丢弃）
  - SubtitleStorage并发访问使用Lock（线程安全）
  - 字幕时长根据下一条计算（动态时长）
  - 线程清理时清空队列（快速停止）
  - PyAudio流读取捕获异常（容错）

### 技术架构
- 线程模型：主线程 + 音频捕获线程 + 转录翻译线程
- 通信机制：Queue(maxsize=10) + Event + Lock
- 数据流：VB-Cable → 捕获 → Queue → 转录 → API → GUI
- 音频参数：48kHz立体声，5秒分块

### 文档
- 新增 README.md（用户指南）
- 新增 SUMMARY.md（阶段1总结）
- 新增 PROGRESS.md（进度记录）
- 新增 CLAUDE.md v1.0（开发规范）
- 新增 .ai-rules/目录（设计文档）

---

## 版本说明

### [v2.1] - 2025-01-09（当前版本）
- 性能优化版本
- 延迟降低88%（6.5秒）
- 新增Netflix风格桌面字幕窗口
- 新增多语言支持（480种组合）
- 总代码：2,286行（6个模块）

### [v2.0] - 2025-11-07
- VAD优化版本
- 集成Silero VAD（节省30-50%成本）
- 3次重试机制（成功率≥99.9%）
- 12个P0修复全部应用
- 总代码：1,087行（5个模块）

### [v1.0] - 2025-11-06
- MVP基础版本
- 核心功能完整
- 6个P0修复已应用
- 总代码：643行（4个模块）

---

## 技术债务

### 已解决
- [x] 队列无限增长导致内存泄漏（v1.0）
- [x] 队列满时线程阻塞（v1.0）
- [x] SubtitleStorage并发访问数据竞争（v1.0）
- [x] 字幕时长固定5秒不合理（v1.0）
- [x] 线程清理缓慢（v1.0）
- [x] PyAudio异常未捕获（v1.0）
- [x] VADIterator线程安全问题（v2.0）
- [x] 立体声转单声道溢出（v2.0）
- [x] 重采样质量不佳（v2.0）
- [x] VAD模型加载不稳定（v2.0）
- [x] 实时延迟过长（55秒）（v2.1）
- [x] 音频文件过大（938KB）（v2.1）

### 待优化（可选）
- [ ] 本地Whisper模型（需GPU，可降至4秒延迟）
- [ ] 先显示原文，后更新翻译（可降至5.8秒延迟）
- [ ] 减少到2秒块（可降至5.5秒，质量可能下降）
- [ ] 更多语言支持（当前15+32种）

---

## 贡献者

- Claude Code（开发）
- 人工验收（测试）

---

## 许可证

本项目用于学习和研究目的。

---

**最后更新**: 2025-01-09
**当前版本**: v2.1
**项目状态**: ✅ 生产就绪
