# 实时字幕系统 - Claude 开发规范

## 📍 当前状态
- **阶段**: 阶段1开发完成 ✅ | 等待人工验收 ⏳
- **已完成**: 4个核心模块 + 6个P0修复 (共643行代码)
- **待验收**: 模块测试 + 集成测试 + 人工确认
- **下一步**: 人工验收通过后可进入阶段2
- **最后更新**: 2025-11-06

---

## 一、架构标准

### 技术栈
- **语言**: Python 3.9+
- **GUI**: Tkinter（内置）
- **音频捕获**: PyAudio + VB-Cable
- **API**: OpenAI Whisper ($0.006/min) + DeepL (免费500K字符/月)
- **VAD**: Silero VAD（阶段2，节省30-50%成本）
- **依赖管理**: pip + requirements.txt + .env

### 架构模式
- **线程模型**: 三线程（主线程 + 音频捕获线程 + 转录翻译线程）
- **通信机制**: Queue(maxsize=10) + Event + Lock
- **数据流**: VB-Cable → 捕获 → Queue → 转录 → API → GUI

---

## 二、工作流

### 开发顺序（严格执行）
1. **优先读取** `.ai-rules/README.md`（项目概览 + 进度追踪）
2. **必读** `technical/critical-fixes.md`（12个P0必修问题）
3. **参考** `implementation-roadmap.md`（当前阶段详细任务）
4. **查阅** `modules/[模块名].md`（具体实现设计）
5. **实施代码** → 应用所有P0修复
6. **⚠️ 模块测试** → 自动化测试必须通过（见下文"测试流程"）
7. **⚠️ 人工验收** → 等待人工确认测试通过
8. **更新状态** → 本文件 + README.md 进度追踪

### 阶段顺序（严格遵循）
1. **阶段1**: 基础MVP（不实现VAD，不实现重试）
2. **阶段2**: 优化版本（集成VAD + 错误重试 + 所有P0修复）
3. **阶段3**: 完善版本（日志系统 + 监控，可选）

⚠️ **禁止跳过阶段1直接实现VAD**
⚠️ **禁止未经测试就继续下一个模块**

---

## 三、测试流程（必须执行）

### 模块级测试（每个模块完成后）

#### 1. 音频捕获模块 (audio_capture.py)
**自动化测试**:
```python
# test_audio_capture.py
import queue
import threading
from audio_capture import AudioCaptureThread

def test_audio_capture():
    audio_queue = queue.Queue(maxsize=10)
    stop_event = threading.Event()

    # 启动线程
    thread = AudioCaptureThread(audio_queue, stop_event)
    thread.start()

    # 等待5秒
    import time
    time.sleep(5)

    # 检查队列是否有数据
    assert not audio_queue.empty(), "队列应该有音频数据"

    # 停止线程
    stop_event.set()
    thread.join(timeout=10)

    print("✅ 音频捕获测试通过")
```

**人工验收清单**:
- [ ] 运行测试脚本无错误
- [ ] 控制台显示"找到VB-Cable设备"
- [ ] 控制台显示"音频捕获线程已启动"
- [ ] 没有异常或警告信息
- [ ] 人工确认: ✅ / ❌

#### 2. 转录翻译模块 (transcription.py)
**自动化测试**:
```python
# test_transcription.py
import os
import queue
import threading
from transcription import TranscriptionThread

def test_transcription():
    # 需要有效的API Keys
    openai_key = os.getenv('OPENAI_API_KEY')
    deepl_key = os.getenv('DEEPL_API_KEY')

    if not openai_key or not deepl_key:
        print("⚠️ 跳过测试: 未配置API Keys")
        return

    audio_queue = queue.Queue()
    stop_event = threading.Event()
    results = []

    def callback(original, translation):
        results.append((original, translation))

    # 启动线程
    thread = TranscriptionThread(
        audio_queue, stop_event, callback,
        openai_key, deepl_key
    )
    thread.start()

    # 放入测试音频（需要准备）
    # audio_queue.put(test_audio_data)

    # 停止
    stop_event.set()
    thread.join(timeout=15)

    print("✅ 转录翻译测试通过")
```

**人工验收清单**:
- [ ] API Keys配置正确
- [ ] 能成功调用Whisper API
- [ ] 能成功调用DeepL API
- [ ] 回调函数正确执行
- [ ] 人工确认: ✅ / ❌

