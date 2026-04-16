# 文档编写规范

本规范用于指导 agent 和开发者在编写、更新文档时保持一致性。

---

## 一、文档目录结构

```
huaqi-growing/
├── README.md                        # 项目首页，面向所有人，保持简洁
├── QUICK_START.md                   # 5分钟快速上手
├── CHANGELOG.md                     # 版本变更记录
│
├── docs/
│   ├── DOC_GUIDELINES.md            # 本文件，项目文档组织与编写规范
│   ├── design/                      # 顶层产品与技术设计文档（宏观系统说明）
│   │   ├── adr/                     # 架构决策记录 (ADR)
│   │   │   └── ADR-*.md
│   │   ├── ARCHITECTURE.md          # 系统架构（权威版本）
│   │   ├── PRD.md                   # 产品需求文档
│   │   ├── SPEC.md                  # 宏观系统说明与产品愿景（功能层面）
│   │   ├── TECH_SPEC.md             # 具体的技术选型与技术方案（技术层面）
│   │   └── MULTI_USER_DESIGN.md     # 多用户设计规范
│   ├── designs/                     # 历史特性设计草稿（带日期前缀，保留用于对比总结）
│   │   └── 2026-*.md
│   ├── features/                    # 各个功能模块的设计定稿
│   │   ├── user-profile/
│   │   │   ├── extraction.md        # 用户画像提取
│   │   │   └── narrative.md         # 用户画像叙述
│   │   ├── proactive-care/
│   │   │   ├── design.md            # 主动关怀设计
│   │   │   └── impl.md              # 主动关怀实现
│   │   ├── pattern-learning.md      # 模式学习
│   │   ├── langgraph-agent.md       # LangGraph Agent 对话系统
│   │   └── listeners.md             # 监听采集（微信 + CLI 对话）
│   ├── guides/                      # 指南类文档
│   │   ├── user/                    # 面向使用者的指南
│   │   │   ├── cli-guide.md         # CLI 命令完整参考（字典式命令清单）
│   │   │   └── IMPORT_GUIDE.md      # 记忆数据导入指南
│   │   └── dev/                     # 面向开发者的指南
│   │       ├── DOC_GUIDELINES.md    # 本文件，项目文档组织与编写规范
│   │       ├── usage.md             # 系统概览与开发集成使用指南
│   │       ├── code-standards.md    # 代码及目录规范
│   │       └── cli-ui-improvements.md # CLI/UI 改进方案
│   ├── plans/                       # 项目开发、测试与实施计划
│   │   ├── ROADMAP.md               # 项目演进路线图
│   │   ├── 2026-*.md                # 历史各阶段计划
│   │   └── ops/                     # 运维与工程落地文档
│   │       ├── implementation-plan.md   # 实施计划
│   │       ├── test-plan.md             # 测试计划
│   │       └── migration-v2.md          # 数据迁移方案
│   └── iterations/                  # 迭代验收与 Bug 追踪
│       ├── BUGLIST.md               # 全局 Bug 清单（仅关键链路 bug，跨迭代持续更新）
│       └── 2026-10-04-telos-refactor/   # 特性迭代文件夹（YYYY-MM-DD-{特性名}）
│           ├── acceptance.md        # 本次迭代验收文档
│           └── buglist.md           # 本次迭代 Bug 清单
```

---

## 二、何时需要更新文档

| 改动类型 | 必须更新 | 建议更新 |
|---------|---------|---------|
| 修复 bug | `CHANGELOG.md` | 相关功能文档（如果 bug 涉及文档描述有误） |
| 新增小功能 | `CHANGELOG.md` | `docs/guides/` 中对应的使用说明 |
| 新增大功能（影响架构） | `CHANGELOG.md` + `docs/features/` 下新建文档 | `docs/design/ARCHITECTURE.md` |
| 涉及架构决策 | `docs/design/adr/ADR-xxx.md` | `docs/design/ARCHITECTURE.md` |
| 修改 CLI 命令 | `CHANGELOG.md` + `docs/guides/user/cli-guide.md` | `README.md`（如果是核心命令） |
| 数据迁移 | `docs/ops/migration-*.md` | `CHANGELOG.md` |

---

## 三、各类文档的写法规范

### 3.1 CHANGELOG.md

遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/) 格式：

