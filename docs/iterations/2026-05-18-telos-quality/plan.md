# Plan: TELOS 蒸馏质量优化

> **Goal:** 通过优化 step1 和 step345 的 prompt，解决核心层空洞、维度坍缩、版本膨胀/语言虚浮三个问题。
> **Architecture:** 两个 Task 按 prompt 文件分拆，先 step1 后 step345，每个 Task 同步更新 data dir prompt 和 `_defaults.py` 内置回退。
> **Spec:** `docs/iterations/2026-05-18-telos-quality/spec.md`

---

## 背景阅读

- `docs/iterations/2026-05-18-telos-quality/spec.md`
- `{data_dir}/prompts/layers/growth/telos/engine/step1.md` — 当前 step1 prompt
- `{data_dir}/prompts/layers/growth/telos/engine/step345.md` — 当前 step345 prompt
- `huaqi_src/prompts/_defaults.py` — 内置回退
- `huaqi_src/layers/growth/telos/engine.py` — 引擎代码（dimension cap 安全网）

运行已有测试确认基线：
```bash
pytest tests/unit/layers/growth/ -x --tb=short
```

---

## Task 1: step1 提示词优化（核心层门槛 + 维度互斥）

**Files:**
- Modify: `{data_dir}/prompts/layers/growth/telos/engine/step1.md`
- Modify: `huaqi_src/prompts/_defaults.py` → key `layers.growth.telos.engine.step1`

### Step 1: 写失败测试

```python
# tests/unit/layers/growth/test_telos_engine.py — 新增测试类
class TestStep1PromptQuality:
    """AC-1~4: step1 prompt 质量约束"""

    def test_step1_prompt_includes_implicit_belief_trigger(self, telos_manager):
        """AC-1: 核心层触发条件包含隐含信念/行为选择/是非判断"""
        from huaqi_src.layers.growth.telos.engine import _load_telos_prompt
        prompt = _load_telos_prompt("layers.growth.telos.engine.step1",
                                     telos_index="", active_dimensions="",
                                     source_type="AI_CHAT", timestamp="2026-01-01", content="test")
        assert "行为选择" in prompt or "隐含" in prompt or "决策" in prompt
        assert "是非" in prompt or "对错" in prompt or "判断" in prompt

    def test_step1_prompt_includes_dimension_limit(self, telos_manager):
        """AC-4: 每条信号最多匹配 2 个维度"""
        from huaqi_src.layers.growth.telos.engine import _load_telos_prompt
        prompt = _load_telos_prompt("layers.growth.telos.engine.step1",
                                     telos_index="", active_dimensions="",
                                     source_type="AI_CHAT", timestamp="2026-01-01", content="test")
        assert "2 个维度" in prompt or "两个维度" in prompt or "最多" in prompt
```

### Step 2: 运行确认失败

```bash
pytest tests/unit/layers/growth/test_telos_engine.py::TestStep1PromptQuality -v
```

### Step 3: 写实现

**step1.md 改动点：**

1. **核心层触发扩展（AC-1）**：将 beliefs/models 的触发条件从「用户表达了『我相信/我认为…是对的/是错的』」扩展为：
   - beliefs: 「用户表达了价值观判断、是非选择，或行为中隐含了某种信念假设（如『还是用开源方案吧』隐含了对开源的偏好）」
   - models: 「用户显露出对某件事运作方式的理解框架，或者用某种因果逻辑解释事情（如『因为 A 所以 B，这类事一般都这样』）」

2. **核心层首次初始化（AC-2）**：增加说明——「如果某个核心维度多次被 medium 信号触发（≥3 次），即使没有 strong 信号，也可在 summary 中提示 LLM 关注该维度」

3. **维度数量限制（AC-4）**：增加规则——「每条信号最多匹配 2 个维度。选择关联最强的维度，宁可少匹配合适的，不要多匹配牵强的。如果最佳维度已满 2 个，其余信号特性可通过 new_dimension_hint 提示。」

4. **同步更新 `_defaults.py`**（AC-3）

### Step 4: 运行确认通过

```bash
pytest tests/unit/layers/growth/test_telos_engine.py::TestStep1PromptQuality -v
```

### Step 5: 更新验收测试

将 `TestStep1PromptQuality` 追加到 `tests/smoke_test.py` 末尾的 Feature Acceptance Tests 区域。

---

## Task 2: step345 提示词优化（字数限制 + 禁词 + 关联验证）

**Files:**
- Modify: `{data_dir}/prompts/layers/growth/telos/engine/step345.md`
- Modify: `huaqi_src/prompts/_defaults.py` → key `layers.growth.telos.engine.step345`

### Step 1: 写失败测试

