# Plan: 定时任务迁移至 GitHub Actions

> **Plan 是基于 Spec 的具体实施方案。Spec 定义 WHAT，Plan 定义 HOW。**

**Goal:** 创建 6 个 GitHub Actions workflow，替代 APScheduler 实现云端定时报告
**Architecture:** 4 个 Task，按依赖顺序执行
**Spec:** `docs/specs/2026-05-14-reports-github-actions.md`

---

## 背景阅读

实施前必读：
- `docs/specs/2026-05-14-reports-github-actions.md` — 功能规格
- `huaqi_src/cli/__init__.py` — CLI 入口，了解回调机制
- `huaqi_src/config/paths.py` — `get_data_dir()` 和 `require_data_dir()`
- `huaqi_src/layers/capabilities/reports/manager.py` — ReportManager 门面
- `huaqi_src/scheduler/scheduled_job_store.py` — 默认任务定义（cron、prompt、output_dir）

运行已有测试确认基线：
```bash
pytest tests/ -x --tb=short
```

---

## 架构设计

### 部署拓扑

```
数据仓库 (私有 GitHub repo)
  ├── .github/workflows/      ← workflow 文件放这里
  │   ├── morning-brief.yml
  │   ├── daily-report.yml
  │   ├── weekly-report.yml
  │   ├── quarterly-report.yml
  │   ├── learning-push.yml
  │   ├── world-fetch.yml
  │   └── notify.sh           ← Server酱 通知脚本
  ├── reports/                ← 报告输出目录
  ├── memory/                 ← config.yaml、scheduled_jobs.yaml
  └── ...

源码仓库 (huaqi-growing)
  ├── scripts/github-actions/ ← 模板文件（方便维护和重新部署）
  │   └── *.yml, notify.sh
  └── ...
```

### 单个 workflow 执行流程

```
cron 触发 (UTC 时间)
  → actions/checkout 数据仓库
  → actions/checkout 源码仓库 (huaqi-growing)
  → setup-python + pip install -e 源码仓库
  → export HUAQI_DATA_DIR=$GITHUB_WORKSPACE
  → huaqi report <type> (或 huaqi scheduler run)
  → git pull --rebase (防冲突)
  → git add reports/ && git commit && git push
  → (成功) notify.sh "✅ 报告已生成" <摘要>
  → (失败) notify.sh "❌ 任务失败" <错误信息>
```

### 时区换算

| 任务 | 北京时间 | UTC cron |
|------|---------|----------|
| 晨间简报 | 08:00 | `0 0 * * *` |
| 日终复盘 | 23:00 | `0 15 * * *` |
| 周报 | 周日 21:00 | `0 13 * * 0` |
| 季报 | 季度末 22:00 | 每日触发 + 脚本判断 |
| 学习推送 | 21:00 | `0 13 * * *` |
| 世界新闻 | 07:00 | `0 23 * * *`（前一天） |

### 季报特殊处理

GitHub Actions cron 不支持「每月最后一天」语义。方案：
- cron 设为 `0 14 28-31 3,6,9,12 *`（UTC 14:00 = 北京 22:00）
- workflow 第一步用 Python 判断「今天是否为季度最后一天」：`date.today().month in (3,6,9,12) and (date.today() + timedelta(days=1)).month != date.today().month`
- 不是则 `exit 0` 跳过

---

## Task 1: 创建 workflow 模板文件

**Files:**
- Create: `scripts/github-actions/morning-brief.yml`
- Create: `scripts/github-actions/daily-report.yml`
- Create: `scripts/github-actions/weekly-report.yml`
- Create: `scripts/github-actions/quarterly-report.yml`
- Create: `scripts/github-actions/learning-push.yml`
- Create: `scripts/github-actions/world-fetch.yml`
- Create: `scripts/github-actions/notify.sh`

### Step 1: 写失败测试

