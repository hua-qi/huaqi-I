# Plan: docs 目录重组

> **Plan 是基于 Spec 的具体实施方案。Spec 定义 WHAT，Plan 定义 HOW。**

**Goal:** 将 `docs/` 重组为 `project/`（全局）+ `iterations/`（迭代），合并顶层设计文档从 6→3
**Architecture:** 7 个 Task，顺序执行（mv → merge → update refs → clean up）
**Spec:** `docs/specs/docs-reorganization.md`

---

## 背景阅读

- `docs/specs/docs-reorganization.md` — 功能规格
- `docs/guides/dev/DOC_GUIDELINES.md` — 文档编写规范（需更新）
- `CLAUDE.md` 106-149 — 开发工作流章节（需更新）
- `.claude/skills/develop/SKILL.md` — develop skill（需更新）
- `README.md` — 文档链接（需更新）
- `CHANGELOG.md` — 历史引用（需更新）
- `tests/smoke_test.py` 1637-1893 — Spec 引用（需更新）

运行已有测试确认基线：
```bash
pytest tests/ -x --tb=short
```

---

## Task 1: 创建新目录结构

**Files:**
- Create: `docs/project/design/adr/`
- Create: `docs/project/guides/user/`
- Create: `docs/project/guides/dev/`
- Create: `docs/iterations/_templates/`

**Step 1: 写失败测试（纯目录操作，跳过 TDD）**

**Step 2: 运行确认失败（跳过）**

**Step 3: 创建目录**

```bash
mkdir -p docs/project/design/adr
mkdir -p docs/project/guides/user
mkdir -p docs/project/guides/dev
mkdir -p docs/iterations/_templates
```

**Step 4: 确认目录存在**

```bash
ls -d docs/project/design/adr docs/project/guides/user docs/project/guides/dev docs/iterations/_templates
```

---

## Task 2: 迁移项目全局文档

**Files:**
- Move: `docs/design/adr/*` → `docs/project/design/adr/*`
- Move: `docs/design/{ARCHITECTURE,PRD,TECH_SPEC}.md` → `docs/project/design/`
- Move: `docs/guides/**` → `docs/project/guides/**`

**Step 1-2: 跳过（目录操作）**

**Step 3: 执行 git mv**

```bash
# ADR 决策记录
git mv docs/design/adr/ADR-000-project-origins.md docs/project/design/adr/
git mv docs/design/adr/ADR-001-initial-design.md docs/project/design/adr/
git mv docs/design/adr/ADR-002-code-organization-refactor.md docs/project/design/adr/
git mv docs/design/adr/ADR-003-memory-retrieval-strategy.md docs/project/design/adr/
git mv docs/design/adr/ADR-004-langgraph-default-mode.md docs/project/design/adr/
git mv docs/design/adr/ADR-005-report-data-provider-registry.md docs/project/design/adr/
git mv docs/design/adr/ADR-006-three-layer-architecture.md docs/project/design/adr/
git mv docs/design/adr/ADR-007-scheduler-unified-chat-tasks.md docs/project/design/adr/

# 核心顶层文档
git mv docs/design/ARCHITECTURE.md docs/project/design/
git mv docs/design/PRD.md docs/project/design/
git mv docs/design/TECH_SPEC.md docs/project/design/

# 指南
git mv docs/guides/user/cli-guide.md docs/project/guides/user/
git mv docs/guides/user/IMPORT_GUIDE.md docs/project/guides/user/
git mv docs/guides/dev/code-standards.md docs/project/guides/dev/
git mv docs/guides/dev/DOC_GUIDELINES.md docs/project/guides/dev/
git mv docs/guides/dev/usage.md docs/project/guides/dev/
git mv docs/guides/dev/cli-ui-improvements.md docs/project/guides/dev/
```

**Step 4: 确认**

```bash
ls docs/project/design/ docs/project/design/adr/ docs/project/guides/user/ docs/project/guides/dev/
```

---

## Task 3: 处理遗留在 design/ 的文档（合并 + 移入迭代）

处理 SPEC.md、MULTI_USER_DESIGN.md、memory-retrieval-strategy.md

**Step 1: 写失败测试（跳过，纯内容操作）**

**Step 2: 跳过**

**Step 3: 执行**

