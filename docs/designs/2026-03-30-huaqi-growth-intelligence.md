# Huaqi 成长智能系统：深度用户理解、信息采集扩展与世界感知

**Date:** 2026-03-30

## Context

huaqi 的核心目标是造就一位可以自成长的 AI 同伴，通过深度理解用户来帮助用户成长。当前 huaqi 已具备基础对话、日记、技能追踪、内容流水线等功能，但在以下几个方向存在明显提升空间：

1. **用户深度理解**：仅基于日记和对话，数据源单一，缺少周/季/年粒度的成长总结
2. **信息采集扩展**：微信聊天、其他 Agent CLI 对话、工作文档等富含用户信息的数据源尚未接入
3. **世界感知**：需定期获取 X、小红书、今日头条等平台热门信息，帮助用户理解世界动态

基于"人是一切社会关系的综合"的世界观，还需要增加对用户社交网络中其他人的画像和关系分析能力。

## Discussion

### 架构选型

讨论了三种架构方案：
- **方案 A（统一数据湖）**：所有数据源归一化后进入统一存储，分析引擎从数据湖读取
- **方案 B（消息总线）**：各数据源独立采集，通过事件总线分发给各领域处理器
- **方案 C（渐进式扩展）**：在现有架构基础上最小化扩展

最终选择**方案 A（统一数据湖）**，架构清晰，扩展性强，长期维护成本低。

### 存储分层策略

三层互补存储，各司其职：
- **Markdown**：人类可读存档，纳入 Git 版本控制，是主要持久化格式
- **SQLite**：结构化元数据索引，用于按条件过滤、统计、关系查询
- **Chroma**：语义检索引擎，将文本向量化，支持模糊语义查询

所有数据均存储在用户自定义的 `data_dir/` 目录下，可迁移；Chroma 向量库属于可重建的派生数据，迁移后可通过 `huaqi system rebuild-index` 重新构建。

### Agent + Tool 驱动的记忆检索

huaqi 的核心架构哲学：**数据由 Collector 存入，由 Tool 取出，由 Agent 理解**。

LangGraph Agent 在生成报告或对话时，自主推理需要哪些信息，然后调用对应的 Tool 检索数据湖，而不是执行固定流程。这是"AI 同伴"与"定时脚本"的本质区别。

### 数据采集策略分类

根据数据特性，采集方式分为两类：

| 类型 | 数据源 | 采集方式 |
|------|--------|----------|
| 用户主动产生 | 工作文档、笔记、公众号文章 | 放入 `inbox/` 目录，手动触发处理 |
| 系统自动产生 | 微信聊天记录、其他 CLI 对话 | 本地 watchdog 监听，增量采集 |
| 外部世界信息 | X、小红书、今日头条、RSS | 定时网络抓取（每日 07:00） |

### 世界感知数据源扩展性

用户明确提出需要支持扩展新数据源（如 B 站热搜），确定采用**插件化架构**，用户可通过编写 Python 插件实现 `BaseWorldSource` 接口并放入 `plugins/` 目录来扩展。

### 成长报告设计

确认需要支持四个周期的成长报告，同时新增晨间简报：

| 报告 | 触发时间 | 核心内容 |
|------|----------|----------|
| 晨间简报 | 每天 08:00 | 今日 Todo + 行动建议 + 世界热点 |
| 日终复盘 | 每天 23:00 | 当天得失 + 情绪回顾 |
| 周报 | 每周日 21:00 | 成长亮点 + 目标进展 + 下周建议 |
| 季报 | 季末 | 长期模式 + 目标漂移识别 |
| 年报 | 12/31 | 人生叙事 + 重大成长节点 |

所有报告均由专属 LangGraph Agent 自主分析生成，Agent 自主决定调用哪些 Tool。

## Approach

整体方案以**统一数据湖 + Agent 自主分析**为核心，在现有 huaqi 基础设施（SQLite、Chroma、APScheduler、LangGraph）之上，新增以下能力：

1. **Collector 层**：统一的数据采集接口，支持监听类（微信/CLI）、手动类（Inbox）、网络类（世界感知）三种模式
2. **数据湖扩展**：新增 `wechat`、`cli_chats`、`work_docs`、`world`、`people` 等存储目录
3. **Tools 扩展**：每种新数据源对应一个新 Tool，Agent 可按需调用
4. **分析引擎升级**：从单一周报升级为日/周/季/年四档报告 + 晨间简报，均由 LangGraph Agent 驱动
5. **人物关系引擎**：新建 People Graph，支持人物画像自动提取和关系网络分析

## Architecture

### 整体架构

