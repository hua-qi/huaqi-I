# DATA_DIR 目录组织规范与文档规范

**状态**：草稿  
**日期**：2026-04-17  
**范围**：用户自定义存储目录（DATA_DIR，如 `~/.huaqi/` 或用户指定路径）

---

## 背景与动机

当前 DATA_DIR 存在四个核心问题：

1. **目录定义不清晰**：不知道某个数据应该放哪个目录
2. **各子目录职责重叠**：如 `memory/` 与 `signals/` 的原始信号归属模糊
3. **文件命名不一致**：无统一格式，根据感觉命名
4. **新子目录无内部文档模板**：新增子目录时缺少标准说明

---

## 一、目录结构规范

### 1.1 顶层结构

```
<DATA_DIR>/
├── config.yaml               # 全局配置
├── memory/                   # 记忆与认知数据
├── signals/                  # 待处理原始信号
├── telos/                    # TELOS 8维度认知蒸馏结果
├── drafts/                   # 内容草稿（待发布）
├── pending_reviews/          # 待人工审核的 AI 输出
├── people/                   # 关系人长期档案
├── world/                    # 世界知识与新闻
├── learning/                 # 学习记录
├── vector_db/                # 向量数据库（可再生成，gitignore）
├── models/                   # 本地模型缓存（gitignore）
├── scheduler.db              # 调度器数据库
└── signals.db                # 信号数据库
```

### 1.2 子目录职责边界

| 目录 | 放什么 | 不放什么 |
|------|--------|---------|
| `memory/` | 对话历史、日记、用户画像、成长数据 | 未处理的原始信号 |
| `signals/` | 待处理的原始信号（工作日志、网页采集等） | 已蒸馏的认知结论 |
| `telos/` | 8 维度认知蒸馏结果 YAML | 原始对话记录、未处理信号 |
| `drafts/` | 正在编辑中的内容 | 已发布或已废弃内容 |
| `pending_reviews/` | 需人工确认的 AI 输出 | 已确认内容 |
| `people/` | 关系人长期档案 | 单次对话中仅提及的人名 |
| `world/` | 世界知识、新闻、行业动态 | 个人工作日志 |
| `learning/` | 学习记录与笔记 | 已蒸馏进 telos 的认知结论 |

---

## 二、文件命名规范

### 2.1 三类数据对应三种命名策略

#### 流水数据：年/月/日三级时间目录

适用于日记、对话历史、原始信号等**持续产生的时序内容**。

```
<domain>/
└── YYYY/
    └── MM/
        └── DD/
            └── <slug>.md
```

同一天内有多个文件时，在 `DD/` 目录下用描述性 slug 区分：

```
memory/
├── diary/
│   └── 2026/04/17/
│       └── daily.md
├── conversations/
│   └── 2026/04/17/
│       ├── 143022_about_design.md      # HHmmss_<主题>
│       └── 163015_work_plan.md
└── cli_chats/
    └── codeflicker/
        └── 2026/04/17/
            └── 143022.md               # 按会话时刻命名

signals/
└── 2026/04/17/
    ├── worklog.md
    └── web_capture.md
```

#### 月度蒸馏数据：年/月两级目录

适用于更新频率较低、按月汇总的内容：

```
telos/
└── 2026/
    └── 04/
        ├── work_style.yaml
        ├── learning_pattern.yaml
        └── social_trait.yaml
```

#### 档案数据：无时间目录，直接文件

适用于**长期稳定**、不随时间版本化的内容：

```
memory/
├── personality.yaml         # 固定名
└── growth.yaml              # 固定名

people/
├── zhang_wei.md             # <人名_slug>.md
└── li_ming.md

world/
└── ai_industry.md           # <主题_slug>.md
```

### 2.2 命名约定汇总

| 数据类型 | 目录结构 | 文件名格式 |
|----------|---------|-----------|
| 流水数据 | `<domain>/YYYY/MM/DD/` | `<slug>.md` 或 `HHmmss_<slug>.md` |
| 月度蒸馏 | `<domain>/YYYY/MM/` | `<dimension>.yaml` |
| 档案数据 | `<domain>/` | `<slug>.yaml` 或 `<slug>.md` |
| 数据库 | 根目录 | `<name>.db` |

### 2.3 通用命名约束

- 目录名和文件名统一使用 `snake_case`（全小写，下划线分隔）
- 禁止中文文件名（用拼音或英文 slug 代替）
- 禁止文件名中出现空格
- 禁止版本词汇（`final`、`v2`、`copy`、`backup` 等）
- slug 应具有业务语义，避免无意义编号（如 `file001.md`）

---

## 三、内部文档规范

### 3.1 目录级 README.md

**每个子目录必须有 `README.md`**，遵循统一模板：

```markdown
# <目录名>

## 职责
一句话说明此目录存放什么。

## 包含内容
- `<文件类型或模式>`：说明

## 禁止放置
- 列出明确不属于此目录的内容

## 文件结构
\`\`\`
<示例目录树>
\`\`\`

## 相关目录
- `../other_dir/`：关联关系说明
```

### 3.2 文件级 frontmatter

**所有 Markdown 文件**头部必须包含标准 frontmatter：

```yaml
---
type: diary | conversation | worklog | draft | person | knowledge | signal
created_at: 2026-04-17T14:30:00+08:00
updated_at: 2026-04-17T14:30:00+08:00
tags: []
source: cli | daemon | manual | agent
---
```

**YAML 文件**使用顶层 `meta` 字段代替 frontmatter：

```yaml
meta:
  type: personality | telos | config | person
  created_at: 2026-04-17T00:00:00+08:00
  updated_at: 2026-04-17T00:00:00+08:00
  version: "0.1"
```

`type` 字段枚举值说明：

| 值 | 适用场景 |
|----|---------|
| `diary` | 日记 |
| `conversation` | 对话历史 |
| `worklog` | 工作日志信号 |
| `signal` | 其他原始信号 |
| `draft` | 内容草稿 |
| `person` | 关系人档案 |
| `knowledge` | 知识/学习笔记 |
| `personality` | 用户画像 |
| `telos` | 认知蒸馏结果 |
| `config` | 配置文件 |

### 3.3 新子目录上线 Checklist

新增子目录前必须满足所有条件：

- [ ] 目录名符合 `snake_case`
- [ ] 已创建 `README.md`，包含职责、内容类型、禁止项、关联目录
- [ ] 已在 `paths.py` 注册对应 `get_xxx_dir()` 函数
- [ ] 已确认与现有目录无职责重叠（参考 1.2 职责边界表）
- [ ] 已确认该目录的文件类型和 frontmatter `type` 枚举值

---

## 四、实施计划

本规范落地需要以下步骤：

1. **现有数据文件迁移**：将不符合新规范的文件移动到正确位置
2. **创建各子目录 README.md**：为每个已有子目录补充文档
3. **修改 `paths.py` 等代码**：新增 `signals/` 相关函数，统一路径常量
4. **修改写入逻辑自动添加 frontmatter**：在各数据写入处自动注入 frontmatter

具体实施以独立任务推进，本文档仅定义规范标准。
