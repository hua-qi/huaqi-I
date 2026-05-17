# 测试策略文档

> 整体采用测试驱动开发（TDD）模式。先写测试，再写实现，测试即规范。

---

## 一、TDD 工作流

```
写测试（Red）
    ↓
运行测试，确认失败（确认测试有效）
    ↓
写最小实现让测试通过（Green）
    ↓
重构，保持测试通过（Refactor）
    ↓
下一个测试
```

**核心原则**：
- 没有测试，不写实现代码
- 每次只让一个测试从红变绿
- 测试文件和实现文件同步提交

---

## 二、测试分层

```
tests/
├── conftest.py               ← 全局 fixtures
├── fixtures/                 ← 测试数据文件
│   ├── raw_signals/          ← 各类型的 RAW_SIGNAL 样本
│   ├── telos/                ← TELOS 维度文件样本
│   └── prompts/              ← Prompt 输出样本（用于 mock）
│
├── unit/                     ← 单元测试（最多，最快）
│   ├── layers/
│   │   ├── data/
│   │   │   ├── test_raw_signal_models.py
│   │   │   ├── test_raw_signal_store.py
│   │   │   ├── test_raw_signal_pipeline.py
│   │   │   └── converters/
│   │   │       ├── test_diary_converter.py
│   │   │       ├── test_chat_converter.py
│   │   │       └── test_wechat_converter.py
│   │   ├── growth/
│   │   │   ├── test_telos_models.py
│   │   │   ├── test_telos_manager.py
│   │   │   ├── test_telos_engine.py
│   │   │   ├── test_growth_events.py
│   │   │   └── test_meta.py
│   │   └── capabilities/
│   │       ├── test_reports.py
│   │       ├── test_learning.py
│   │       └── test_pipeline.py
│   ├── agent/
│   │   └── test_state.py
│   └── config/
│       └── test_config.py
│
├── integration/              ← 集成测试（较少，较慢）
│   ├── test_raw_signal_to_telos.py   ← 数据层 → 成长层全流程
│   ├── test_telos_to_agent.py        ← 成长层 → Agent 上下文注入
│   ├── test_cold_start.py            ← 冷启动全流程
│   └── test_scheduler.py            ← 定时任务触发
│
└── e2e/                      ← 端到端测试（最少，最慢）
    ├── test_journal_to_telos.py      ← 写日记到 TELOS 更新完整链路
    └── test_onboarding.py            ← 新用户完整引导流程
```

---

## 三、各模块测试规范

### 3.1 RAW_SIGNAL 模型测试

**文件**：`tests/unit/layers/data/test_raw_signal_models.py`

```python
# 测试覆盖点：
# - 各 source_type 的合法值校验
# - timestamp 必须是合法的 ISO 8601 格式
# - content 不允许为空字符串
# - metadata 按 source_type 校验结构
# - processed / distilled 默认值为 False
# - id 不存在时是否自动生成 UUID
```

**fixture 约定**：

```python
@pytest.fixture
def journal_signal() -> RawSignal:
    """标准日记类型的 RAW_SIGNAL"""

@pytest.fixture
def wechat_signal() -> RawSignal:
    """微信聊天记录类型的 RAW_SIGNAL"""

@pytest.fixture
def absence_signal() -> RawSignal:
    """沉默期类型的 RAW_SIGNAL"""
```

---

### 3.2 RAW_SIGNAL 存储测试

**文件**：`tests/unit/layers/data/test_raw_signal_store.py`

```python
# 测试覆盖点：
# - 写入一条 RAW_SIGNAL 后可以读取到
# - 按 user_id 隔离：用户 A 无法读取用户 B 的数据
# - 按 timestamp 范围查询返回正确结果
# - 按 source_type 过滤返回正确结果
# - 查询 processed=0 只返回未处理的信号
# - 批量写入 N 条后，count 正确
# - 同一 id 写入两次，是否幂等（不重复）
# - distilled 更新后，热记忆查询不再包含该条
# - 数据库文件路径通过 StorageAdapter 注入，不硬编码
```

**关键 fixture**：

```python
@pytest.fixture
def in_memory_store(temp_dir) -> RawSignalStore:
    """使用临时目录的 SQLite，测试结束自动清理"""
```

---

### 3.3 转换器测试

**文件**：`tests/unit/layers/data/converters/test_diary_converter.py`

```python
# 测试覆盖点：
# - Markdown 日记文件 → RawSignal，source_type 正确
# - timestamp 从文件名或 frontmatter 中提取，不使用当前时间
# - 没有时间信息时，使用导入时间并记录警告
# - 空文件不生成 RawSignal
# - frontmatter 中的 mood/tags 写入 metadata
```

