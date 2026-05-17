# CLAUDE.md

## 项目概况

**Huaqi (花旗)** — 个人 AI 同伴系统。核心理念："不是使用 AI，而是养育 AI"。
通过长期对话积累对用户的理解，成为真正懂你的数字伙伴。
作者：连子蒙，语言：Python 3.10+，许可证：MIT。

## 常用命令

```bash
# 环境与运行
pip install -e ".[dev]"             # 安装项目 + 开发依赖
huaqi                               # 启动 CLI（首次自动引导配置 data_dir）
huaqi chat                          # 进入 LangGraph Agent 对话
huaqi chat --list-sessions          # 列出最近会话
huaqi chat -s <thread_id>           # 恢复指定会话

# 测试
pytest tests/smoke_test.py -v        # 冒烟测试（每次迭代必须跑）
pytest tests/ -x                    # 快速运行所有测试
pytest tests/unit/                  # 仅单元测试
pytest tests/ -m "not e2e"          # 跳过端到端测试（需要真实 LLM）

# 代码质量
ruff check .                        # Lint 检查
ruff format .                       # 代码格式化
mypy huaqi_src/                     # 类型检查

# 配置
huaqi config show                   # 查看配置
huaqi config set data_dir           # 设置/修改数据目录
huaqi config set llm                # 配置 LLM

# 后台任务
huaqi daemon start                  # 启动定时任务
huaqi daemon status                 # 查看后台状态
huaqi scheduler list                # 列出定时任务

# 报告
huaqi report daily                  # 查看日报
huaqi report weekly                 # 查看周报
```

## 核心架构：三层 + Agent + 调度器

```
cli (Typer)
  ↓
agent (LangGraph StateGraph)
  ↓
layers/
  ├── data/         # 数据层：收、存、不丢（raw_signal → converters → SQLite/ChromaDB）
  ├── growth/       # 成长层：理解、提炼、更新（telos 知识图谱）
  └── capabilities/ # 能力层：帮用户干活（reports/learning/pipeline/personality/care/...）
  ↓
scheduler/          # APScheduler 驱动三层运转
config/             # 统一配置管理（paths/manager/adapters）
```

依赖方向**单向向下**，禁止反向依赖。`capabilities/` 和 `scheduler/` 可以依赖下层，但下层不能依赖它们。

## 源码目录速查

| 目录/文件 | 职责 |
|-----------|------|
| `cli.py` | CLI 入口（18行薄包装） |
| `huaqi_src/cli/__init__.py` | 子命令组装与主 app |
| `huaqi_src/cli/chat.py` | 对话主循环、斜杠命令 |
| `huaqi_src/cli/context.py` | 全局组件缓存、ensure_initialized |
| `huaqi_src/agent/state.py` | AgentState 定义（所有 workflow 共享） |
| `huaqi_src/agent/graph/chat.py` | 对话工作流状态图 |
| `huaqi_src/agent/nodes/chat_nodes.py` | 对话节点实现 |
| `huaqi_src/agent/tools.py` | Agent 可调用工具注册 |
| `huaqi_src/agent/hooks.py` | 对话后 Hook 触发 |
| `huaqi_src/config/manager.py` | 配置加载/保存 |
| `huaqi_src/config/paths.py` | 数据目录路径函数（统一入口） |
| `huaqi_src/layers/data/raw_signal/` | 统一摄取入口，所有输入由此进入 |
| `huaqi_src/layers/data/memory/` | 记忆检索（BM25 + 向量混合） |
| `huaqi_src/layers/data/collectors/` | 外部数据采集（CLI对话、微信等） |
| `huaqi_src/layers/growth/telos/` | TELOS 知识图谱提炼引擎 |
| `huaqi_src/layers/capabilities/reports/` | 定时报告（晨/日/周/季报） |
| `huaqi_src/layers/capabilities/pipeline/` | 内容流水线（X/RSS → 小红书） |
| `huaqi_src/layers/capabilities/llm/manager.py` | LLM 抽象层（多提供商） |
| `huaqi_src/scheduler/manager.py` | APScheduler 封装 |

## 数据流

```
外部数据 → layers/data/raw_signal（Converters） → layers/growth/telos（Engine） → agent → cli → 用户
```

## 编码规范（强制）

