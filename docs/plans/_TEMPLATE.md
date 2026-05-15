# Plan: <feature-name>

> **Plan 是基于 Spec 的具体实施方案。Spec 定义 WHAT，Plan 定义 HOW。**

**Goal:** <一句话目标>
**Architecture:** <分几个阶段，每个阶段做什么>
**Spec:** `docs/specs/<feature-name>.md`

---

## 背景阅读

实施前必读：
- `docs/specs/<feature-name>.md` — 功能规格
- <相关源码文件列表>

运行已有测试确认基线：
```bash
pytest tests/ -x --tb=short
```

---

## Task 1: <阶段名称>

**Files:**
- Modify: `<file-path>`
- Create: `<file-path>`

### Step 1: 写失败测试

```python
# <test-file-path>
<test-code>
```

### Step 2: 运行确认失败

```bash
pytest tests/<test-file> -v
```

期望：测试失败，错误信息为 <expected-error>

### Step 3: 写实现

<what to change>

### Step 4: 运行确认通过

```bash
pytest tests/<test-file> -v
```

期望：测试通过

### Step 5: 更新验收测试

将核心场景测试加入 `tests/smoke_test.py`，按以下格式：

```python
class Test<FeatureName>:
    """<feature-name> 功能验收。"""

    def test_<scenario>(self, ...):
        ...
```

---

## Task 2: <下一阶段>

...