```bash
# SPEC.md → 删除（内容手动合并到 PRD.md + ARCHITECTURE.md）
# 稍后在 Task 6 中完成合并

# MULTI_USER_DESIGN.md → 移入 iterations/ 对应目录
git mv docs/design/MULTI_USER_DESIGN.md docs/iterations/multi-user-support/design.md

# memory-retrieval-strategy.md → 移入 iterations/ 对应目录
git mv docs/design/memory-retrieval-strategy.md docs/iterations/2026-03-29-agentic-memory-retrieval/design.md
```

**Step 3a: 合并 SPEC.md 到 PRD.md**

手动编辑 `docs/project/design/PRD.md`：
- 在「产品定位」节插入 SPEC.md 的核心理念（Human 3.0、同伴关系）
- 在「功能需求」节后追加 SPEC.md 的设计原则（Humans set direction 等 4 条）
- 追加 SPEC.md 的系统目标（记忆/执行/成长/陪伴）

**Step 3b: 合并 SPEC.md 到 ARCHITECTURE.md**

手动编辑 `docs/project/design/ARCHITECTURE.md`：
- 在开头 reference 原 SPEC.md 的 7 层架构概念
- 确保 ARCHITECTURE.md 的「源码目录速查」覆盖 SPEC.md 中的所有模块描述
- 保留 ARCHITECTURE.md 已有内容（它是更权威、更新的版本）

**Step 3c: 删除 SPEC.md**

```bash
git rm docs/design/SPEC.md
```

**Step 4: 手动验证合并质量**

- 确认 PRD.md 包含完整的产品愿景和设计原则
- 确认 ARCHITECTURE.md 包含完整的系统架构说明
- 确认原 SPEC.md 的关键信息没有遗漏

---

## Task 4: 迁移迭代文档（specs/plans/features/designs → iterations/）

这是最复杂的 Task。先按日期分组，再逐个移动。

### 4.1 完整迁移映射表

以下为**按迭代目录名排序**的完整映射：

