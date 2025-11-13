# 安装和运行指南

## 快速开始

### 步骤1: 安装Python依赖

```bash
cd C:\Users\zhi89\Desktop\ai\sample\subtitle
pip install -r requirements.txt
```

**注意**:
- 如果 `pyaudio` 安装失败,请使用预编译版本:
  ```bash
  pip install pipwin
  pipwin install pyaudio
  ```
- 或者从这里下载对应版本: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio

### 步骤2: 配置API Keys

1. 复制配置模板:
   ```bash
   copy .env.example .env
   ```

2. 编辑 `.env` 文件,填入你的API Keys:
   ```
   OPENAI_API_KEY=sk-your-key-here
   DEEPL_API_KEY=your-key-here
   ```

### 步骤3: 安装VB-Cable (如果还没安装)

1. 下载: https://vb-audio.com/Cable/
2. 解压并运行安装程序
3. **重启电脑** (重要!)
4. 设置系统音频输出为 "CABLE Input"

### 步骤4: 运行程序

```bash
cd C:\Users\zhi89\Desktop\ai\sample\subtitle
python app/main.py
```

---

## 测试指南

### 测试1: 字幕存储模块 (无需API Keys)

```bash
python tests/test_subtitle_storage.py
```

**预期结果**: 所有测试通过 ✅

### 测试2: 音频捕获模块 (需要VB-Cable)

```bash
python tests/test_audio_capture.py
```

**运行前确保**:
- VB-Cable已安装并重启
- 有音频正在播放

### 测试3: 完整集成测试

1. 运行程序:
   ```bash
   python app/main.py
   ```

2. 点击"开始捕获"

3. 播放YouTube视频(1-2分钟)

4. 观察字幕显示

5. 点击"导出SRT"

---

## 常见问题

### Q: pip install pyaudio 失败

**解决方案1** (推荐):
```bash
pip install pipwin
pipwin install pyaudio
```

**解决方案2**:
从 https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio 下载对应Python版本的whl文件,然后:
```bash
pip install PyAudio-0.2.13-cp312-cp312-win_amd64.whl
```

### Q: ModuleNotFoundError: No module named 'XXX'

确保所有依赖都已安装:
```bash
pip install -r requirements.txt
```

### Q: 未找到VB-Cable设备

1. 确认VB-Cable已安装
2. 确认已重启电脑
3. 运行测试看能否找到设备:
   ```bash
   python tests/test_audio_capture.py
   ```

### Q: API调用失败

1. 检查 `.env` 文件是否存在
2. 检查API Keys是否正确
3. 检查网络连接

---

## 验收流程

按照 [claude.md](claude.md) 第三章节的测试流程进行验收:

1. ✅ 运行 `test_subtitle_storage.py` - 已通过
2. ⏳ 运行 `test_audio_capture.py` - 待测试
3. ⏳ 运行 `python app/main.py` - 待测试
4. ⏳ 集成测试 (播放视频) - 待测试

全部通过后,在 [claude.md](claude.md) 中记录验收结果。

---

**最后更新**: 2025-11-06