```python
# tests/unit/layers/growth/test_telos_engine.py — 新增测试类
class TestStep345PromptQuality:
    """AC-5~9: step345 prompt 质量约束"""

    def test_step345_prompt_includes_word_limit(self, telos_manager):
        """AC-7: new_content 字数上限 ≤300"""
        from huaqi_src.layers.growth.telos.engine import _load_telos_prompt
        prompt = _load_telos_prompt("layers.growth.telos.engine.step345",
                                     telos_index="", days=7, dimension="learned",
                                     layer="surface", count=3,
                                     signal_summaries="- test\n", current_content="test")
        assert "300 字" in prompt or "不超过" in prompt

    def test_step345_prompt_bans_abstract_words(self, telos_manager):
        """AC-8: 禁止「元认知」「跃迁」「校准」「共建」「范式」「涌现」"""
        from huaqi_src.layers.growth.telos.engine import _load_telos_prompt
        prompt = _load_telos_prompt("layers.growth.telos.engine.step345",
                                     telos_index="", days=7, dimension="learned",
                                     layer="surface", count=3,
                                     signal_summaries="- test\n", current_content="test")
        for word in ["元认知", "跃迁", "校准", "共建", "范式", "涌现"]:
            # Prompt should contain a ban instruction, not the word itself in the output section
            assert word in prompt  # The ban rule must mention them

    def test_step345_prompt_includes_signal_reference_requirement(self, telos_manager):
        """AC-7: 要求引用至少一条具体信号内容"""
        from huaqi_src.layers.growth.telos.engine import _load_telos_prompt
        prompt = _load_telos_prompt("layers.growth.telos.engine.step345",
                                     telos_index="", days=7, dimension="learned",
                                     layer="surface", count=3,
                                     signal_summaries="- test\n", current_content="test")
        assert "具体信号" in prompt or "引用" in prompt or "信号内容" in prompt

    def test_step345_prompt_includes_association_check(self, telos_manager):
        """AC-5: 关联点验证——更新前须指定信号与维度的具体关联"""
        from huaqi_src.layers.growth.telos.engine import _load_telos_prompt
        prompt = _load_telos_prompt("layers.growth.telos.engine.step345",
                                     telos_index="", days=7, dimension="learned",
                                     layer="surface", count=3,
                                     signal_summaries="- test\n", current_content="test")
        assert "关联" in prompt or "关联点" in prompt or "具体关联" in prompt
```

### Step 2: 运行确认失败

```bash
pytest tests/unit/layers/growth/test_telos_engine.py::TestStep345PromptQuality -v
```

### Step 3: 写实现

**step345.md 改动点：**

1. **字数限制（AC-7）**：在任务 2 的 new_content 说明中增加——「new_content 不超过 300 字，保持简洁。必须引用至少一条具体信号内容（如『你在 XX 对话中说了…』），而不是纯抽象概括。」

2. **禁止抽象词（AC-8）**：在任务 2 中增加风格约束——「禁止使用以下术语：元认知、跃迁、校准、共建、范式、涌现。用日常口语表达相同的含义（如不说『元认知跃迁』，说『你开始思考自己是怎么思考的』）。」

3. **关联点验证（AC-5）**：在任务 1 的更新判断标准中增加——「在决定 should_update=true 之前，先确认：能否在这批信号中指定至少一条与当前维度有具体关联的信号？如果不能指定，说明这批信号与该维度无关，应设 should_update=false。」

4. **同步更新 `_defaults.py`**（AC-6, AC-9）

### Step 4: 运行确认通过

```bash
pytest tests/unit/layers/growth/test_telos_engine.py::TestStep345PromptQuality -v
```

### Step 5: 更新验收测试

将 `TestStep345PromptQuality` 追加到 `tests/smoke_test.py` 末尾的 Feature Acceptance Tests 区域。

---

## 变更影响汇总

| 文件 | 改动类型 | 影响范围 |
|------|---------|---------|
| `{data_dir}/prompts/.../step1.md` | 内容优化 | 新信号分析质量 |
| `{data_dir}/prompts/.../step345.md` | 内容优化 | 新维度更新质量 |
| `huaqi_src/prompts/_defaults.py` | 同步 2 个 key | PromptLoader 不可用时的回退 |
| `tests/unit/layers/growth/test_telos_engine.py` | 新增 2 个测试类 | 回归保护 |
| `tests/smoke_test.py` | 追加验收测试 | 功能验收 |

**不改动的文件：**
- `huaqi_src/layers/growth/telos/engine.py` — 已有 95% 相似度跳过和 history cap，本次不需要额外代码改动
- `huaqi_src/layers/growth/telos/manager.py` — 无改动