| 原文件 | 新位置 | 备注 |
|--------|--------|------|
| —— 迭代：2026-01-04-personal-growth-system —— | | |
| `designs/2026-01-04-personal-growth-system-design.md` | `iterations/2026-01-04-personal-growth-system/design.md` | |
| `designs/2026-01-04-acceptance-checklist.md` | `iterations/2026-01-04-personal-growth-system/acceptance.md` | 推断归属 |
| `designs/2026-01-04-design-gaps.md` | `iterations/2026-01-04-personal-growth-system/design-gaps.md` | 补充文档 |
| `designs/2026-01-04-implementation-details.md` | `iterations/2026-01-04-personal-growth-system/implementation-details.md` | 补充文档 |
| `designs/2026-01-04-test-strategy.md` | `iterations/2026-01-04-personal-growth-system/test-strategy.md` | 补充文档 |
| —— 迭代：2026-01-04-lesson-complete-mark —— | | |
| `plans/2026-01-04-lesson-complete-mark.md` | `iterations/2026-01-04-lesson-complete-mark/plan.md` | |
| `designs/2026-01-04-lesson-complete-mark.md` | `iterations/2026-01-04-lesson-complete-mark/design.md` | |
| —— 迭代：2026-01-04-remaining-features —— | | |
| `plans/2026-01-04-remaining-features.md` | `iterations/2026-01-04-remaining-features/plan.md` | |
| —— 迭代：2026-02-04-dependency-architecture-migration —— | | |
| `plans/2026-02-04-dependency-architecture-migration.md` | `iterations/2026-02-04-dependency-architecture-migration/plan.md` | |
| `designs/2026-02-04-dependency-architecture-design.md` | `iterations/2026-02-04-dependency-architecture-migration/design.md` | |
| —— 迭代：2026-03-29-save-brainstorm —— | | |
| `designs/2026-03-29-save-brainstorm-design.md` | `iterations/2026-03-29-save-brainstorm/design.md` | 独立 design |
| —— 迭代：2026-03-29-agentic-memory-retrieval —— | | |
| `plans/2026-03-29-agentic-memory-retrieval.md` | `iterations/2026-03-29-agentic-memory-retrieval/plan.md` | |
| `features/agentic-memory-retrieval.md` | `iterations/2026-03-29-agentic-memory-retrieval/feature.md` | |
| —— 迭代：2026-03-29-huaqi-growing-core-engine —— | | |
| `plans/2026-03-29-huaqi-growing-core-engine.md` | `iterations/2026-03-29-huaqi-growing-core-engine/plan.md` | |
| `features/core-engine.md` | `iterations/2026-03-29-huaqi-growing-core-engine/feature.md` | |
| —— 迭代：2026-03-30-growth-intelligence-phase1 —— | | |
| `plans/2026-03-30-growth-intelligence-phase1.md` | `iterations/2026-03-30-growth-intelligence-phase1/plan.md` | |
| `designs/2026-03-30-huaqi-growth-intelligence.md` | `iterations/2026-03-30-growth-intelligence-phase1/design.md` | |
| —— 迭代：2026-03-30-huaqi-memory-recall —— | | |
| `plans/2026-03-30-huaqi-memory-recall.md` | `iterations/2026-03-30-huaqi-memory-recall/plan.md` | |
| —— 迭代：2026-03-30-phase2-deep-understanding —— | | |
| `plans/2026-03-30-phase2-deep-understanding.md` | `iterations/2026-03-30-phase2-deep-understanding/plan.md` | |
| —— 迭代：2026-03-30-phase3-listeners —— | | |
| `plans/2026-03-30-phase3-listeners.md` | `iterations/2026-03-30-phase3-listeners/plan.md` | |
| `features/listeners.md` | `iterations/2026-03-30-phase3-listeners/feature.md` | |
| —— 迭代：2026-03-31-learning-assistant —— | | |
| `plans/2026-03-31-learning-assistant.md` | `iterations/2026-03-31-learning-assistant/plan.md` | |
| `features/learning-assistant.md` | `iterations/2026-03-31-learning-assistant/feature.md` | |
| `designs/2026-03-31-learning-assistant.md` | `iterations/2026-03-31-learning-assistant/design.md` | |
| —— 迭代：2026-03-31-report-data-provider-registry —— | | |
| `plans/2026-03-31-report-data-provider-registry.md` | `iterations/2026-03-31-report-data-provider-registry/plan.md` | |
| `features/report-data-provider-registry.md` | `iterations/2026-03-31-report-data-provider-registry/feature.md` | |
| `designs/2026-03-31-report-data-provider-registry.md` | `iterations/2026-03-31-report-data-provider-registry/design.md` | |
| —— 迭代：2026-04-03-cli-report-viewer —— | | |
| `plans/2026-04-03-cli-report-viewer.md` | `iterations/2026-04-03-cli-report-viewer/plan.md` | |
| `features/cli-report-viewer.md` | `iterations/2026-04-03-cli-report-viewer/feature.md` | |
| `designs/2026-04-03-cli-report-viewer.md` | `iterations/2026-04-03-cli-report-viewer/design.md` | |
| —— 迭代：2026-05-04-codeflicker-transcript-collector —— | | |
| `designs/2026-05-04-codeflicker-transcript-collector.md` | `iterations/2026-05-04-codeflicker-transcript-collector/design.md` | 独立 design |
| —— 迭代：2026-05-04-codeflicker-worklog-storage —— | | |
| `plans/2026-05-04-codeflicker-worklog-storage.md` | `iterations/2026-05-04-codeflicker-worklog-storage/plan.md` | |
| `designs/2026-05-04-codeflicker-worklog-storage.md` | `iterations/2026-05-04-codeflicker-worklog-storage/design.md` | |
| —— 迭代：2026-05-04-world-pipeline-and-job-recovery —— | | |
| `plans/2026-05-04-world-pipeline-and-job-recovery.md` | `iterations/2026-05-04-world-pipeline-and-job-recovery/plan.md` | |
| `features/world-pipeline-and-job-recovery.md` | `iterations/2026-05-04-world-pipeline-and-job-recovery/feature.md` | |
| `designs/2026-05-04-world-pipeline-and-job-recovery.md` | `iterations/2026-05-04-world-pipeline-and-job-recovery/design.md` | |
| —— 迭代：2026-05-14-reports-github-actions —— | | |
| `specs/2026-05-14-reports-github-actions.md` | `iterations/2026-05-14-reports-github-actions/spec.md` | |
| `plans/2026-05-14-reports-github-actions.md` | `iterations/2026-05-14-reports-github-actions/plan.md` | |
| `features/reports-github-actions.md` | `iterations/2026-05-14-reports-github-actions/feature.md` | |
| —— 迭代：2026-04-07-google-search-tool —— | | |
| `plans/2026-04-07-google-search-tool.md` | `iterations/2026-04-07-google-search-tool/plan.md` | |
| `designs/2026-04-07-google-search-tool.md` | `iterations/2026-04-07-google-search-tool/design.md` | |
| —— 迭代：2026-04-09-scheduler-deep-audit —— | | |
| `plans/2026-04-09-scheduler-deep-audit.md` | `iterations/2026-04-09-scheduler-deep-audit/plan.md` | |
| —— 迭代：2026-04-09-scheduler-refactor-bugs —— | | |
| `plans/2026-04-09-scheduler-refactor-bugs.md` | `iterations/2026-04-09-scheduler-refactor-bugs/plan.md` | |
| —— 迭代：2026-04-09-scheduler-refactor-gaps —— | | |
| `plans/2026-04-09-scheduler-refactor-gaps.md` | `iterations/2026-04-09-scheduler-refactor-gaps/plan.md` | |
| —— 迭代：2026-04-10-telos-refactor —— | | |
| `plans/2026-04-10-telos-refactor.md` | `iterations/2026-04-10-telos-refactor/plan.md` | |
| `designs/2026-04-10-telos-design-and-implementation.md` | `iterations/2026-04-10-telos-refactor/design.md` | |
| `designs/2026-04-10-telos-acceptance-checklist.md` | `iterations/2026-04-10-telos-refactor/acceptance.md` | |
| —— 迭代：2026-04-11-telos-next-phase —— | | |
| `plans/2026-04-11-telos-next-phase.md` | `iterations/2026-04-11-telos-next-phase/plan.md` | |
| `designs/2026-04-11-telos-next-phase-design.md` | `iterations/2026-04-11-telos-next-phase/design.md` | |
| `designs/2026-04-11-telos-next-phase-acceptance-checklist.md` | `iterations/2026-04-11-telos-next-phase/acceptance.md` | |
| —— 迭代：2026-04-11-work-habit-to-codeflicker —— | | |
| `plans/2026-04-11-work-habit-to-codeflicker.md` | `iterations/2026-04-11-work-habit-to-codeflicker/plan.md` | |
| `designs/2026-04-11-work-habit-to-codeflicker.md` | `iterations/2026-04-11-work-habit-to-codeflicker/design.md` | |
| `iterations/2026-04-11-work-habit-to-codeflicker/acceptance.md` | `iterations/2026-04-11-work-habit-to-codeflicker/acceptance.md` | 已在迭代目录 |
| `iterations/2026-04-11-work-habit-to-codeflicker/buglist.md` | `iterations/2026-04-11-work-habit-to-codeflicker/buglist.md` | 已在迭代目录 |
| —— 迭代：2026-04-17-data-dir-spec —— | | |
| `plans/2026-04-17-data-dir-spec-implementation.md` | `iterations/2026-04-17-data-dir-spec-implementation/plan.md` | |
| `designs/2026-04-17-data-dir-spec.md` | `iterations/2026-04-17-data-dir-spec-implementation/design.md` | |
| —— 迭代：prompts-overhaul（无日期前缀）—— | | |
| `specs/prompts-overhaul.md` | `iterations/prompts-overhaul/spec.md` | |
| `plans/prompts-overhaul.md` | `iterations/prompts-overhaul/plan.md` | |
| —— 迭代：telos-distillation-scheduling（无日期前缀）—— | | |
| `specs/telos-distillation-scheduling.md` | `iterations/telos-distillation-scheduling/spec.md` | |
| `plans/telos-distillation-scheduling.md` | `iterations/telos-distillation-scheduling/plan.md` | |
| —— 迭代：world-news-enhance（无日期前缀）—— | | |
| `specs/world-news-enhance.md` | `iterations/world-news-enhance/spec.md` | |
| `plans/world-news-enhance.md` | `iterations/world-news-enhance/plan.md` | |
| `features/world-news-enhance.md` | `iterations/world-news-enhance/feature.md` | |
| —— 无日期的 features/ 散件 → 各自独立迭代目录 —— | | |
| `features/conversation-context.md` | `iterations/conversation-context/feature.md` | 无对应 plan/spec，独立迭代 |
| `features/langgraph-agent.md` | `iterations/langgraph-agent/feature.md` | 无对应 plan/spec，独立迭代 |
| `features/pattern-learning.md` | `iterations/pattern-learning/feature.md` | 无对应 plan/spec，独立迭代 |
| `features/scheduler.md` | `iterations/scheduler/feature.md` | 无对应 plan/spec，独立迭代 |
| `features/proactive-care/design.md` | `iterations/proactive-care/design.md` | |
| `features/proactive-care/impl.md` | `iterations/proactive-care/feature.md` | 重命名 impl→feature |
| `features/user-profile/extraction.md` | `iterations/user-profile/extraction.md` | 子文档保持原名 |
| `features/user-profile/narrative.md` | `iterations/user-profile/narrative.md` | 子文档保持原名 |
| —— 跨迭代文档 —— | | |
| `plans/ROADMAP.md` | `iterations/ROADMAP.md` | |
| `plans/ops/implementation-plan.md` | `iterations/ops/implementation-plan.md` | |
| `plans/ops/migration-v2.md` | `iterations/ops/migration-v2.md` | |
| `plans/ops/test-plan.md` | `iterations/ops/test-plan.md` | |
| `iterations/BUGLIST.md` | `iterations/BUGLIST.md` | 不变 |