```markdown
## [版本号] - YYYY-MM-DD

### Added
- 新增了 XXX 功能

### Changed
- 修改了 XXX 行为

### Fixed
- 修复了 XXX bug

### Removed
- 移除了 XXX
```

**规则：**
- 每次 bug fix 或 feature 合并后必须在 `[Unreleased]` 下追加一条
- 发布版本时将 `[Unreleased]` 重命名为对应版本号
- 描述要简洁，一句话说清楚做了什么，不需要写原因

### 3.2 功能模块文档（docs/features/）

每个功能模块文档应包含：

```markdown
# 功能名称

## 概述
一句话说明这个功能是什么、解决什么问题。

## 设计思路
为什么这样设计，核心思路是什么。

## 实现细节
关键实现代码或流程图。

## 接口与使用
如何调用，入参出参说明。

## 相关文件
- `huaqi_src/core/xxx.py` - 说明
```

### 3.3 架构决策记录（docs/design/adr/ADR-xxx.md）

适用于：技术选型、架构重大变更、废弃旧方案等。

```markdown
# ADR-XXX: 决策标题

**状态**: 已采纳 / 已废弃 / 待定  
**日期**: YYYY-MM-DD

## 背景
为什么需要做这个决策。

## 决策
最终选择了什么方案。

## 备选方案
考虑过哪些方案，为什么没选。

## 结果
这个决策带来了哪些影响。
```

### 3.4 迭代验收文档（docs/iterations/{迭代名}/acceptance.md）

在确定设计方案后，由 agent 根据计划文档生成。迭代结束后，由 agent 逐条执行验收。

```markdown
# [特性名] 迭代验收

**迭代标识**: 2026-10-04-telos-refactor
**验收日期**: YYYY-MM-DD
**关联计划**: [docs/plans/2026-10-04-telos-refactor.md](../../../plans/2026-10-04-telos-refactor.md)

---

## 功能 Checklist

| # | 功能点 | 验证命令 | 通过条件 | 状态 |
|---|--------|---------|---------|------|
| 1 | Telos 初始化 | `pytest tests/unit/layers/growth/test_telos_engine.py` | exit code 0，无 FAILED | ✅ |
| 2 | 人际关系图写入 | `pytest tests/unit/layers/growth/people/` | exit code 0 | ⚠️ |
| 3 | CLI 对话触发调度 | `huaqi chat "test"` | 日志中出现 `scheduler triggered` | ❌ |

状态取值：`✅` 已验证通过 / `❌` 未完成 / `⚠️` 有问题（见已知问题）

---

## Out of Scope

本次迭代明确不包含：
- XXX（原因：留到下一迭代）

---

## 已知问题 / 遗留事项

| ID | 描述 | 优先级 | 处理方式 |
|----|------|--------|---------|
| B-001 | XXX 场景下偶现崩溃 | P1 | 已录入全局 BUGLIST，下迭代修复 |

---

## 验证环境

- Python 版本: 3.x
- 测试命令: `pytest tests/ -x`
```

**规则：**
- 验证命令必须可直接执行，通过条件必须可客观判断（exit code、输出关键词等）
- agent 执行验收时逐行运行验证命令，对照通过条件填写状态
- 发现的问题录入本迭代 `buglist.md`，同时同步到全局 `BUGLIST.md`

### 3.5 迭代 Bug 清单（docs/iterations/{迭代名}/buglist.md）

记录本次迭代发现的所有 bug，支持多轮循环修复，按轮次分节追加。

```markdown
# [特性名] 迭代 Bug 清单

**所属迭代**: 2026-10-04-telos-refactor

---

## Round 1 - YYYY-MM-DD

| ID | 描述 | 复现命令 | 优先级 | 状态 |
|----|------|---------|--------|------|
| B-003 | Telos engine 初始化失败 | `pytest tests/unit/layers/growth/test_telos_engine.py` | P1 | fixed |
| B-004 | 人际关系图节点重复写入 | `pytest tests/unit/layers/growth/people/` | P2 | open |

## Round 2 - YYYY-MM-DD

| ID | 描述 | 复现命令 | 优先级 | 状态 |
|----|------|---------|--------|------|
| B-004 | 人际关系图节点重复写入 | `pytest tests/unit/layers/growth/people/` | P2 | fixed |
| B-005 | XXX 新发现问题 | `pytest tests/xxx` | P1 | open |
```

