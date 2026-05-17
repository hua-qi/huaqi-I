# Spec: docs 目录重组

## 1. 要解决的问题

当前 `docs/` 目录结构存在以下问题：

- **`design/` vs `designs/`** 名称相似但用途不同，极易混淆（前者是宏观架构，后者是历史设计草稿）
- **迭代文档分散**：`specs/`、`plans/`、`features/` 分属三个平级目录，无法一眼看出哪些文件属于同一次迭代
- **没有清晰的「项目全局」vs「迭代范围」边界**：guides/、design/、specs/、plans/ 全部平铺在 docs/ 下，缺乏组织层次
- **模板文件散落**：`_TEMPLATE.md` 分别藏在 `specs/` 和 `plans/` 下，不够显眼

## 2. 功能范围

- 重组 `docs/` 目录结构，建立「项目全局」和「迭代范围」两层组织
- 将 `specs/`、`plans/`、`features/`、`designs/` 中的文件按日期归入对应迭代目录
- 更新所有引用 docs 路径的文件
- 更新 CLAUDE.md 开发工作流章节以反映新结构

**不包含**：
- 不修改任何文件的内容（纯重组 + 路径更新）
- 不新增或删除功能文档
- 不修改 `tests/` 目录结构

## 3. 技术选型

### 3.1 新目录结构

```
docs/
├── project/                          # 项目全局文档（跨迭代、持久存在）
│   ├── design/                       # 顶层设计（3 份活文档 + ADR）
│   │   ├── adr/                      # 架构决策记录
│   │   │   └── ADR-*.md
│   │   ├── PRD.md                    # 产品要做什么、给谁用、功能边界
│   │   ├── ARCHITECTURE.md           # 系统架构、模块关系、数据流
│   │   └── TECH_SPEC.md              # 技术选型、版本、选型理由
│   └── guides/                       # 使用与开发指南
│       ├── user/
│       │   ├── cli-guide.md
│       │   └── IMPORT_GUIDE.md
│       └── dev/
│           ├── DOC_GUIDELINES.md
│           ├── usage.md
│           ├── code-standards.md
│           └── cli-ui-improvements.md
│
└── iterations/                       # 迭代文档（按日期-特性名组织）
    ├── _templates/                   # Spec 和 Plan 模板
    │   ├── spec.md
    │   └── plan.md
    ├── BUGLIST.md                    # 全局 bug 清单（跨迭代）
    └── <YYYY-MM-DD>-<feature-name>/  # 具体迭代目录
        ├── spec.md                   # 功能顶层设计（原 specs/<name>.md）
        ├── plan.md                   # 实施方案（原 plans/<name>.md）
        ├── feature.md                # 实现定稿（原 features/<name>.md）
        ├── design.md                 # 设计草稿（原 designs/<name>.md，可选）
        ├── acceptance.md             # 迭代验收（原 iterations/<name>/acceptance.md）
        └── buglist.md                # 迭代 bug 清单（原 iterations/<name>/buglist.md）
```

### 3.2 顶层设计文档合并

原 `docs/design/` 有 6 份文档，存在重叠：

| 文档 | 问题 |
|------|------|
| SPEC.md | 与 PRD.md 重叠（愿景/目标），与 ARCHITECTURE.md 重叠（架构图/模块描述） |
| MULTI_USER_DESIGN.md | 特定功能设计，不是「顶层」，应归入迭代目录 |
| memory-retrieval-strategy.md | 特定策略分析，已有 ADR-003 覆盖决策，应归入迭代目录 |

合并后保留 **3 份活文档**，各司其职：

```
PRD.md          ← PRD.md（产品定位/目标用户/功能需求）
                   + SPEC.md（核心理念/设计原则/系统目标）

ARCHITECTURE.md ← ARCHITECTURE.md（整体架构/三层结构/数据流）
                   + SPEC.md（7 层架构图/模块功能概述）

TECH_SPEC.md    ← TECH_SPEC.md（技术栈选型/版本要求/选型理由）
                   + ARCHITECTURE.md（技术特色部分）
```