- **禁止万能桶目录**：不允许 `core/`、`utils/`、`common/`、`helpers/`、`misc/`
- **目录命名**：名词、小写下划线（如 `raw_signal/`），见名知意
- **文件角色**：`models.py`（数据模型）、`manager.py`（业务管理）、`store.py`（持久化）、`engine.py`（计算逻辑）、`base.py`（抽象基类）
- **禁止临时命名**：不允许 `_v2`、`_simple`、`_new`、`_old` 后缀
- **Pydantic 数据模型**：所有业务数据用 Pydantic，禁止裸 `dict` 传递
- **依赖方向**：单向向下。如果 `data/` 需要依赖 `growth/` 就说明设计错了
- **单例模式**：使用 `get_xxx()` 工厂函数 + 模块级 `_xxx: Optional[X] = None`，不用模块级直接初始化
- **公开接口**：通过模块 `__init__.py` 导出，外部 `from huaqi_src.layers.growth.telos import TelosManager`，不穿透到内部文件
- **文档**：公开类/函数必须有 docstring，说"做什么"不说"怎么做"
- **版本后缀禁止**：文件名不允许出现 `_v2`、`_simple`、`_new`、`_old`

## 开发工作流：Spec → Plan → Test → Code

四层文档，单向推进：

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
docs/project/design/          # 同步更新受影响的顶层设计文档（活文档）
```

> **顶层设计文档是活文档**：`docs/project/design/` 下的文档（PRD.md / ARCHITECTURE.md / TECH_SPEC.md）是项目的「当前真相」。
> 每次迭代结束时，如果实现结果改变了系统架构、技术选型、核心约定或模块边界，
> 必须在 `feature.md` 定稿的同时，将影响回写至 `docs/project/design/` 下的相应文档。
> 如果一个迭代的架构影响需要记录决策过程，先写 ADR，再更新 ARCHITECTURE。

**核心规则：**

1. **新功能必须先写 Spec**，格式为 `docs/iterations/<YYYY-MM-DD>-<feature>/spec.md`
2. **Spec 只写 WHAT 和 WHY，不写 HOW**——技术实现细节留给 Plan
3. **Spec 的验收标准必须可验证**——每条 AC 能直接翻译为 1-2 个测试函数
4. **Plan 从 Spec 的 AC 生成测试**，每个 Task 遵循「写失败测试 → 确认失败 → 写实现 → 确认通过」
5. **测试按 layer 分组**，新增 feature 在 `smoke_test.py` 末尾追加 `Test<FeatureName>` 类
6. **Plan 完成后**，将 Plan 中的关键设计结论移入同迭代目录的 `feature.md` 定稿

### 触发规则

Agent 判断当前任务属于以下哪种类型，自动决定需要写什么：

| 改动类型 | 必须产出 |
|----------|---------|
| 新功能 | `docs/iterations/<date>-<name>/spec.md` → `docs/iterations/<date>-<name>/plan.md` → tests → code → `docs/iterations/<date>-<name>/feature.md` |
| 功能增强（影响已有行为） | `docs/iterations/<date>-<name>/plan.md` → tests → code → 更新 `docs/iterations/<date>-<name>/feature.md` |
| Bug fix | tests（复现）→ code → `CHANGELOG.md` |
| 重构（不改变行为） | tests（保护）→ code |
| 架构变更 | `docs/project/design/adr/ADR-xxx.md` → `docs/project/design/ARCHITECTURE.md` |
| 迭代触及顶层设计 | 更新 `docs/project/design/` 中受影响文档（PRD / ARCHITECTURE / TECH_SPEC） |

### 迭代对顶层设计的反馈规则

迭代结束后，按以下规则判断是否需要更新 `docs/project/design/`：

| 迭代结果 | 需更新的顶层文档 |
|---------|-----------------|
| 新增/删除模块、改变依赖方向 | `ARCHITECTURE.md` |
| 改变技术选型、存储方案、LLM 策略 | `TECH_SPEC.md` |
| 新增/改变产品功能边界、用户体验流程 | `PRD.md` |
| 新增架构决策 | 先写 `adr/ADR-xxx.md` → 再更新 `ARCHITECTURE.md` |
| 纯修复 bug、不改变行为 | 不需要更新 |

**规则：**
1. 迭代 Plan 中应标注「是否触及顶层设计」，提前列出需要关注的项目级文档
2. Phase 4（Finalize）时，将迭代中沉淀的架构/设计变更回写至 `docs/project/design/`
3. 顶层设计文档的更新与 `feature.md` 定稿同步完成

### 模板

- Spec 模板：`docs/iterations/_templates/spec.md`
- Plan 模板：`docs/iterations/_templates/plan.md`

## 测试体系

测试四层金字塔，由上到下：运行频率从高到低，覆盖范围从窄到宽。

```
         运行频率     覆盖面      依赖
 单元     最高        窄（单函数）  无
 集成     高          中（跨层）    无（SQLite :memory:）
 冒烟     中等        宽（全模块）  无
 E2E      低          最宽（全链路）真实 LLM