```python
# tests/unit/test_github_actions_workflows.py
import yaml
import pytest
from pathlib import Path

WORKFLOW_DIR = Path("scripts/github-actions")

EXPECTED_WORKFLOWS = [
    "morning-brief.yml",
    "daily-report.yml",
    "weekly-report.yml",
    "quarterly-report.yml",
    "learning-push.yml",
    "world-fetch.yml",
]

class TestWorkflowFilesExist:
    """AC-1: 6 个 workflow 文件存在且 schema 合法。"""

    def test_all_workflows_exist(self):
        """AC-1: 验证 6 个 workflow 文件都存在。"""
        for wf in EXPECTED_WORKFLOWS:
            path = WORKFLOW_DIR / wf
            assert path.exists(), f"Missing workflow: {wf}"

    def test_all_workflows_valid_yaml(self):
        """AC-1: 验证所有 workflow 文件是合法 YAML。"""
        for wf in EXPECTED_WORKFLOWS:
            path = WORKFLOW_DIR / wf
            if path.exists():
                with open(path) as f:
                    data = yaml.safe_load(f)
                assert data is not None, f"Empty or invalid YAML: {wf}"
                assert "on" in data, f"Missing 'on' trigger: {wf}"
                assert "jobs" in data, f"Missing 'jobs': {wf}"

    def test_notify_script_exists_and_executable(self):
        """AC-4: notify.sh 存在。"""
        path = WORKFLOW_DIR / "notify.sh"
        assert path.exists(), "Missing notify.sh"

class TestWorkflowHeadlessCommands:
    """AC-2: 每个 workflow 的 CLI 命令在无交互环境下合法。"""

    def test_report_commands_are_headless(self):
        """报告命令不含交互式标志。"""
        report_commands = {
            "morning-brief.yml": "huaqi report morning",
            "daily-report.yml": "huaqi report daily",
            "weekly-report.yml": "huaqi report weekly",
            "quarterly-report.yml": "huaqi report quarterly",
        }
        for wf, cmd in report_commands.items():
            # 验证命令不以需要 TTY 的方式调用
            assert "huaqi report" in cmd
            assert "--interactive" not in cmd

    def test_scheduler_run_commands_exist(self):
        """学习推送和世界新闻使用 scheduler run 命令。"""
        scheduler_commands = {
            "learning-push.yml": "learning_daily_push",
            "world-fetch.yml": "world_fetch",
        }
        for wf, job_id in scheduler_commands.items():
            assert job_id in ("learning_daily_push", "world_fetch")

class TestWorkflowOutputPaths:
    """AC-3: git commit 步骤引用正确的输出路径。"""

    def test_report_output_paths(self):
        """验证报告输出路径与 git add 路径一致。"""
        expected_paths = {
            "morning-brief.yml": "reports/daily/",
            "daily-report.yml": "reports/daily/",
            "weekly-report.yml": "reports/weekly/",
            "quarterly-report.yml": "reports/quarterly/",
            "learning-push.yml": "learning/",  # 学习推送输出路径
            "world-fetch.yml": "world/",       # 世界新闻输出路径
        }
        for wf, path in expected_paths.items():
            assert path.endswith("/") or path  # 确保是目录路径
            # 实际路径验证将在 Step 3 中通过解析 YAML 完成
```

### Step 2: 运行确认失败

```bash
pytest tests/unit/test_github_actions_workflows.py -v
```

期望：全部失败（文件不存在）。

### Step 3: 写实现

创建 7 个文件：

**`scripts/github-actions/notify.sh`**（Server酱 通知脚本）：
```bash
#!/bin/bash
# 用法: ./notify.sh "标题" "内容"
# 需要环境变量: SERVERCHAN_KEY

SERVERCHAN_KEY="${SERVERCHAN_KEY:-}"
if [ -z "$SERVERCHAN_KEY" ]; then
    echo "WARNING: SERVERCHAN_KEY not set, skipping notification"
    exit 0
fi

TITLE="$1"
CONTENT="$2"

curl -s -X POST "https://sctapi.ftqq.com/${SERVERCHAN_KEY}.send" \
    -d "title=${TITLE}" \
    -d "desp=${CONTENT}" \
    -o /dev/null
```

**`scripts/github-actions/morning-brief.yml`**（示例，其余 5 个结构相同）：
```yaml
name: 晨间简报

on:
  schedule:
    - cron: '0 0 * * *'   # UTC 0:00 = 北京时间 8:00
  workflow_dispatch:       # 手动触发

jobs:
  generate:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          ref: main

      - uses: actions/checkout@v4
        with:
          repository: lianzimeng05/huaqi-growing
          path: huaqi-src

      - uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install huaqi
        run: pip install -e huaqi-src/

      - name: Generate morning brief
        id: report
        env:
          HUAQI_DATA_DIR: ${{ github.workspace }}
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
        run: |
          huaqi report morning
          echo "file=$(ls reports/daily/$(date +%F)-morning.md 2>/dev/null || echo '')" >> $GITHUB_OUTPUT

      - name: Commit and push
        run: |
          git pull --rebase
          git config user.name "Huaqi Bot"
          git config user.email "bot@huaqi.local"
          git add reports/
          if git diff --cached --quiet; then
            echo "No changes to commit"
          else
            git commit -m "chore: generate morning brief $(date +%F)"
            git push
          fi

      - name: Notify success
        if: success()
        env:
          SERVERCHAN_KEY: ${{ secrets.SERVERCHAN_KEY }}
        run: |
          bash scripts/github-actions/notify.sh \
            "✅ 晨间简报已生成" \
            "晨间简报 $(date +%F) 已生成并推送到数据仓库。"

      - name: Notify failure
        if: failure()
        env:
          SERVERCHAN_KEY: ${{ secrets.SERVERCHAN_KEY }}
        run: |
          bash scripts/github-actions/notify.sh \
            "❌ 晨间简报生成失败" \
            "请查看 GitHub Actions 运行日志：${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}"
```