```python
# tests/unit/layers/data/converters/test_wechat_converter.py
# 测试覆盖点：
# - 微信导出 txt 文件 → 多条 RawSignal（每条消息一条）
# - participants 写入 metadata
# - 系统消息（撤回、加入群等）过滤掉，不生成 RawSignal
# - 时间戳从消息时间提取
```

---

### 3.4 TELOS 模型测试

**文件**：`tests/unit/layers/growth/test_telos_models.py`

```python
# 测试覆盖点：
# - 8 个标准维度的 layer 分类正确（core/mid/surface）
# - frontmatter 序列化/反序列化正确
# - confidence 范围限制在 0.0-1.0
# - update_count 从历史条目数自动计算
# - 自定义维度可以创建，layer 默认为 surface
# - 归档维度不出现在活跃列表
```

---

### 3.5 TELOS 管理器测试

**文件**：`tests/unit/layers/growth/test_telos_manager.py`

```python
# 测试覆盖点：
# - 初始化后生成 9 个标准维度文件 + INDEX.md + meta.md
# - 读取某维度返回正确内容
# - 更新某维度后，文件内容变更，update_count +1
# - 更新后历史记录新增一条
# - 更新后 INDEX.md 对应行同步刷新
# - 更新触发 Git commit（通过 mock GitAutoCommit）
# - 创建新维度后，文件存在，META 活跃列表更新
# - 归档维度后，文件移入 _archive/，INDEX.md 移除该行
# - 回滚到历史版本后，内容还原，update_count 不变
```

---

### 3.6 TELOS 提炼引擎测试

**文件**：`tests/unit/layers/growth/test_telos_engine.py`

**重点**：引擎调用 LLM，测试时必须 mock LLM，不发真实请求。

```python
# fixture 约定：
@pytest.fixture
def mock_llm():
    """返回预设 JSON 的假 LLM，不调用真实 API"""

# 测试覆盖点（Step 1）：
# - 单条强信号正确识别涉及的维度
# - 自定义维度出现在活跃列表时，能被正确识别
# - 不属于任何维度的信号，new_dimension_hint 不为 null
# - 属于现有维度的信号，new_dimension_hint 为 null
# - emotion/intensity/signal_strength 字段存在且类型正确

# 测试覆盖点（Step 3）：
# - should_update=false 时，Step 4 不被调用
# - 核心层维度要求更多信号才触发（阈值验证）
# - update_type 为 reinforce/challenge/new 之一

# 测试覆盖点（Step 4）：
# - 生成的 new_content 长度 ≤ 100 字
# - history_entry 包含 change 和 trigger 字段

# 测试覆盖点（Step 5）：
# - 核心层更新时 is_growth_event=true
# - 表面层日常更新时 is_growth_event=false
```

---

### 3.7 成长事件测试

**文件**：`tests/unit/layers/growth/test_growth_events.py`

```python
# 测试覆盖点：
# - 成长事件写入后可读取
# - 包含 trigger_signals 列表（RAW_SIGNAL ID）
# - narrative 和 title 字段非空
# - 按时间线查询返回按时间排序的事件列表
# - 用户未确认的事件 user_confirmed 为 null
# - 用户确认后 user_confirmed 为 true
```

---

### 3.8 META 维度测试

**文件**：`tests/unit/layers/growth/test_meta.py`

```python
# 测试覆盖点：
# - 用户反馈写入后出现在 meta.md 的反馈表格
# - 维度创建/归档写入维度演化历史
# - 活跃维度列表更新后，Step 1 prompt 注入正确
# - 同类 new_dimension_hint 累积到阈值触发提案
# - 用户拒绝提案后，记录拒绝，短期不再提案
```

---

### 3.9 冷启动测试

**文件**：`tests/integration/test_cold_start.py`

```python
# 测试覆盖点：
# - 首次启动自动进入问卷流程
# - 对话式推进（问完 Q1 才问 Q2）
# - 用户跳过问题后继续推进
# - 问卷结束后生成正确数量的 TELOS 文件
# - 跳过的问题对应维度不生成文件
# - 所有生成维度的 confidence 为 0.5
# - 用户纠正总结后，对应维度内容更新，META 新增校正记录
# - 完成问卷后引导导入历史数据
# - 跳过导入后正常进入主对话
```

---

### 3.10 全链路集成测试

**文件**：`tests/integration/test_raw_signal_to_telos.py`

```python
# 场景：用户连续 3 天写日记，内容都涉及「方向感缺失」
# 验证：
# - Day 1：写入日记 → RawSignal → Step 1 识别为 challenges 维度弱信号 → 无更新
# - Day 2：同上，累积 2 条
# - Day 3：累积 3 条 + 情感强度高 → Step 3 决定更新 → Step 4 生成新内容
#           → challenges.md 更新 → 成长事件生成（中间层方向性转变）
# - INDEX.md 中 challenges 行同步更新
# - 3 条 RawSignal 的 processed 均变为 1
```

