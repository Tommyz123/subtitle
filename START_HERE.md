# 快速启动指南

## ✅ 依赖已安装

所有Python包已安装:
- ✅ openai
- ✅ deepl
- ✅ pyaudio
- ✅ python-dotenv

## 🚀 启动步骤

### 方式1: 使用批处理脚本 (推荐)

双击 `run.bat` 文件

### 方式2: 命令行启动

```bash
cd C:\Users\zhi89\Desktop\ai\sample\subtitle
python app/main.py
```

## ⚙️ 配置API Keys (首次运行必须)

1. 复制配置文件:
   ```bash
   copy .env.example .env
   ```

2. 编辑 `.env` 文件,填入你的API Keys:
   ```
   OPENAI_API_KEY=sk-你的OpenAI密钥
   DEEPL_API_KEY=你的DeepL密钥
   ```

**获取API Keys**:
- OpenAI: https://platform.openai.com/api-keys
- DeepL: https://www.deepl.com/pro-api (有免费额度)

## 🎤 VB-Cable设置 (首次使用必须)

1. **下载安装**: https://vb-audio.com/Cable/
2. **重启电脑** (必须!)
3. **设置音频**:
   - 右键任务栏音量图标 → 打开声音设置
   - 输出设备选择: "CABLE Input (VB-Audio Virtual Cable)"
4. **设置监听** (否则听不到声音):
   - 控制面板 → 声音 → 录制
   - 找到"CABLE Output" → 属性 → 监听
   - 勾选"侦听此设备" → 选择你的扬声器

## 📋 测试验收

### 测试1: 字幕存储模块
```bash
python tests/test_subtitle_storage.py
```
**预期**: 所有测试通过 ✅

### 测试2: 完整功能测试

1. 启动程序: `python app/main.py`
2. 点击"开始捕获"
3. 播放YouTube视频
4. 查看字幕显示
5. 点击"导出SRT"

## ❓ 遇到问题?

### "未找到.env文件"
→ 运行 `copy .env.example .env` 并配置API Keys

### "未找到VB-Cable设备"
→ 确保VB-Cable已安装并重启电脑

### "API调用失败"
→ 检查.env文件中的API Keys是否正确

### 程序无法启动
→ 确保在正确的目录: `C:\Users\zhi89\Desktop\ai\sample\subtitle`

## 📖 详细文档

- **完整说明**: [README.md](README.md)
- **安装指南**: [INSTALL.md](INSTALL.md)
- **测试说明**: [tests/README.md](tests/README.md)
- **开发规范**: [claude.md](claude.md)

---

**当前状态**: 阶段1开发完成,等待人工验收 ⏳

**验收任务**:
1. 配置API Keys
2. 运行程序测试
3. 验证字幕生成功能
4. 按照[claude.md](claude.md)记录验收结果

---

**最后更新**: 2025-11-06