**移除的文档处理**：
- `SPEC.md` → 删除，内容分流至 PRD.md 和 ARCHITECTURE.md
- `MULTI_USER_DESIGN.md` → 移入 `docs/iterations/` 对应迭代目录
- `memory-retrieval-strategy.md` → 移入 `docs/iterations/` 对应迭代目录（与 ADR-003 同目录）

### 3.3 移动映射

| 原位置 | 新位置 |
|--------|--------|
| `docs/design/adr/**` | `docs/project/design/adr/**` |
| `docs/design/PRD.md` | `docs/project/design/PRD.md`（合并 SPEC.md 的愿景/原则/目标部分） |
| `docs/design/ARCHITECTURE.md` | `docs/project/design/ARCHITECTURE.md`（合并 SPEC.md 的架构/模块部分） |
| `docs/design/TECH_SPEC.md` | `docs/project/design/TECH_SPEC.md` |
| `docs/design/SPEC.md` | **删除**，内容分流至 PRD.md + ARCHITECTURE.md |
| `docs/design/MULTI_USER_DESIGN.md` | 移入 `docs/iterations/` 对应迭代目录 |
| `docs/design/memory-retrieval-strategy.md` | 移入 `docs/iterations/` 对应迭代目录 |
| `docs/guides/**` | `docs/project/guides/**` |
| `docs/specs/<name>.md` | `docs/iterations/<date>-<name>/spec.md` |
| `docs/plans/<name>.md` | `docs/iterations/<date>-<name>/plan.md` |
| `docs/features/<name>.md` | `docs/iterations/<date>-<name>/feature.md` |
| `docs/designs/<date>-<name>.md` | `docs/iterations/<date>-<name>/design.md` |
| `docs/iterations/<date>-<name>/**` | `docs/iterations/<date>-<name>/**`（内容不变） |
| `docs/iterations/BUGLIST.md` | `docs/iterations/BUGLIST.md`（不变） |
| `docs/specs/_TEMPLATE.md` | `docs/iterations/_templates/spec.md` |
| `docs/plans/_TEMPLATE.md` | `docs/iterations/_templates/plan.md` |
| `docs/plans/ops/**` | `docs/iterations/ops/**`（运维类迭代） |
| `docs/plans/ROADMAP.md` | `docs/iterations/ROADMAP.md` |

### 3.3 文件名规则

迭代目录下使用**固定文件名**（不再带日期前缀或功能名）：
- `spec.md` — 功能顶层设计
- `plan.md` — 实施方案
- `feature.md` — 实现定稿
- `design.md` — 设计草稿（可选）
- `acceptance.md` — 迭代验收
- `buglist.md` — 迭代 bug 清单

迭代目录名本身已包含日期和功能名，目录内无需重复。

## 4. 验收标准