```

### 单元测试 `tests/unit/`（~70 文件）

**目的**：验证单个函数/类的**业务逻辑正确性**。

**解决什么问题**：
- 改了函数 A，怎么确保函数 B 没被搞坏？（回归保护网）
- 重构内部实现时，外部行为一致吗？（行为不变性）
- 边界条件处理对了吗？空输入、负数、超长字符串？

**组织方式**：与源码目录一一对应，如 `tests/unit/layers/growth/test_telos_manager.py` 对应 `huaqi_src/layers/growth/telos/manager.py`。

**原则**：
- 运行快（无 IO、无网络），可以随时跑、频繁跑
- 用 Mock 替代 LLM、文件系统、外部 API
- 一个测试只验证一个行为

```bash
pytest tests/unit/ -x                  # 快速通过所有单元测试
pytest tests/unit/layers/growth/ -x    # 只跑 growth 层的单元测试
```

### 集成测试 `tests/integration/`（3 文件）

**目的**：验证**跨模块/跨层的交互**是否正确。

**解决什么问题**：
- 单元测试都绿了，但拼在一起能工作吗？（接口匹配性）
- 数据从 raw_signal → converters → store 这条链路的格式对吗？（数据流正确性）
- 组件之间传的是 Pydantic 模型，字段名和类型对得上吗？（契约一致性）

**原则**：
- 用真实的 SQLite（`:memory:`）、真实的 tmp_path，不用 mock
- 只验证接口和数据流，不测业务细节
- 每个集成测试覆盖一条核心数据流链路

```bash
pytest tests/integration/ -v
```

### 冒烟测试 `tests/smoke_test.py`（116 用例）

**目的**：每次迭代的**功能验收**——系统还是完整的吗？

**解决什么问题**：
- 改了一个模块的 API，有没有其他模块用了旧 API 没更新？（接口兼容性）
- 新加的代码破坏了单向依赖规则吗？（架构约束）
- 所有 store/manager/engine 还能正常初始化吗？（模块可用性）
- 所有数据模型能正确序列化/反序列化吗？（持久化正确性）
- 空数据、Unicode、特殊字符场景会崩溃吗？（边界健壮性）

**设计原则**：
1. **按架构 layer 组织**，与 `huaqi_src/layers/` 结构对应
2. **不测试业务逻辑细节**（那是单元测试的事），只验证模块初始化、数据流、架构约束、模型 roundtrip、边界条件
3. **每个 feature 的冒烟测试追加在末尾的 Feature Acceptance Tests 区域**，注释标注对应 Spec 的 AC 编号
4. **随项目迭代增长**——每个新 feature 追加冒烟测试，但不删除已有测试

```bash
pytest tests/smoke_test.py -v          # 每次迭代完成后必须运行
```

### 端到端测试 `tests/e2e/`（1 文件）

**目的**：验证**真实 LLM 调用**的完整流程。

**解决什么问题**：
- Prompt 改了之后 LLM 的输出格式还能解析吗？（LLM 输出兼容性）
- 快开发布了，真实调用整个链路能走通吗？（发布前确认）

**原则**：
- 需要真实的 LLM API Key，不常跑
- 只覆盖最核心的链路（TELOS 提炼），不追求覆盖率

```bash
pytest tests/e2e/ -v                   # 重大发布前运行
pytest tests/ -m "not e2e"             # 日常跳过 e2e
```

### Agent 行为规则：何时自动运行测试

Agent 必须根据所做改动的**影响范围**，自动选择并运行对应的测试层级。运行顺序由窄到宽：先单元，通过后再集成，最后冒烟。

| 触发条件 | 自动运行 | 原因 |
|----------|---------|------|
| 编辑了任意 `huaqi_src/` 下的 `.py` 文件 | 对应的 unit test（`tests/unit/<mirror-path>.py`） | 验证改动没有破坏该模块的业务逻辑 |
| 编辑了 `config/adapters/` 或跨层 import 的模块 | 对应 unit test **+** `tests/integration/` | 跨层接口变更可能影响上游调用方 |
| 一个 Plan Task 的所有 Step 完成 | 本 Task 涉及的 unit tests **+** `tests/smoke_test.py`（如果本 Task 追加了冒烟测试） | Plan 模板 Step 5 要求 |
| 用户说「迭代完成」「这个 feature 做完了」 | `tests/smoke_test.py -v` | 全量功能验收 |
| 用户要求 commit / 合并到 main | `tests/smoke_test.py -v && pytest tests/ -x -m "not e2e"` | 合并前回归检查 |
| 用户要求发布 / 打 tag | `pytest tests/ -v`（含 e2e） | 发布前全量验证 |

Agent 运行测试后，必须向用户报告结果：通过了多少、失败了几项。如果失败，在修复代码后重新运行对应测试，直到全部通过。

## 重要区分

- **源码目录**：`~/workspace/huaqi-growing/`（本仓库）
- **用户数据目录**：由 `--data-dir` 或 `HUAQI_DATA_DIR` 环境变量指定（如 `~/.huaqi/`），完全独立于源码
- **Git 同步管理的是用户数据目录**，而非源码目录