---

## 四、Mock 策略

### 4.1 LLM Mock

所有涉及 LLM 调用的测试，使用 fixture 注入假 LLM：

```python
# tests/conftest.py 新增

@pytest.fixture
def mock_step1_output():
    """Step 1 的标准输出"""
    return {
        "dimensions": ["challenges"],
        "emotion": "negative",
        "intensity": 0.7,
        "signal_strength": "strong",
        "strong_reason": "用户明确表达了困惑",
        "summary": "用户对方向感感到迷茫",
        "new_dimension_hint": None
    }

@pytest.fixture
def mock_step3_output_update():
    """Step 3 决定更新的输出"""
    return {
        "should_update": True,
        "update_type": "challenge",
        "confidence": 0.75,
        "reason": "连续 3 次提到方向感问题",
        "suggested_content": "当前最大挑战是目标感缺失"
    }

@pytest.fixture
def mock_step3_output_skip():
    """Step 3 决定不更新的输出"""
    return {
        "should_update": False,
        "update_type": None,
        "confidence": 0.3,
        "reason": "信号太弱，尚不足以更新",
        "suggested_content": None
    }
```

### 4.2 存储 Mock

测试不使用生产数据库，通过 StorageAdapter 注入临时数据库：

```python
@pytest.fixture
def test_store(temp_dir):
    """指向临时目录的存储适配器"""
    return SQLiteStorageAdapter(db_path=temp_dir / "test.db")

@pytest.fixture
def test_telos_dir(temp_dir):
    """临时 TELOS 目录"""
    telos_dir = temp_dir / "telos"
    telos_dir.mkdir()
    return telos_dir
```

### 4.3 时间 Mock

涉及时间的测试固定时间，避免测试结果随日期变化：

```python
@pytest.fixture
def fixed_now(monkeypatch):
    """固定当前时间为 2026-01-04T10:00:00"""
    import datetime
    fixed = datetime.datetime(2026, 1, 4, 10, 0, 0)
    monkeypatch.setattr(datetime, "datetime", lambda *a, **k: fixed)
    return fixed
```

---

## 五、测试命名规范

```python
# 格式：test_[被测对象]_[场景]_[预期结果]

# ✅ 正确
def test_raw_signal_store_write_returns_id(): ...
def test_telos_manager_update_increments_update_count(): ...
def test_telos_engine_step3_skips_step4_when_no_update(): ...
def test_cold_start_skipped_question_has_no_telos_file(): ...

# ❌ 错误
def test_write(): ...           # 太模糊
def test_telos(): ...           # 太模糊
def test_it_works(): ...        # 无意义
```

---

## 六、测试执行策略

### 6.1 分级执行

```bash
# 开发时（最快，秒级）：只跑单元测试
pytest tests/unit/ -x

# PR 合并前（分钟级）：跑单元 + 集成
pytest tests/unit/ tests/integration/

# 发布前（完整）：跑全部
pytest tests/
```

### 6.2 覆盖率要求

```
layers/data/       ≥ 90%    数据层是基础，必须高覆盖
layers/growth/     ≥ 85%    成长层是核心，高覆盖
layers/capabilities/ ≥ 70%  能力层可适当放宽
agent/             ≥ 75%
config/            ≥ 90%
```

### 6.3 CI 规则

```
单元测试失败     → 禁止合并
集成测试失败     → 禁止合并
覆盖率低于要求   → 警告，不阻断（初期）
e2e 测试失败     → 警告，不阻断（初期）
```

---

## 七、TDD 开发顺序

按依赖关系从底层向上，每层测试通过后再开始上层：

```
Phase 1：数据层（无依赖，最先）
  1. test_raw_signal_models.py
  2. test_raw_signal_store.py
  3. test_diary_converter.py
  4. test_chat_converter.py
  5. test_wechat_converter.py

Phase 2：成长层（依赖数据层）
  6. test_telos_models.py
  7. test_telos_manager.py
  8. test_meta.py
  9. test_telos_engine.py（mock LLM）
  10. test_growth_events.py

Phase 3：集成（数据层 + 成长层联通）
  11. test_raw_signal_to_telos.py

Phase 4：能力层（依赖成长层）
  12. test_reports.py
  13. test_learning.py

Phase 5：冷启动和端到端
  14. test_cold_start.py
  15. test_journal_to_telos.py（e2e）
```

---

**文档版本**：v1.0
**创建时间**：2026-01-04
**开发模式**：TDD（测试驱动开发）
**对应验收清单**：2026-01-04-acceptance-checklist.md