### 4.2 执行命令（按迭代目录分批 git mv）

```bash
# === 创建所有迭代目录 ===
declare -a ITER_DIRS=(
    "2026-01-04-personal-growth-system"
    "2026-01-04-lesson-complete-mark"
    "2026-01-04-remaining-features"
    "2026-02-04-dependency-architecture-migration"
    "2026-03-29-save-brainstorm"
    "2026-03-29-agentic-memory-retrieval"
    "2026-03-29-huaqi-growing-core-engine"
    "2026-03-30-growth-intelligence-phase1"
    "2026-03-30-huaqi-memory-recall"
    "2026-03-30-phase2-deep-understanding"
    "2026-03-30-phase3-listeners"
    "2026-03-31-learning-assistant"
    "2026-03-31-report-data-provider-registry"
    "2026-04-03-cli-report-viewer"
    "2026-05-04-codeflicker-transcript-collector"
    "2026-05-04-codeflicker-worklog-storage"
    "2026-05-04-world-pipeline-and-job-recovery"
    "2026-05-14-reports-github-actions"
    "2026-04-07-google-search-tool"
    "2026-04-09-scheduler-deep-audit"
    "2026-04-09-scheduler-refactor-bugs"
    "2026-04-09-scheduler-refactor-gaps"
    "2026-04-10-telos-refactor"
    "2026-04-11-telos-next-phase"
    "2026-04-11-work-habit-to-codeflicker"
    "2026-04-17-data-dir-spec-implementation"
    "prompts-overhaul"
    "telos-distillation-scheduling"
    "world-news-enhance"
    "conversation-context"
    "langgraph-agent"
    "pattern-learning"
    "scheduler"
    "proactive-care"
    "user-profile"
    "multi-user-support"
    "ops"
)
for d in "${ITER_DIRS[@]}"; do
    mkdir -p "docs/iterations/$d"
done

# === 执行 git mv（按映射表逐条） ===
# designs/ → iterations/
git mv docs/designs/2026-01-04-personal-growth-system-design.md docs/iterations/2026-01-04-personal-growth-system/design.md
git mv docs/designs/2026-01-04-acceptance-checklist.md docs/iterations/2026-01-04-personal-growth-system/acceptance.md
git mv docs/designs/2026-01-04-design-gaps.md docs/iterations/2026-01-04-personal-growth-system/design-gaps.md
git mv docs/designs/2026-01-04-implementation-details.md docs/iterations/2026-01-04-personal-growth-system/implementation-details.md
git mv docs/designs/2026-01-04-test-strategy.md docs/iterations/2026-01-04-personal-growth-system/test-strategy.md
git mv docs/designs/2026-01-04-lesson-complete-mark.md docs/iterations/2026-01-04-lesson-complete-mark/design.md
git mv docs/designs/2026-02-04-dependency-architecture-design.md docs/iterations/2026-02-04-dependency-architecture-migration/design.md
git mv docs/designs/2026-03-29-save-brainstorm-design.md docs/iterations/2026-03-29-save-brainstorm/design.md
git mv docs/designs/2026-03-30-huaqi-growth-intelligence.md docs/iterations/2026-03-30-growth-intelligence-phase1/design.md
git mv docs/designs/2026-03-31-learning-assistant.md docs/iterations/2026-03-31-learning-assistant/design.md
git mv docs/designs/2026-03-31-report-data-provider-registry.md docs/iterations/2026-03-31-report-data-provider-registry/design.md
git mv docs/designs/2026-04-03-cli-report-viewer.md docs/iterations/2026-04-03-cli-report-viewer/design.md
git mv docs/designs/2026-05-04-codeflicker-transcript-collector.md docs/iterations/2026-05-04-codeflicker-transcript-collector/design.md
git mv docs/designs/2026-05-04-codeflicker-worklog-storage.md docs/iterations/2026-05-04-codeflicker-worklog-storage/design.md
git mv docs/designs/2026-05-04-world-pipeline-and-job-recovery.md docs/iterations/2026-05-04-world-pipeline-and-job-recovery/design.md
git mv docs/designs/2026-04-07-google-search-tool.md docs/iterations/2026-04-07-google-search-tool/design.md
git mv docs/designs/2026-04-10-telos-design-and-implementation.md docs/iterations/2026-04-10-telos-refactor/design.md
git mv docs/designs/2026-04-10-telos-acceptance-checklist.md docs/iterations/2026-04-10-telos-refactor/acceptance.md
git mv docs/designs/2026-04-11-telos-next-phase-design.md docs/iterations/2026-04-11-telos-next-phase/design.md
git mv docs/designs/2026-04-11-telos-next-phase-acceptance-checklist.md docs/iterations/2026-04-11-telos-next-phase/acceptance.md
git mv docs/designs/2026-04-11-work-habit-to-codeflicker.md docs/iterations/2026-04-11-work-habit-to-codeflicker/design.md
git mv docs/designs/2026-04-17-data-dir-spec.md docs/iterations/2026-04-17-data-dir-spec-implementation/design.md

# plans/ → iterations/
git mv docs/plans/2026-01-04-lesson-complete-mark.md docs/iterations/2026-01-04-lesson-complete-mark/plan.md
git mv docs/plans/2026-01-04-remaining-features.md docs/iterations/2026-01-04-remaining-features/plan.md
git mv docs/plans/2026-02-04-dependency-architecture-migration.md docs/iterations/2026-02-04-dependency-architecture-migration/plan.md
git mv docs/plans/2026-03-29-agentic-memory-retrieval.md docs/iterations/2026-03-29-agentic-memory-retrieval/plan.md
git mv docs/plans/2026-03-29-huaqi-growing-core-engine.md docs/iterations/2026-03-29-huaqi-growing-core-engine/plan.md
git mv docs/plans/2026-03-30-growth-intelligence-phase1.md docs/iterations/2026-03-30-growth-intelligence-phase1/plan.md
git mv docs/plans/2026-03-30-huaqi-memory-recall.md docs/iterations/2026-03-30-huaqi-memory-recall/plan.md
git mv docs/plans/2026-03-30-phase2-deep-understanding.md docs/iterations/2026-03-30-phase2-deep-understanding/plan.md
git mv docs/plans/2026-03-30-phase3-listeners.md docs/iterations/2026-03-30-phase3-listeners/plan.md
git mv docs/plans/2026-03-31-learning-assistant.md docs/iterations/2026-03-31-learning-assistant/plan.md
git mv docs/plans/2026-03-31-report-data-provider-registry.md docs/iterations/2026-03-31-report-data-provider-registry/plan.md
git mv docs/plans/2026-04-03-cli-report-viewer.md docs/iterations/2026-04-03-cli-report-viewer/plan.md
git mv docs/plans/2026-05-04-codeflicker-worklog-storage.md docs/iterations/2026-05-04-codeflicker-worklog-storage/plan.md
git mv docs/plans/2026-05-04-world-pipeline-and-job-recovery.md docs/iterations/2026-05-04-world-pipeline-and-job-recovery/plan.md
git mv docs/plans/2026-05-14-reports-github-actions.md docs/iterations/2026-05-14-reports-github-actions/plan.md
git mv docs/plans/2026-04-07-google-search-tool.md docs/iterations/2026-04-07-google-search-tool/plan.md
git mv docs/plans/2026-04-09-scheduler-deep-audit.md docs/iterations/2026-04-09-scheduler-deep-audit/plan.md
git mv docs/plans/2026-04-09-scheduler-refactor-bugs.md docs/iterations/2026-04-09-scheduler-refactor-bugs/plan.md
git mv docs/plans/2026-04-09-scheduler-refactor-gaps.md docs/iterations/2026-04-09-scheduler-refactor-gaps/plan.md
git mv docs/plans/2026-04-10-telos-refactor.md docs/iterations/2026-04-10-telos-refactor/plan.md
git mv docs/plans/2026-04-11-telos-next-phase.md docs/iterations/2026-04-11-telos-next-phase/plan.md
git mv docs/plans/2026-04-11-work-habit-to-codeflicker.md docs/iterations/2026-04-11-work-habit-to-codeflicker/plan.md
git mv docs/plans/2026-04-17-data-dir-spec-implementation.md docs/iterations/2026-04-17-data-dir-spec-implementation/plan.md
git mv docs/plans/prompts-overhaul.md docs/iterations/prompts-overhaul/plan.md
git mv docs/plans/telos-distillation-scheduling.md docs/iterations/telos-distillation-scheduling/plan.md
git mv docs/plans/world-news-enhance.md docs/iterations/world-news-enhance/plan.md
git mv docs/plans/ROADMAP.md docs/iterations/ROADMAP.md
git mv docs/plans/ops/implementation-plan.md docs/iterations/ops/implementation-plan.md
git mv docs/plans/ops/migration-v2.md docs/iterations/ops/migration-v2.md
git mv docs/plans/ops/test-plan.md docs/iterations/ops/test-plan.md

# specs/ → iterations/
git mv docs/specs/2026-05-14-reports-github-actions.md docs/iterations/2026-05-14-reports-github-actions/spec.md
git mv docs/specs/prompts-overhaul.md docs/iterations/prompts-overhaul/spec.md
git mv docs/specs/telos-distillation-scheduling.md docs/iterations/telos-distillation-scheduling/spec.md
git mv docs/specs/world-news-enhance.md docs/iterations/world-news-enhance/spec.md

# features/ → iterations/
git mv docs/features/agentic-memory-retrieval.md docs/iterations/2026-03-29-agentic-memory-retrieval/feature.md
git mv docs/features/core-engine.md docs/iterations/2026-03-29-huaqi-growing-core-engine/feature.md
git mv docs/features/listeners.md docs/iterations/2026-03-30-phase3-listeners/feature.md
git mv docs/features/learning-assistant.md docs/iterations/2026-03-31-learning-assistant/feature.md
git mv docs/features/report-data-provider-registry.md docs/iterations/2026-03-31-report-data-provider-registry/feature.md
git mv docs/features/cli-report-viewer.md docs/iterations/2026-04-03-cli-report-viewer/feature.md
git mv docs/features/world-pipeline-and-job-recovery.md docs/iterations/2026-05-04-world-pipeline-and-job-recovery/feature.md
git mv docs/features/reports-github-actions.md docs/iterations/2026-05-14-reports-github-actions/feature.md
git mv docs/features/world-news-enhance.md docs/iterations/world-news-enhance/feature.md
git mv docs/features/conversation-context.md docs/iterations/conversation-context/feature.md
git mv docs/features/langgraph-agent.md docs/iterations/langgraph-agent/feature.md
git mv docs/features/pattern-learning.md docs/iterations/pattern-learning/feature.md
git mv docs/features/scheduler.md docs/iterations/scheduler/feature.md
git mv docs/features/proactive-care/design.md docs/iterations/proactive-care/design.md
git mv docs/features/proactive-care/impl.md docs/iterations/proactive-care/feature.md
git mv docs/features/user-profile/extraction.md docs/iterations/user-profile/extraction.md
git mv docs/features/user-profile/narrative.md docs/iterations/user-profile/narrative.md

# specs/docs-reorganization.md → 本次迭代
git mv docs/specs/docs-reorganization.md docs/iterations/2026-05-18-docs-reorg/spec.md
```