- [ ] AC-1: `docs/project/design/` 包含 3 份活文档（PRD.md / ARCHITECTURE.md / TECH_SPEC.md）+ `adr/` 子目录
- [ ] AC-2: SPEC.md 已删除，其内容分流至 PRD.md（愿景/原则/目标）和 ARCHITECTURE.md（架构图/模块概述）
- [ ] AC-3: MULTI_USER_DESIGN.md 和 memory-retrieval-strategy.md 已移入对应迭代目录
- [ ] AC-4: `docs/project/guides/` 目录存在，内容与原 `docs/guides/` 一致
- [ ] AC-5: 所有迭代文档（specs/plans/features/designs）已按日期归入 `docs/iterations/<date>-<name>/` 并重命名为固定文件名
- [ ] AC-6: 旧的 `docs/specs/`、`docs/plans/`、`docs/features/`、`docs/designs/`、`docs/design/`、`docs/guides/` 目录已删除（内容已迁移）
- [ ] AC-7: `docs/iterations/_templates/` 目录存在，包含 spec.md 和 plan.md
- [ ] AC-8: `docs/guides/dev/DOC_GUIDELINES.md` 中「文档目录结构」章节反映新结构
- [ ] AC-9: `CLAUDE.md` 开发工作流章节完整更新（路径引用、触发规则表、迭代对顶层设计的反馈规则）
- [ ] AC-10: `.claude/skills/develop/SKILL.md` 中的路径引用已更新
- [ ] AC-11: `README.md` 中的 docs 链接全部有效（指向新路径）
- [ ] AC-12: `CHANGELOG.md` 中的 docs 路径引用已更新
- [ ] AC-13: `tests/smoke_test.py` 中 Spec 引用路径已更新
- [ ] AC-14: `pytest tests/smoke_test.py -v` 全部通过（重组不影响代码行为）
- [ ] AC-15: `ruff check .` 无新增 lint 错误
- [ ] AC-2: 所有 `docs/specs/`、`docs/plans/`、`docs/features/` 中的文件已按日期归入 `docs/iterations/<date>-<name>/` 并重命名为固定文件名（spec.md / plan.md / feature.md）
- [ ] AC-3: 所有 `docs/designs/` 中的设计草稿已按日期移入对应迭代目录
- [ ] AC-4: 旧的 `docs/specs/`、`docs/plans/`、`docs/features/`、`docs/designs/`、`docs/design/`、`docs/guides/` 目录已删除（内容已迁移）
- [ ] AC-5: `docs/iterations/_templates/` 目录存在，包含 `spec.md` 和 `plan.md`
- [ ] AC-6: `docs/guides/dev/DOC_GUIDELINES.md` 中「文档目录结构」章节反映新结构
- [ ] AC-7: `CLAUDE.md` 开发工作流章节完整更新：路径引用、触发规则表、新增「迭代对顶层设计的反馈规则」章节
- [ ] AC-8: `.claude/skills/develop/SKILL.md` 中的路径引用已更新
- [ ] AC-9: `README.md` 中的 docs 链接全部有效（指向新路径）
- [ ] AC-10: `CHANGELOG.md` 中的 docs 路径引用已更新
- [ ] AC-11: `tests/smoke_test.py` 中 Spec 引用路径已更新
- [ ] AC-12: `pytest tests/smoke_test.py -v` 全部通过（重组不影响代码行为）
- [ ] AC-13: `ruff check .` 无新增 lint 错误

## 4. CLAUDE.md 开发工作流章节变更

以下为开发工作流章节的改动要点的字符串对照：

### 4.1 工作流图

**旧**：
```
docs/specs/<feature>.md      # WHAT：要解决什么问题、验收标准（顶层设计）
  ↓
docs/plans/<feature>.md      # HOW：分几个 Task、改哪些文件、什么顺序（实施方案）
  ↓
测试（按金字塔逐层加）：
  1. unit tests              # 验证单个函数/类的业务逻辑（TDD：先红后绿）
  2. integration tests       # 跨层接口改动时加
  3. smoke test              # 从 Spec 的 AC 追加 Feature Acceptance Test
  ↓
huaqi_src/...                 # IMPLEMENTATION：写代码让所有测试从红变绿
  ↓
docs/features/<feature>.md    # 实现完成后定稿
```

**新**：
```
docs/iterations/<YYYY-MM-DD>-<feature>/spec.md     # WHAT：要解决什么问题、验收标准（迭代级设计）
  ↓
docs/iterations/<YYYY-MM-DD>-<feature>/plan.md     # HOW：分几个 Task、改哪些文件、什么顺序（实施方案）
  ↓
测试（按金字塔逐层加）：
  1. unit tests              # 验证单个函数/类的业务逻辑（TDD：先红后绿）
  2. integration tests       # 跨层接口改动时加
  3. smoke test              # 从 Spec 的 AC 追加 Feature Acceptance Test
  ↓
huaqi_src/...                 # IMPLEMENTATION：写代码让所有测试从红变绿
  ↓
docs/iterations/<YYYY-MM-DD>-<feature>/feature.md   # 实现完成后定稿
  ↓ （如本迭代改变了架构/设计）
docs/project/design/          # 同步更新受影响的顶层设计文档（ARCHITECTURE / TECH_SPEC / ADR 等）
```