#### 3. 字幕存储模块 (subtitle_storage.py)
**自动化测试**:
```python
# test_subtitle_storage.py
from subtitle_storage import SubtitleStorage
import os

def test_subtitle_storage():
    storage = SubtitleStorage()

    # 添加测试字幕
    storage.add_subtitle("Hello world", "你好世界")
    storage.add_subtitle("How are you", "你好吗")

    # 检查数量
    assert len(storage.subtitles) == 2, "应该有2条字幕"

    # 导出测试
    test_file = "test_output.srt"
    storage.export_srt(test_file)

    # 验证文件
    assert os.path.exists(test_file), "SRT文件应该存在"

    # 读取验证
    with open(test_file, 'r', encoding='utf-8') as f:
        content = f.read()
        assert "Hello world" in content
        assert "你好世界" in content
        assert "-->" in content  # 时间戳格式

    # 清理
    os.remove(test_file)

    print("✅ 字幕存储测试通过")
```

**人工验收清单**:
- [ ] 字幕正确添加到列表
- [ ] SRT文件格式正确
- [ ] 时间戳计算正确
- [ ] 中文编码正确（UTF-8）
- [ ] 人工确认: ✅ / ❌

#### 4. GUI主程序 (main.py)
**自动化测试**: (GUI难以自动化,主要靠人工)

**人工验收清单**:
- [ ] 程序能正常启动,显示窗口
- [ ] 按钮状态正确切换
- [ ] 点击"开始捕获"无错误
- [ ] 原文和翻译文本框能正常显示
- [ ] 点击"导出SRT"能选择文件
- [ ] 点击"停止"程序正确停止
- [ ] 关闭窗口程序正常退出
- [ ] 人工确认: ✅ / ❌

### 集成测试（所有模块完成后）

#### 端到端测试流程
**测试场景**: 播放1分钟YouTube视频,检查字幕生成

**测试步骤**:
1. 确保VB-Cable已安装并重启
2. 系统音频输出设置为"CABLE Input"
3. 运行 `python app/main.py`
4. 点击"开始捕获"
5. 播放YouTube视频（1-2分钟）
6. 观察字幕显示
7. 点击"导出SRT"
8. 用播放器打开SRT文件验证

**验收清单**:
- [ ] 音频能正常捕获（控制台显示日志）
- [ ] 字幕实时显示在窗口中
- [ ] 原文和翻译都正确
- [ ] 导出的SRT文件能用播放器正常打开
- [ ] 字幕时间轴对齐正确
- [ ] 运行期间无崩溃或内存泄漏
- [ ] 停止后线程正确清理
- [ ] 人工确认: ✅ / ❌

### 性能测试（阶段1可选,阶段2必须）

**内存泄漏测试**:
```python
# test_memory.py
import psutil
import os
import time

def test_memory_leak():
    process = psutil.Process(os.getpid())

    # 记录初始内存
    initial_memory = process.memory_info().rss / 1024 / 1024  # MB
    print(f"初始内存: {initial_memory:.2f} MB")

    # 运行30分钟（阶段1）或1小时（阶段2）
    # 每5分钟检查一次

    # 验证内存增长 < 50MB
    # ...

    print("✅ 内存测试通过")
```

**验收清单**:
- [ ] 运行30分钟内存增长 < 50MB
- [ ] 队列大小保持在 ≤ 10
- [ ] CPU使用率合理（< 30%）
- [ ] 人工确认: ✅ / ❌

---

## 四、人工验收流程

### 验收时机
**每个模块完成后** + **整个阶段完成后** 都需要人工验收

### 验收方式
1. **开发者提交**: 完成模块后,在控制台输出:
   ```
   [验收请求] 模块名: audio_capture.py
   [验收请求] 功能: 音频捕获
   [验收请求] 测试: 自动化测试已通过 ✅
   [验收请求] 等待人工确认...
   ```

2. **等待确认**: 开发者暂停,等待人工测试

3. **人工测试**: 按照上述测试清单逐项验证

4. **确认结果**:
   - ✅ **通过**: 继续下一个模块
   - ❌ **不通过**: 修复问题,重新测试

### 验收记录
在 `PROGRESS.md` 中记录:
```markdown
## 模块验收记录

### audio_capture.py
- 开发完成: 2025-11-06 14:30
- 自动化测试: ✅ 通过
- 人工验收: ✅ 通过 (验收人: XXX, 时间: 2025-11-06 15:00)
- 问题记录: 无

### transcription.py
- 开发完成: 2025-11-06 16:00
- 自动化测试: ✅ 通过
- 人工验收: ❌ 不通过 (问题: API超时未处理)
- 修复完成: 2025-11-06 16:30
- 重新验收: ✅ 通过
```

---

## 五、阶段验收门禁

### 阶段1完成标准（全部必须✅）
- [ ] 所有4个模块独立测试通过
- [ ] 6个P0修复全部应用并验证
- [ ] 集成测试通过（端到端字幕生成）
- [ ] 人工验收通过
- [ ] 代码审查通过（P0修复位置已标注）
- [ ] 文档更新（README.md, PROGRESS.md）