**Step 4: 验证**

```bash
# 确认旧的 specs/plans/features/designs 目录已空
find docs/specs -type f ! -name '_TEMPLATE.md' | wc -l  # 应为 0
find docs/plans -type f ! -name '_TEMPLATE.md' | wc -l   # 应为 0
find docs/features -type f | wc -l                        # 应为 0
find docs/designs -type f | wc -l                         # 应为 0
```

---

## Task 5: 移动模板文件

```bash
git mv docs/specs/_TEMPLATE.md docs/iterations/_templates/spec.md
git mv docs/plans/_TEMPLATE.md docs/iterations/_templates/plan.md
```

---

## Task 6: 更新所有引用

### Step 6.1: 更新 CLAUDE.md 开发工作流章节

按照 Spec 4.1~4.5 的对照表，替换 CLAUDE.md 106-149 行的开发工作流章节。

### Step 6.2: 更新 .claude/skills/develop/SKILL.md

将所有路径引用从旧格式更新为新格式：
- `docs/specs/_TEMPLATE.md` → `docs/iterations/_templates/spec.md`
- `docs/plans/_TEMPLATE.md` → `docs/iterations/_templates/plan.md`
- `docs/specs/<feature-name>.md` → `docs/iterations/<YYYY-MM-DD>-<feature>/spec.md`
- `docs/plans/<feature-name>.md` → `docs/iterations/<YYYY-MM-DD>-<feature>/plan.md`
- `docs/features/<feature-name>.md` → `docs/iterations/<YYYY-MM-DD>-<feature>/feature.md`

