# 快速启动指南

## 🚀 5分钟快速开始

### 第1步: 安装VB-Cable驱动
1. 下载: https://vb-audio.com/Cable/
2. 安装并**重启电脑** (必须重启!)
3. 验证: 控制面板 → 声音 → 播放 → 看到 "CABLE Input"

### 第2步: 配置系统音频
1. 右键任务栏音量图标 → "打开声音设置"
2. 输出设备选择: **CABLE Input (VB-Audio Virtual Cable)**
3. (可选) 配置监听输出,避免听不到声音:
   - 控制面板 → 声音 → 录制
   - 右键 "CABLE Output" → 属性
   - 侦听 → 勾选"侦听此设备" → 应用

### 第3步: 获取API Keys
1. **OpenAI API Key**
   - 注册: https://platform.openai.com/
   - 创建API Key: https://platform.openai.com/api-keys
   - 格式: `sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

2. **DeepL API Key**
   - 注册: https://www.deepl.com/pro-api
   - 免费版: 500K字符/月
   - 格式: `xxxxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx:fx`

### 第4步: 安装Python依赖
```bash
cd c:\Users\zhi89\Desktop\ai\sample\subtitle
pip install -r requirements.txt
```

**依赖说明**:
- `torch`: VAD模型 (~200MB,首次安装较慢)
- `scipy`: 高质量音频重采样
- `openai`, `deepl`: API客户端
- `pyaudio`: 音频捕获
- `numpy`: 音频处理

### 第5步: 配置API Keys
```bash
# 复制配置模板
copy .env.example .env

# 编辑.env文件,填入你的API Keys
notepad .env
```

**最小配置** (.env):
```bash
OPENAI_API_KEY=sk-your_openai_key_here
DEEPL_API_KEY=your_deepl_key_here:fx
ENABLE_VAD=true
```

### 第6步: 运行程序
```bash
python app/main.py
```

---

## 🎬 使用流程

### 基本操作
1. **启动程序** → 看到GUI窗口
2. **点击"开始捕获"** → 控制台显示:
   ```
   [INFO] VAD功能: 启用
   [INFO] VAD模型加载成功 (阈值: 0.5, 最小静音: 500ms)
   [INFO] 找到VB-Cable设备: CABLE Output (索引: 1)
   [INFO] 音频捕获线程已启动
   [INFO] 转录翻译线程已启动
   ```
3. **播放视频** (YouTube, 本地视频等)
4. **观察字幕** → 实时显示在窗口中
5. **点击"停止"** → 看到VAD统计:
   ```
   [VAD最终统计] 总共 40 块, 跳过 16 块, 节省 40.0% 成本
   ```
6. **导出SRT** → 选择保存路径

### VAD节省成本示例
运行30分钟视频:
```
[VAD统计] 已跳过 15/40 块, 节省 37.5% 成本
[VAD统计] 已跳过 32/80 块, 节省 40.0% 成本
[VAD统计] 已跳过 50/120 块, 节省 41.7% 成本
```

**成本对比**:
- 无VAD: 30分钟 × $0.006 = $0.18
- 有VAD (40%节省): $0.108
- **每月节省** (每天1小时): $4.32

---

## ⚙️ 配置选项

### VAD配置 (.env)
```bash
# 启用/禁用VAD (推荐启用)
ENABLE_VAD=true

# VAD阈值 (0.0-1.0)
# 0.3 = 宽松 (捕获更多,成本略高)
# 0.5 = 平衡 (推荐)
# 0.7 = 严格 (节省成本,可能漏检)
VAD_THRESHOLD=0.5

# 最小静音时长 (毫秒)
# 避免短暂停顿被误判为静音
VAD_MIN_SILENCE_MS=500
```

### 语言配置 (.env)
```bash
# 源语言 (Whisper)
SOURCE_LANGUAGE=en

# 目标语言 (DeepL)
TARGET_LANGUAGE=ZH
```

---

## 🐛 故障排查

### 问题1: "未找到VB-Cable设备"
**原因**: VB-Cable未安装或未重启
**解决**:
1. 重新安装VB-Cable
2. **重启电脑** (必须!)
3. 检查: 控制面板 → 声音 → 播放 → 有"CABLE Input"

### 问题2: "请在.env文件中配置API Keys"
**原因**: .env文件不存在或配置错误
**解决**:
1. 确保.env文件在项目根目录
2. 检查API Keys格式正确
3. 确保没有多余空格

### 问题3: VAD加载失败
**控制台显示**:
```
[WARNING] VAD加载失败,禁用VAD功能
```
**原因**: torch未安装或网络问题
**解决**:
```bash
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### 问题4: 听不到系统声音
**原因**: 输出设备改为CABLE Input后,声音被捕获到虚拟设备
**解决**: 配置监听输出 (见第2步)

### 问题5: API调用失败
**控制台显示**:
```
[ERROR] Whisper API调用失败 (尝试1/3): ...
```
**原因**: API Key错误或网络问题
**解决**:
1. 检查API Key是否正确
2. 检查网络连接
3. 程序会自动重试3次

---

## 📊 性能优化建议

### 降低延迟
```bash
# .env
AUDIO_CHUNK_DURATION=3  # 默认5秒
```
- 优点: 延迟降低到3秒
- 缺点: API调用频繁,成本稍高

### 降低成本
```bash
# .env
ENABLE_VAD=true
VAD_THRESHOLD=0.6  # 更严格
VAD_MIN_SILENCE_MS=700  # 更长静音
```
- 优点: 节省成本可能超过50%
- 缺点: 可能遗漏一些轻声语音

---

## 📁 项目结构

```
subtitle/
├── app/
│   ├── main.py                  # GUI主程序 ← 运行这个
│   ├── audio_capture.py         # 音频捕获 + VAD
│   ├── transcription.py         # 转录翻译 + 重试
│   ├── subtitle_storage.py      # 字幕存储
│   └── silero_vad_iterator.py   # VAD模型
├── .env                         # 你的配置 (不提交)
├── .env.example                 # 配置模板
└── requirements.txt             # Python依赖
```

---

## 🎓 学习资源

- **完整文档**: [claude.md](claude.md)
- **开发记录**: [PROGRESS.md](PROGRESS.md)
- **阶段2总结**: [STAGE2_SUMMARY.md](STAGE2_SUMMARY.md)
- **技术细节**: `.ai-rules/`目录

---

## 💡 常见问题

**Q: 可以用于直播吗?**
A: 可以,但有5-8秒延迟(音频分块+API调用)

**Q: 支持哪些语言?**
A: Whisper支持90+语言,DeepL支持30+语言

**Q: 可以离线使用吗?**
A: 不可以,需要调用OpenAI和DeepL API

**Q: 能否导出到视频软件?**
A: 可以,导出的SRT文件可导入Premiere/剪映等软件

**Q: 费用大概多少?**
A: 每天1小时约$0.22 (启用VAD后),每月约$6.5

---

**最后更新**: 2025-11-07
**版本**: v2.0 (阶段2)
**状态**: ✅ 生产就绪
