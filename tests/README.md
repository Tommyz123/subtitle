# 测试说明

## 测试文件

### 1. test_subtitle_storage.py
**测试内容**: 字幕存储和SRT导出功能
**运行条件**: 无特殊要求
**运行命令**:
```bash
cd c:\Users\zhi89\Desktop\ai\sample\subtitle
python tests/test_subtitle_storage.py
```

**验收标准**:
- ✅ 所有测试通过
- ✅ SRT文件格式正确
- ✅ 时间戳计算正确
- ✅ 中文编码正确

---

### 2. test_audio_capture.py
**测试内容**: VB-Cable音频捕获功能
**运行条件**:
- VB-Cable已安装并重启
- 系统音频输出设为 "CABLE Input"
- 测试时播放音频

**运行命令**:
```bash
cd c:\Users\zhi89\Desktop\ai\sample\subtitle
python tests/test_audio_capture.py
```

**验收标准**:
- ✅ 找到VB-Cable设备
- ✅ 线程成功启动
- ✅ 队列接收到音频数据
- ✅ 音频块大小正确(~960KB)
- ✅ 线程正确停止

---

### 3. 集成测试 (手动)
**测试内容**: 完整功能链路
**运行命令**:
```bash
python app/main.py
```

**测试步骤**:
1. 点击"开始捕获"
2. 播放YouTube视频(1-2分钟)
3. 观察字幕实时显示
4. 点击"导出SRT"
5. 用播放器打开验证

**验收标准**:
- ✅ GUI正常显示
- ✅ 字幕实时更新
- ✅ 原文和翻译都正确
- ✅ SRT文件能正常播放
- ✅ 停止按钮正常工作

---

## 人工验收流程

完成所有测试后,请在claude.md中记录验收结果:

### 验收记录模板

```markdown
## 模块验收记录

### subtitle_storage.py
- 开发完成: 2025-11-06
- 自动化测试: ✅ 通过
- 人工验收: ✅ 通过 (验收人: XXX)
- 问题记录: 无

### audio_capture.py
- 开发完成: 2025-11-06
- 自动化测试: ✅ 通过
- 人工验收: ✅ 通过 (验收人: XXX)
- 问题记录: 无

### 集成测试
- 测试日期: 2025-11-06
- 测试场景: YouTube视频字幕生成
- 测试结果: ✅ 通过
- 验收人: XXX
```

---

## 阶段1验收门禁

所有以下项必须✅才能进入阶段2:

- [ ] test_subtitle_storage.py 通过
- [ ] test_audio_capture.py 通过
- [ ] 集成测试通过
- [ ] 6个P0修复验证通过
- [ ] 人工验收确认
- [ ] 文档更新完成

---

**最后更新**: 2025-11-06