```
┌──────────────────────────────────────────────────────────────────┐
│                         数据采集层 (Collectors)                    │
│                                                                    │
│  [监听类]                          [手动类]                        │
│  WeChatWatcher  CLIChatWatcher     Inbox (工作文档/公众号/导出)     │
│  (watchdog)     (watchdog)         huaqi inbox sync               │
│                                                                    │
│  [网络类]                                                          │
│  WorldNewsFetcher (X/RSS/小红书/头条/插件)  定时 07:00             │
└───────────────────────────┬──────────────────────────────────────┘
                             ↓ 归一化为 HuaqiDocument
┌──────────────────────────────────────────────────────────────────┐
│                         统一数据湖                                 │
│  Markdown (.md)  │  SQLite (元数据/关系)  │  Chroma (语义检索)    │
│  data_dir/ 下，可迁移，Git 版本控制                                │
└───────────────────────────┬──────────────────────────────────────┘
                             ↓ Tools 层（Agent 调用接口）
┌──────────────────────────────────────────────────────────────────┐
│                         Tools 层                                   │
│  search_diary  search_wechat  search_cli_chats  search_work_docs  │
│  search_worldnews  search_person  get_relationship_map            │
│  get_goals_status  get_skills_progress  get_emotion_trend         │
└───────────────────────────┬──────────────────────────────────────┘
                             ↓ Agent 自主调用
┌──────────────────────────────────────────────────────────────────┐
│                         分析引擎（LangGraph Agents）               │
│  对话 Agent      │  晨间简报 Agent   │  日终复盘 Agent             │
│  周报 Agent      │  季报 Agent       │  年报 Agent                 │
│  人物提取 Agent  │  世界摘要 Agent                                  │
└───────────────────────────┬──────────────────────────────────────┘
                             ↓
┌──────────────────────────────────────────────────────────────────┐
│                         输出层                                     │
│  对话回复  │  晨间简报(08:00)  │  日报(23:00)  │  周/季/年报       │
│  人物画像  │  世界摘要          │  Todo 建议                       │
└──────────────────────────────────────────────────────────────────┘
```

### 统一文档结构

所有数据源归一化为 `HuaqiDocument`：

```python
class HuaqiDocument:
    doc_id: str          # 唯一 ID
    doc_type: str        # "wechat" | "cli_chat" | "work_doc" | "world_news" | "diary" | ...
    source: str          # 来源标识（"wechat:张三", "file:/path/to/doc.md"）
    content: str         # 正文内容
    summary: str         # AI 摘要（可选，采集时生成）
    people: list[str]    # 涉及的人物
    timestamp: datetime
    metadata: dict       # 扩展字段
```

### 数据存储目录结构

```
data_dir/                          # 用户自定义目录（config.yaml 中配置）
├── memory/
│   ├── conversations/             # 对话历史（已有）
│   ├── diary/                     # 日记（已有）
│   ├── wechat/YYYY-MM/            # 按联系人/群组归类的微信记录
│   └── cli_chats/YYYY-MM/         # 其他 CLI Agent 对话记录
├── inbox/                         # 用户手动放入待处理文件
│   ├── work_docs/
│   ├── wechat_exports/
│   └── cli_chats/
├── world/                         # 世界感知摘要（按日期）
│   └── 2026-03-30.md
├── reports/                       # 成长报告
│   ├── daily/2026-03-30.md
│   ├── weekly/2026-W13.md
│   ├── quarterly/2026-Q1.md
│   └── yearly/2026.md
├── people/                        # 人物画像
│   └── 张三.md
├── events.db                      # SQLite（事件、元数据、人物关系）
├── vector_db/                     # Chroma 向量库（可重建）
└── scheduler.db                   # APScheduler 任务库
```

### 各 Collector 设计

#### WeChatWatcher（微信监听）
- 监听 macOS 微信本地 SQLite DB（`~/Library/Containers/com.tencent.xinWeChat/...`）
- 通过 watchdog 感知 DB 文件变化，增量读取新消息（记录上次同步 rowid）
- 按联系人/群组归类，追加到 `data_dir/memory/wechat/YYYY-MM/联系人.md`
- 元数据写入 SQLite，向量化存入 Chroma
- **默认关闭**，需用户显式开启（`modules.wechat: true`）

#### CLIChatWatcher（CLI 对话监听）
- 监听用户配置的 CLI 工具对话目录（codeflicker、Claude 等）
- 支持 markdown / json / plaintext 多种格式解析
- 写入 `data_dir/memory/cli_chats/YYYY-MM/工具名-会话ID.md`

```yaml
collectors:
  cli_chat:
    enabled: true
    paths:
      - type: codeflicker
        path: ~/.codeflicker/conversations/
      - type: claude
        path: ~/.claude/
      - type: custom
        path: /any/path
        format: markdown
```

#### InboxProcessor（手动文档处理）
- 用户将文件放入 `data_dir/inbox/` 目录
- `huaqi inbox sync` 触发批量处理
- 支持 .md / .txt / .docx / .pdf 格式解析
- 处理后从 inbox 移出，标记已处理