### Step 6.3: 更新 README.md

更新 docs/ 文档索引中的链接：
- `docs/design/ARCHITECTURE.md` → `docs/project/design/ARCHITECTURE.md`
- `docs/design/SPEC.md` → `docs/project/design/PRD.md`（内容已合并）
- `docs/design/TECH_SPEC.md` → `docs/project/design/TECH_SPEC.md`
- `docs/design/PRD.md` → `docs/project/design/PRD.md`
- `docs/guides/user/cli-guide.md` → `docs/project/guides/user/cli-guide.md`
- `docs/guides/dev/code-standards.md` → `docs/project/guides/dev/code-standards.md`
- `docs/guides/dev/DOC_GUIDELINES.md` → `docs/project/guides/dev/DOC_GUIDELINES.md`
- `docs/plans/ROADMAP.md` → `docs/iterations/ROADMAP.md`
- `docs/plans/ops/test-plan.md` → `docs/iterations/ops/test-plan.md`

### Step 6.4: 更新 CHANGELOG.md

将所有 `docs/features/`、`docs/design/`、`docs/guides/` 路径更新为新路径。

### Step 6.5: 更新 tests/smoke_test.py

将所有 `Spec: docs/specs/<name>.md` 更新为 `Spec: docs/iterations/<date>-<name>/spec.md`：
- 1650: `docs/specs/2026-05-14-reports-github-actions.md` → `docs/iterations/2026-05-14-reports-github-actions/spec.md`
- 1731: `docs/specs/world-news-enhance.md` → `docs/iterations/world-news-enhance/spec.md`
- 1854: `docs/specs/telos-distillation-scheduling.md` → `docs/iterations/telos-distillation-scheduling/spec.md`
- 1893: `docs/specs/prompts-overhaul.md` → `docs/iterations/prompts-overhaul/spec.md`
- 1637: `docs/specs/<feature-name>.md` → `docs/iterations/<YYYY-MM-DD>-<feature>/spec.md`（模板注释）