> **顶层设计文档是活文档**：`docs/project/design/` 下的文档是项目的「当前真相」。
> 每次迭代结束时，如果实现结果改变了系统架构、技术选型、核心约定或模块边界，
> 必须在 `feature.md` 定稿的同时，将影响回写至 `docs/project/design/` 下的相应文档。
> 如果一个迭代的架构影响需要记录决策过程，先写 ADR，再更新 ARCHITECTURE。```

### 4.2 核心规则

**旧**：
```
1. **新功能必须先写 Spec**，不用日期前缀，用功能名命如 `docs/specs/reports-reminder.md`
```

**新**：
```
1. **新功能必须先写 Spec**，格式为 `docs/iterations/<YYYY-MM-DD>-<feature>/spec.md`
```

**旧**：
```
6. **Plan 完成后**，将 Plan 中的关键设计结论移入 `docs/features/<feature>.md` 定稿
```

**新**：
```
6. **Plan 完成后**，将 Plan 中的关键设计结论移入同迭代目录的 `feature.md` 定稿
```

### 4.3 触发规则表

| 改动类型 | 必须产出 |
|----------|---------|
| 新功能 | `docs/iterations/<date>-<name>/spec.md` → `docs/iterations/<date>-<name>/plan.md` → tests → code → `docs/iterations/<date>-<name>/feature.md` |
| 功能增强（影响已有行为） | `docs/iterations/<date>-<name>/plan.md` → tests → code → 更新 `docs/iterations/<date>-<name>/feature.md` |
| 架构变更 | `docs/project/design/adr/ADR-xxx.md` → `docs/project/design/ARCHITECTURE.md` |

增加一行：

| 迭代触及顶层设计 | 更新 `docs/project/design/` 中受影响文档（ARCHITECTURE / TECH_SPEC / SPEC / PRD） |

### 4.4 迭代对顶层设计的反馈规则（新增章节）

迭代结束后，按以下规则判断是否需要更新 `docs/project/design/`：

| 迭代结果 | 需更新的顶层文档 |
|---------|-----------------|
| 新增/删除模块、改变依赖方向 | `ARCHITECTURE.md` |
| 改变技术选型、存储方案、LLM 策略 | `TECH_SPEC.md` |
| 新增/改变产品功能边界、用户体验流程 | `SPEC.md` / `PRD.md` |
| 新增架构决策 | 先写 `adr/ADR-xxx.md` → 再更新 `ARCHITECTURE.md` |
| 纯修复 bug、不改变行为 | 不需要更新 |

**规则：**
1. 迭代 Plan 中应标注「是否触及顶层设计」，提前列出需要关注的项目级文档
2. Phase 4（Finalize）时，将迭代中沉淀的架构/设计变更回写至 `docs/project/design/`
3. 顶层设计文档的更新与 `feature.md` 定稿同步完成

### 4.5 模板路径

**旧**：
```
- Spec 模板：`docs/specs/_TEMPLATE.md`
- Plan 模板：`docs/plans/_TEMPLATE.md`
```

**新**：
```
- Spec 模板：`docs/iterations/_templates/spec.md`
- Plan 模板：`docs/iterations/_templates/plan.md`
```

## 5. 依赖

- 依赖：无（纯文档重组）
- 被依赖：开发工作流、develop skill、所有引用 docs 路径的文件

## 6. 风险与假设

- **风险**：大量文件移动后 git 可能丢失文件历史。**缓解**：使用 `git mv` 保留历史
- **风险**：某些文件的日期前缀不规范导致归入迭代目录时判断困难。**缓解**：Plan 阶段列出完整映射表，人工确认
- **假设**：`docs/plans/ops/` 属于运维性质的计划，作为独立「迭代」目录处理
- **假设**：`docs/plans/ROADMAP.md` 属于跨迭代的路线图，放在 `docs/iterations/` 根下