**Agent 操作规范：**
- 每轮开始前：检查上轮所有 `open` 条目，验证是否已修复，更新状态
- 每轮结束时：将新发现的 bug 追加到新节，状态为 `open`
- 终止条件：当前轮无新 `open` 条目
- 影响关键链路的 bug 同步录入全局 `BUGLIST.md`

### 3.6 全局 Bug 清单（docs/iterations/BUGLIST.md）

仅收录影响关键链路的 bug，每次迭代验收时必须逐条回归验证。

```markdown
# 全局 Bug 清单

> 仅收录影响关键链路的 bug，每次迭代验收时必须逐条回归验证。

## 活跃 Bug

| ID | 描述 | 优先级 | 状态 | 发现迭代 | 修复迭代 |
|----|------|--------|------|---------|---------|
| B-001 | XXX 场景崩溃 | P1 | open | 2026-10-04-telos-refactor | - |

## 回归记录

| ID | 迭代 | 验证结果 | 备注 |
|----|------|---------|------|
| B-001 | 2026-11-04-telos-next | ⚠️ 仍存在 | 触发条件未变化 |
| B-001 | 2026-10-04-telos-refactor | ❌ 发现 | 首次记录 |

## 已关闭 Bug

| ID | 描述 | 关闭原因 | 关闭迭代 |
|----|------|---------|---------|
| B-002 | YYY 乱码 | 已修复验证通过 | 2026-11-04-telos-next |
```

**规则：**
- ID 全局唯一，格式 `B-NNN`，由本文件统一递增分配
- 优先级：`P0`（阻塞） / `P1`（严重） / `P2`（一般）
- 状态：`open` / `fixed` / `verified` / `wontfix`
- 每次迭代验收时，agent 必须对活跃 bug 逐条执行回归验证并追加回归记录

### 3.7 README.md
- 项目是什么（1-2 句话）
- 核心特性（表格，最多 7 条）
- 快速开始（3 步以内）
- 常用命令（不超过 10 条）
- 文档索引（链接到各子文档）

不要放：详细命令说明、架构细节、实现代码——这些放到对应子文档中。

---

## 四、文档命名约定

| 位置 | 命名规则 | 示例 |
|------|---------|------|
| 根目录 | 全大写，下划线 | `README.md`, `CHANGELOG.md` |
| docs/design/ | 全大写，下划线 | `ARCHITECTURE.md`, `TECH_SPEC.md` |
| docs/features/ | 小写，连字符 | `pattern-learning.md` |
| docs/guides/ | 小写，连字符 | `cli-guide.md` |
| docs/ops/ | 小写，连字符 | `migration-v2.md` |
| docs/design/adr/ | `ADR-NNN-短标题.md` | `ADR-002-langgraph-adoption.md` |
| docs/iterations/ | 迭代文件夹：`YYYY-MM-DD-{特性名}`，连字符小写 | `2026-10-04-telos-refactor/` |

---

## 五、文档版本信息

每个文档底部可选添加：

```markdown
---
**文档版本**: v1.0  
**最后更新**: YYYY-MM-DD  
```

`design/` 和 `features/` 下的文档建议加，`CHANGELOG.md` 和 `guides/` 不需要。

---

## 六、agent 编写文档时的检查清单

在编写或更新文档前，请确认：

- [ ] 这个改动属于哪种类型（bug fix / 小功能 / 大功能 / 架构决策）？
- [ ] 是否需要更新 `CHANGELOG.md`？
- [ ] 文档放在正确的目录下了吗（参考第一节的目录结构）？
- [ ] 文档命名遵循了第四节的约定吗？
- [ ] 如果修改了 CLI 命令，`docs/guides/user/cli-guide.md` 是否同步更新了？
- [ ] 如果涉及架构变化，`docs/design/ARCHITECTURE.md` 是否需要更新？
- [ ] 本次特性迭代是否需要新建 `docs/iterations/{迭代名}/` 文件夹？
- [ ] `acceptance.md` 是否已填写全部功能 Checklist（含验证命令和通过条件）？
- [ ] 迭代中发现的新 bug 是否已录入 `buglist.md` 并将关键链路 bug 同步到全局 `BUGLIST.md`？
- [ ] 全局 `BUGLIST.md` 中的活跃 Bug 是否在本迭代完成了回归验证并追加了回归记录？