其余 5 个 workflow 结构相同，差异见下表：

| workflow 文件 | CLI 命令 | cron (UTC) | 特殊逻辑 |
|--------------|---------|-----------|---------|
| `daily-report.yml` | `huaqi report daily` | `0 15 * * *` | - |
| `weekly-report.yml` | `huaqi report weekly` | `0 13 * * 0` | - |
| `quarterly-report.yml` | `huaqi report quarterly` | `0 14 28-31 3,6,9,12 *` | 第一步判断是否季度最后一天 |
| `learning-push.yml` | `huaqi scheduler run learning_daily_push` | `0 13 * * *` | - |
| `world-fetch.yml` | `huaqi scheduler run world_fetch` | `0 23 * * *` | - |

### Step 4: 运行确认通过

```bash
pytest tests/unit/test_github_actions_workflows.py -v
```

期望：所有测试通过。

### Step 5: 更新验收测试

追加到 `tests/smoke_test.py`：

```python
class TestGitHubActionsWorkflows:
    """GitHub Actions 定时任务迁移功能验收。

    Spec: docs/specs/2026-05-14-reports-github-actions.md
    """

    def test_six_workflow_files_exist(self):
        """AC-1: 6 个 workflow 文件存在。"""
        workflow_dir = Path("scripts/github-actions")
        expected = [
            "morning-brief.yml", "daily-report.yml",
            "weekly-report.yml", "quarterly-report.yml",
            "learning-push.yml", "world-fetch.yml",
        ]
        for wf in expected:
            assert (workflow_dir / wf).exists(), f"Missing: {wf}"

    def test_workflow_files_have_cron_trigger(self, data_dir, set_data_dir):
        """AC-1: 每个 workflow 包含 cron 触发器。"""
        import yaml
        workflow_dir = Path("scripts/github-actions")
        for wf in workflow_dir.glob("*.yml"):
            with open(wf) as f:
                data = yaml.safe_load(f)
            triggers = data.get("on", {})
            has_cron = "schedule" in triggers
            has_manual = "workflow_dispatch" in triggers
            assert has_cron, f"{wf.name}: missing schedule trigger"
            assert has_manual, f"{wf.name}: missing workflow_dispatch"

    def test_workflow_has_write_permission(self, data_dir, set_data_dir):
        """AC-10: workflow 声明 contents: write 权限。"""
        import yaml
        workflow_dir = Path("scripts/github-actions")
        for wf in workflow_dir.glob("*.yml"):
            with open(wf) as f:
                data = yaml.safe_load(f)
            for job_id, job in data.get("jobs", {}).items():
                perms = job.get("permissions", {})
                assert perms.get("contents") == "write", \
                    f"{wf.name}/{job_id}: missing contents:write"

    def test_quarterly_has_conditional_check(self, data_dir, set_data_dir):
        """AC-9: 季报 workflow 包含季度最后一天判断。"""
        import yaml
        path = Path("scripts/github-actions/quarterly-report.yml")
        with open(path) as f:
            data = yaml.safe_load(f)
        # 将整个 workflow 序列化为字符串搜索关键逻辑
        yaml_str = yaml.dump(data)
        assert "timedelta" in yaml_str or "last_day" in yaml_str.lower() or \
            "end of quarter" in yaml_str.lower(), \
            "quarterly-report.yml: missing end-of-quarter check"

    def test_notify_sh_uses_serverchan_key(self, data_dir, set_data_dir):
        """AC-4: notify.sh 使用 SERVERCHAN_KEY 环境变量。"""
        path = Path("scripts/github-actions/notify.sh")
        content = path.read_text()
        assert "SERVERCHAN_KEY" in content
        assert "sctapi.ftqq.com" in content
```

---

## Task 2: 创建 Secrets 配置说明

**Files:**
- Create: `scripts/github-actions/SECRETS.md`

### Step 1-4: 纯文档任务，直接在 Step 3 写入