```bash
huaqi inbox sync          # 处理 inbox 中所有待处理文件
huaqi inbox status        # 查看待处理/已处理文件
huaqi inbox list          # 列出已导入文档
```

#### WorldNewsFetcher（世界感知采集）
- 每日 07:00 定时触发（APScheduler）
- 支持内置数据源：X、RSS、小红书热榜、今日头条
- 支持用户自定义 RSS 和插件扩展（实现 `BaseWorldSource` 接口）
- 抓取失败时降级处理，不影响其他功能

```yaml
world_sources:
  - type: builtin
    id: xiaohongshu_hot
    enabled: true
  - type: rss
    url: https://xxx.com/feed
    name: 自定义订阅
  - type: plugin
    path: ~/.huaqi/plugins/bilibili_hot.py
```

### 人物关系引擎设计

#### 数据结构

```
People Graph
├── Person（节点）
│   ├── person_id / name / alias
│   ├── relation_type: 家人|朋友|同事|导师|合作者
│   ├── profile: AI 从对话/聊天中自动提取的性格、职业、兴趣
│   ├── emotional_impact: 积极|中性|消极（对用户情绪的影响倾向）
│   ├── interaction_frequency: 近 30 天互动次数
│   └── notes: 用户手动备注
│
└── Relation（边）
    ├── relation_strength: 0-100（互动频率 + 情感浓度综合计算）
    ├── topics: 主要交流话题
    └── history_summary: AI 生成的关系发展摘要
```

#### 人物信息来源

人物数据通过 AI 自动提取 + 用户补充两种方式建立：
- **微信聊天记录**：自动识别联系人，提取互动频率和话题
- **日记中提到的人**：提取情感倾向（正面/负面）
- **huaqi 对话**：用户主动提及的人
- **用户手动添加**：`/people add 张三 --relation 同事`

#### 命令行接口

```bash
huaqi people list                  # 列出所有关系人（按亲密度排序）
huaqi people show 张三             # 查看某人详细画像
huaqi people map                   # 可视化关系网络
huaqi people add 李四 --relation 朋友
huaqi people note 张三 "他喜欢直接说结论"
huaqi people delete 张三           # 删除某人数据（隐私保护）
```

#### 隐私保护约束
- 人物画像只存本地，不上传云端
- AI 判断（如 emotional_impact）标注为"huaqi 的观察"而非客观事实
- 用户可随时删除某人数据

### 新增 Tools 清单

| Tool | 用途 |
|------|------|
| `search_wechat_tool` | 语义搜索微信记录，支持按联系人过滤 |
| `search_cli_chats_tool` | 语义搜索其他 CLI 对话记录 |
| `search_work_docs_tool` | 语义搜索工作文档 |
| `search_worldnews_tool` | 搜索本地缓存的世界感知摘要 |
| `search_person_tool` | 查询某人画像和互动历史 |
| `get_relationship_map_tool` | 获取关系网络全图 |
| `get_person_interactions_tool` | 某时间段与某人的所有互动 |
| `analyze_relationship_impact_tool` | 分析某段关系对用户的整体影响 |
| `get_world_summary_tool` | 获取指定日期的世界摘要 |

### 新增模块清单

| 模块 | 建议路径 |
|------|----------|
| `WeChatWatcher` | `collectors/wechat_watcher.py` |
| `CLIChatWatcher` | `collectors/cli_chat_watcher.py` |
| `InboxProcessor` | `collectors/inbox_processor.py` |
| `BaseWorldSource` | `world/base_source.py` |
| `WorldNewsFetcher` | `world/fetcher.py` |
| `WorldSummaryAgent` | `world/summary_agent.py` |
| `PeopleGraph` | `people/graph.py` |
| `PersonExtractor` | `people/extractor.py` |
| `ReportAgent`（扩展） | `reports/agent.py` |

### 实施路线（分阶段）

**Phase 1（基础扩展）**
- InboxProcessor（工作文档导入）
- WorldNewsFetcher + WorldSummaryAgent（世界感知）
- 晨间简报 Agent（08:00 推送 Todo + 世界热点）

**Phase 2（深度理解）**
- PeopleGraph + PersonExtractor（人物关系引擎）
- 日/周/季/年报 Agent 升级（整合所有新数据源）

**Phase 3（监听采集）**
- WeChatWatcher（复杂度最高，需处理本地 DB 权限）
- CLIChatWatcher

### 核心设计原则

1. **数据由 Collector 存入，由 Tool 取出，由 Agent 理解**
2. **所有数据存 `data_dir/`，可迁移，可 Git 版本控制**
3. **监听类数据默认关闭，用户显式开启**
4. **新增数据源 = 新增 Collector + 新增 Tool**，架构线性可扩展
5. **报告是 Agent 的自主分析，不是模板填空**
6. **人物数据仅存本地，AI 判断标注来源**