### Step 6.6: 更新 docs/project/guides/dev/DOC_GUIDELINES.md

重写「文档目录结构」章节，反映新结构。

### Step 6.7: 更新 docs/project/design/ARCHITECTURE.md 和 PRD.md/internal links

检查所有内部链接是否指向新路径。

---

## Task 7: 清理空目录

```bash
# 删除已清空的旧目录
rmdir docs/designs
rmdir docs/specs
rmdir docs/plans/ops
rmdir docs/plans
rmdir docs/features/proactive-care
rmdir docs/features/user-profile
rmdir docs/features
rmdir docs/design/adr
rmdir docs/design
rmdir docs/guides/user
rmdir docs/guides/dev
rmdir docs/guides
```

---

## Task 8: 验证

运行所有验证命令：

```bash
# 确认新结构完整
ls docs/project/design/
ls docs/project/design/adr/
ls docs/project/guides/
ls docs/iterations/_templates/
ls docs/iterations/BUGLIST.md
ls docs/iterations/ROADMAP.md
ls docs/iterations/ | wc -l  # 应有 35+ 个迭代目录

# 确认旧目录不存在
test -d docs/design && echo "FAIL" || echo "PASS"
test -d docs/designs && echo "FAIL" || echo "PASS"
test -d docs/specs && echo "FAIL" || echo "PASS"
test -d docs/plans && echo "FAIL" || echo "PASS"
test -d docs/features && echo "FAIL" || echo "PASS"
test -d docs/guides && echo "FAIL" || echo "PASS"

# 烟雾测试
pytest tests/smoke_test.py -v

# Lint
ruff check .
```