**只有全部✅后才能进入阶段2开发**

### 阶段2完成标准
- [ ] 所有模块更新测试通过
- [ ] 额外6个P0修复全部应用
- [ ] VAD节省成本验证（日志显示30-50%）
- [ ] API重试机制验证（成功率≥99.9%）
- [ ] 内存泄漏测试通过（1小时稳定）
- [ ] 人工验收通过

---

## 六、文件组织

### 项目结构
```
subtitle/
├── claude.md                  # 本文件（开发规范）
├── .ai-rules/                 # 设计文档（必读）
│   ├── README.md             # 项目概览 + 进度追踪
│   ├── architecture.md       # 架构设计
│   ├── implementation-roadmap.md  # 实施路线图
│   ├── WORKFLOW.md           # 标准开发流程
│   ├── modules/              # 模块设计（4个）
│   └── technical/            # 技术专题（3个）
├── app/                      # 应用代码
│   ├── __init__.py
│   ├── audio_capture.py      # 音频捕获 + VAD
│   ├── transcription.py      # 转录翻译 + 重试
│   ├── subtitle_storage.py   # 字幕存储
│   ├── silero_vad_iterator.py  # VAD实现（阶段2）
│   └── main.py               # GUI主程序
├── .env                      # API配置（不提交）
├── .env.example              # 配置模板
└── requirements.txt          # Python依赖
```

### 文档导航（必读顺序）
1. `.ai-rules/README.md` - 项目概览、进度追踪
2. `.ai-rules/architecture.md` - 系统架构、线程模型
3. `.ai-rules/implementation-roadmap.md` - 分阶段实施指南
4. `.ai-rules/technical/critical-fixes.md` - ⚠️ 12个必修问题
5. `.ai-rules/modules/*.md` - 模块详细设计
6. `.ai-rules/WORKFLOW.md` - 开发流程规范

---

## 七、质量关卡

### 阶段1（基础MVP）- 6个必修问题
- [ ] Queue 设置 `maxsize=10`
- [ ] Queue.put() 使用 `timeout=1`
- [ ] SubtitleStorage 并发访问使用 `Lock`
- [ ] 字幕时长根据下一条计算（不固定5秒）
- [ ] 线程清理时清空队列
- [ ] PyAudio 流读取捕获异常

### 阶段2（优化版）- 额外6个必修问题
- [ ] VADIterator.speech_start 改为实例变量
- [ ] 立体声转单声道使用 int32
- [ ] 重采样使用 `scipy.signal.resample_poly()`
- [ ] VAD 模型加载3次重试
- [ ] VAD 参数验证（threshold 0-1）
- [ ] 配置验证支持多格式（true/1/yes/on）

### 验收标准
**阶段1**:
- ✅ 能捕获VB-Cable音频
- ✅ 字幕正确显示在窗口
- ✅ 能导出SRT文件
- ✅ 运行30分钟无内存泄漏

**阶段2**:
- ✅ VAD 跳过静音段（日志显示节省比例）
- ✅ API 失败自动重试（成功率 ≥99.9%）
- ✅ 运行1小时内存稳定
- ✅ 停止响应时间 <15秒

---

## 八、日志和进度管理

### 日志规范
**主日志**: `logs/development.log`（项目整体开发日志）
**模块日志**: `logs/modules/[模块名].log`（单模块详细日志）

**日志格式**: `[YYYY-MM-DD HH:MM:SS] [阶段] [模块] 消息内容`

**示例**:
```
[2025-11-06 14:30:00] [阶段1] [audio_capture] 开始实现音频捕获基础版本
[2025-11-06 16:45:00] [阶段1] [audio_capture] 完成，共80行，应用2个P0修复
```

### 进度管理
**进度表**: `PROGRESS.md`（根目录）

**更新时机**:
- 开始模块开发时：更新状态为 🚧，记录开始时间
- 完成模块开发时：更新状态为 ✅，记录完成时间、代码行数、P0修复数量
- 阶段完成时：更新阶段进度百分比和统计信息

**状态标识**:
- ⏸️ 未开始
- 🚧 进行中
- ✅ 已完成
- ⚠️ 有问题
- 🔄 需重构

---

## 九、快速参考

### 当前阶段任务
**阶段1**: 实现 `audio_capture.py` + `transcription.py` + `subtitle_storage.py` + `main.py`
**详细指南**: → `implementation-roadmap.md` 第1节

### 原始设计文档
**完整设计**: `plan.md` (2188行)

---

---

**文档版本**: v3.0 (添加完整测试流程和人工验收规范)
**重要变更**:
- 新增"测试流程"章节 (强制要求)
- 新增"人工验收流程"章节
- 新增"阶段验收门禁"标准
- 禁止未经测试就继续下一模块