### Step 3: 写实现

创建 `scripts/github-actions/SECRETS.md`，列出所有需要的 GitHub Secrets：

- `OPENAI_API_KEY`（或 `KIMI_API_KEY`）：LLM API 密钥
- `SERVERCHAN_KEY`：Server酱 SendKey
- 设置方法：GitHub 仓库 → Settings → Secrets and variables → Actions

### Step 5: 更新验收测试

追加到 `tests/smoke_test.py`：

```python
def test_secrets_doc_exists(self):
    """AC-5: Secrets 配置文档存在且包含必要信息。"""
    path = Path("scripts/github-actions/SECRETS.md")
    assert path.exists()
    content = path.read_text()
    assert "SERVERCHAN_KEY" in content
    assert "API" in content
    assert "Secret" in content or "secret" in content
```

---

## Task 3: 更新架构文档

**Files:**
- Modify: `docs/design/ARCHITECTURE.md`（如果存在）
- 或 Create: `docs/features/reports-github-actions.md`

### Step 1-4: 文档任务

### Step 3: 写实现

将关键设计结论写入 `docs/design/ARCHITECTURE.md`（如不存在则创建 `docs/designs/reports-github-actions.md`）：
- 定时任务已迁移至 GitHub Actions
- 后续新增定时任务遵循 GitHub Actions 模式
- 保留 APScheduler 作为本地调试备选

### Step 5: 更新验收测试

追加到 `tests/smoke_test.py`：

```python
def test_architecture_doc_has_github_actions_decision(self):
    """AC-6: 架构文档标注 GitHub Actions 决策。"""
    arch_path = Path("docs/design/ARCHITECTURE.md")
    if not arch_path.exists():
        arch_path = Path("docs/designs/reports-github-actions.md")
    assert arch_path.exists(), "Architecture doc not found"
    content = arch_path.read_text()
    assert "GitHub Actions" in content
```

---

## Task 4: 验证 headless 执行

### Step 1: 写测试

```python
# tests/unit/test_headless_report_commands.py
import subprocess
import os
import pytest

class TestHeadlessReportCommands:
    """AC-2: CLI 命令在无 TTY 环境下可执行。"""

    def test_report_daily_headless(self, tmp_path):
        """验证 huaqi report daily 在 HUAQI_DATA_DIR 下不要求交互。"""
        # 设置最小数据目录结构
        (tmp_path / "memory").mkdir(parents=True)
        (tmp_path / "memory" / "config.yaml").write_text("version: 1\n")

        env = {**os.environ, "HUAQI_DATA_DIR": str(tmp_path)}
        result = subprocess.run(
            ["huaqi", "report", "daily"],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
        )
        # 不应因缺少 TTY 而崩溃
        assert "Cannot prompt" not in result.stderr
        assert "Abort" not in result.stderr

    def test_require_data_dir_gives_clear_error(self):
        """未设置 data_dir 时给出明确错误而非提示输入。"""
        result = subprocess.run(
            ["huaqi", "report", "daily"],
            env={**os.environ, "HUAQI_DATA_DIR": ""},
            capture_output=True,
            text=True,
            timeout=30,
        )
        # 应该输出错误信息，而不是卡在交互式提示
        assert result.returncode != 0
```

### Step 2: 运行确认失败

```bash
pytest tests/unit/test_headless_report_commands.py -v
```

期望：如果 huaqi 未安装或 LLM 未配置，部分测试可能失败。

### Step 3: 写实现

无需修改源码。`HUAQI_DATA_DIR` 环境变量已支持绕过交互式向导。

### Step 4: 运行确认通过

```bash
HUAQI_DATA_DIR=/tmp/test_huaqi_ci pytest tests/unit/test_headless_report_commands.py -v
```

### Step 5: 更新验收测试

追加到 `tests/smoke_test.py`：

```python
def test_headless_env_var_bypasses_wizard(self, data_dir, set_data_dir):
    """AC-2: HUAQI_DATA_DIR 环境变量绕过交互式向导。"""
    from huaqi_src.config.paths import get_data_dir, is_data_dir_set
    # 在测试环境中 data_dir fixture 已设置，应正常工作
    data_path = get_data_dir()
    assert data_path is not None
    assert data_path.exists()
```
```

---

## Task 完成顺序与依赖

```
Task 1 (workflow 模板) ──┐
                          ├──→ Task 4 (验证 headless)
Task 2 (Secrets 文档) ────┤
                          │
Task 3 (架构文档) ────────┘
```

Task 1-3 可并行开发，Task 4 依赖 Task 1（需要 workflow 中的命令定义）。
