# Huaqi 系统架构总结

## 一、系统概述

**Huaqi (花旗)** 是一个个人 AI 同伴系统，核心理念是"不是使用 AI，而是养育 AI"。通过长期对话积累对用户的理解，AI 会逐渐成长为真正懂你的数字伙伴，而非简单的工具。

### 1.1 核心定位

| 维度 | 说明 |
|------|------|
| **产品愿景** | 让 AI 成为用户的长期数字伙伴，随交互而成长 |
| **目标用户** | 追求自我成长的个人、内容创作者、需要情感陪伴的用户 |
| **核心价值** | 长期陪伴、成长辅助、内容创作三大价值 |
| **隐私理念** | 本地优先存储，用户完全控制数据 |

### 1.2 技术特色

- **Agent 架构**: 基于 LangGraph 状态图构建，支持人机协同和持久化
- **混合检索**: BM25 + 向量语义检索，兼容所有 LLM（无需强制 Embedding）
- **本地存储**: Markdown + YAML 格式，Git 友好，人类可读
- **可扩展性**: 插件化设计，支持多平台适配器、多数据源、多 LLM 提供商

---

## 二、系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户接口层                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                    │
│  │  CLI (Typer) │  │  Web (待定)  │  │  API (待定)  │                    │
│  └──────────────┘  └──────────────┘  └──────────────┘                    │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────────────┐
│                        编排层                          │
│  ┌───────────────────────────────────────────────────────────────────┐   │
│  │                  LangGraph Agent (StateGraph)                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐             │   │
│  │  │  Chat    │ │  Diary   │ │ Content  │ │ Insight  │             │   │
│  │  │  Node    │ │  Node    │ │  Node    │ │  Node    │             │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘             │   │
│  └───────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                    │
│  │ APScheduler  │  │  Pipeline    │  │    Hooks     │                    │
│  │ (定时任务)    │  │  Orchestrator│  │   System     │                    │
│  └──────────────┘  └──────────────┘  └──────────────┘                    │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────────────┐
│                           领域层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Personality  │  │   Growth     │  │    Diary     │  │   Memory     │   │
│  │   Engine     │  │   Tracker    │  │    Store     │  │   Manager    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                    │
│  │   Schema     │  │   Analysis   │  │   Flexible   │                    │
│  │   Registry   │  │    Engine    │  │    Store     │                    │
│  └──────────────┘  └──────────────┘  └──────────────┘                    │
└─────────────────────────────────────────────────────────────────────────┘
                                  │
┌─────────────────────────────────────────────────────────────────────────┐
│                       基础设施层                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   Markdown   │  │   Chroma     │  │    BM25      │  │     Git      │   │
│  │    Store     │  │  Vector DB   │  │   Search     │  │    Sync      │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                    │
│  │     LLM      │  │   Embedder   │  │   Config     │                    │
│  │   Provider   │  │   Service    │  │   Manager     │                    │
│  └──────────────┘  └──────────────┘  └──────────────┘                    │
└─────────────────────────────────────────────────────────────────────────┘
```

### 2.2 架构分层说明

| 层次 | 职责 | 关键技术 |
|------|------|---------|
| **用户接口层** | 与用户的交互界面 | Typer, Rich, Prompt Toolkit |
| **编排层** | 流程编排、任务调度、事件驱动 | LangGraph, APScheduler |
| **领域层** | 核心业务逻辑 | Pydantic, YAML, 自定义算法 |
| **基础设施层** | 存储检索、模型调用、数据同步 | Chroma, BM25, GitPython |

---

## 三、核心模块说明

### 3.1 Agent 系统 (`huaqi_src/agent/`)

基于 LangGraph 的状态机驱动 Agent 架构。

#### 核心组件

| 组件 | 文件 | 说明 |
|------|------|------|
| **StateGraph** | `graph/chat.py` | 对话工作流状态图 |
| **AgentState** | `state.py` | 统一状态定义，支持消息累积 |
| **Chat Nodes** | `nodes/chat_nodes.py` | 对话节点实现 |

#### 状态定义

```python
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]  # 对话历史
    user_id: str                                          # 用户ID
    personality_context: Optional[str]                    # 人格画像
    recent_memories: Optional[List[str]]                  # 相关记忆
    intent: Optional[str]                                 # 意图识别
    workflow_data: Dict[str, Any]                         # 工作流数据
    interrupt_requested: bool                             # 人机协同标志
    response: Optional[str]                               # 最终回复
```

#### 工作流示例

```
用户输入 → intent_classifier → context_builder → chat_response → save_conversation → END
```

### 3.2 记忆系统 (`huaqi_src/memory/`)

#### 三层记忆架构

| 层次 | 存储 | 用途 | 特点 |
|------|------|------|------|
| **Session Memory** | 内存 | 当前会话上下文 | 临时、快速 |
| **Working Memory** | YAML | 近期重要信息 | 可编辑、结构化 |
| **Long-term Memory** | Markdown + Chroma | 长期历史记录 | 持久化、可检索 |

#### 混合检索引擎

```python
class HybridSearch:
    """
    融合策略:
    - BM25: 精确匹配关键词 (30%)
    - 向量相似度: 语义匹配 (60%)
    - 时间衰减: 近期内容加权 (10%)
    """
    
    def search(self, query: str, top_k: int = 5):
        # 1. 向量检索
        vector_results = self.chroma.search(query, top_k * 2)
        
        # 2. BM25 检索
        bm25_results = self.bm25.get_scores(tokenize(query))
        
        # 3. 融合分数
        final_score = (
            0.7 * vector_score + 
            0.3 * bm25_normalized + 
            0.1 * recency_score
        )
```

**设计亮点**：
- 无需强制 Embedding，可仅用 BM25 + LLM 实现
- 时间衰减确保近期内容优先
- 支持按类型过滤

### 3.3 个性引擎 (`huaqi_src/core/personality_simple.py`)

#### 五维人格模型

| 维度 | 说明 | 默认值 |
|------|------|--------|
| **Openness** | 开放性 | 0.5 |
| **Conscientiousness** | 尽责性 | 0.7 |
| **Extraversion** | 外向性 | 0.3 |
| **Agreeableness** | 宜人性 | 0.8 |
| **Neuroticism** | 神经质 | -0.3 |

#### 预设模式

- `companion`: 同伴模式（温暖、高共情）
- `mentor`: 导师模式（专业、挑战性）
- `friend`: 朋友模式（活泼、幽默）
- `assistant`: 助手模式（正式、高效）

#### 提示词生成

```python
def to_prompt(self) -> str:
    """将人格配置转换为系统提示词"""
    return f"""你是 {self.name}，用户的个人 AI {self.role}。

沟通风格: {self.tone}
正式程度: {self.formality}
共情水平: {self.empathy}

价值观:
- 成长优于稳定
- 真诚优于讨好
- 引导优于指令
"""
```

### 3.4 成长系统 (`huaqi_src/core/growth_simple.py`)

#### 技能管理

```python
@dataclass
class Skill:
    name: str              # 技能名称
    category: str          # 分类
    current_level: str     # 当前水平
    target_level: str      # 目标水平
    total_hours: float     # 累计时长
    last_practice: str     # 最后练习时间
```

#### 目标管理

```python
@dataclass
class Goal:
    id: str                # 目标ID
    title: str             # 标题
    status: str            # active/completed
    progress: int          # 进度 0-100
    created_at: str        # 创建时间
```

### 3.5 内容流水线 (`huaqi_src/pipeline/`)

#### 流水线架构

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Sources    │ -> │  Processors  │ -> │   Platforms  │ -> │   Publish    │
│  (数据采集)   │    │  (内容处理)   │    │  (平台适配)   │    │  (发布/草稿)  │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

#### 已实现组件

| 类型 | 组件 | 说明 |
|------|------|------|
| **Sources** | XMockSource, RSSMockSource | Twitter/X、RSS 数据源 |
| **Processors** | Summarizer, Translator, XiaoHongShuFormatter | 摘要、翻译、格式化 |
| **Platforms** | XiaoHongShuPublisher | 小红书发布（草稿模式） |

#### 使用示例

```python
pipeline = (PipelineBuilder()
    .add_x_source(mock=True)
    .add_rss_source(mock=True)
    .add_summarizer(max_length=500)
    .add_xiaohongshu_formatter()
    .set_xiaohongshu_publisher(draft_dir="~/.huaqi/drafts")
    .build())

await pipeline.run(dry_run=True)  # 预览模式
```

### 3.6 调度器 (`huaqi_src/scheduler/`)

#### APScheduler 封装

```python
class SchedulerManager:
    """
    功能:
    - 支持 cron/interval/date 三种触发器
    - 任务持久化到 SQLite
    - 任务执行事件监听
    """
    
    def add_cron_job(self, job_id: str, func: Callable, cron: str):
        """添加定时任务，如每天早上8点问候"""
        trigger = CronTrigger.from_crontab("0 8 * * *")
        self.scheduler.add_job(func, trigger, id=job_id)
```

#### 内置任务

- `morning_greeting`: 每日晨间问候
- `daily_summary`: 每日总结生成
- `content_pipeline`: 定时内容抓取

### 3.7 Schema 系统 (`huaqi_src/core/schema.py`)

#### 动态维度定义

```python
class DimensionSchema:
    """维度 Schema 定义"""
    dimension_id: str           # 维度ID
    dimension_name: str         # 维度名称
    dimension_type: DimensionType  # 类型
    allowed_values: List[str]   # 允许值
    extraction_prompt: str      # LLM 提取提示
    priority: int               # 优先级 1-10
```

#### 维度类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `CATEGORY` | 枚举值 | 主导情绪 |
| `SCORE` | 0-1 分数 | 分享倾向 |
| `SCALE` | 1-10 量表 | 情绪强度 |
| `TEXT` | 文本描述 | 深层意图 |
| `LIST` | 列表 | 话题列表 |
| `JSON` | 任意 JSON | 立场数据 |

#### 内置维度

- **情绪维度**: `emotion.primary`, `emotion.intensity`
- **意图维度**: `intent.surface`, `intent.deep`
- **话题维度**: `topics`, `stances`, `facts`
- **内容偏好**: `content.topic_interest`, `content.depth_preference`

---

## 四、功能特性列表

### 4.1 核心功能（已实现）

| 功能模块 | 状态 | 说明 |
|----------|------|------|
| 💬 **智能对话** | ✅ 完成 | 基于 LangGraph 的状态驱动对话 |
| 📝 **日记系统** | ✅ 完成 | Markdown 格式，支持批量导入 |
| 🎯 **技能追踪** | ✅ 完成 | 记录练习时间，追踪成长进度 |
| 🎖️ **目标管理** | ✅ 完成 | 设定目标，可视化进展 |
| 🧠 **记忆系统** | ✅ 完成 | 三层记忆，混合检索 |
| 🎭 **人格引擎** | ✅ 完成 | 可定制 AI 性格、语气 |
| 🔗 **内容流水线** | ✅ 完成 | X/RSS → 摘要 → 小红书文案 |
| ⏰ **定时任务** | ✅ 完成 | APScheduler 支持定时触发 |
| 🔒 **Git 同步** | ✅ 完成 | 数据版本控制 |
| 🔥 **配置热重载** | ✅ 完成 | Daemon 无需重启 |

### 4.2 扩展功能（规划中）

| 功能模块 | 优先级 | 说明 |
|----------|--------|------|
| 语音日记 | P1 | Whisper 转录 |
| 图片剪藏 | P1 | OCR 提取 + 自动描述 |
| 多平台发布 | P2 | 微博、即刻、知乎等 |
| Web 界面 | P2 | 脱离 CLI 的图形界面 |
| 移动端 | P3 | PWA 或原生 App |

### 4.3 CLI 命令一览

```bash
# 对话
huaqi chat                    # 开始对话

# 日记
huaqi diary                   # 写日记
huaqi diary list              # 查看日记
huaqi diary import <path>     # 导入 Markdown 日记

# 技能与目标
huaqi skill add "Python"      # 添加技能
huaqi skill log Python 2.5    # 记录练习时间
huaqi goal add "学习 LangGraph"  # 添加目标

# 内容流水线
huaqi pipeline add-source     # 添加内容源
huaqi pipeline fetch          # 手动抓取内容

# 配置
huaqi config set-data-dir <path>  # 设置数据目录
huaqi config set-llm              # 配置 LLM
huaqi config migrate              # 数据迁移

# 任务恢复
huaqi resume <task_id>        # 恢复中断的任务
```

---

## 五、架构设计亮点

### 5.1 LangGraph 状态驱动架构

**传统方式**：
```python
# 命令式流程控制
def chat(user_input):
    intent = classify(user_input)
    if intent == "chat":
        return generate_response(user_input)
    elif intent == "diary":
        return handle_diary(user_input)
```

**LangGraph 方式**：
```python
# 状态图驱动
workflow = StateGraph(AgentState)
workflow.add_node("intent_classifier", classify_intent)
workflow.add_node("chat_response", generate_response)
workflow.add_conditional_edges("intent_classifier", route_by_intent)
```

**优势**：
- ✅ 状态持久化，支持中断恢复
- ✅ 流程可视化，易于调试
- ✅ 人机协同，interrupt 机制
- ✅ 易于扩展新节点

### 5.2 无需 Embedding 的混合检索

**传统方案**：
```
必须使用 Embedding → Chroma 向量检索 → 依赖特定模型
```

**Huaqi 方案**：
```
BM25 文本检索 → 候选集 → LLM 相关性判断 → 结果
```

**优势**：
- ✅ 兼容所有 LLM（包括不提供 Embedding 的）
- ✅ 本地优先，零依赖外部服务
- ✅ 可选向量检索，按需启用

### 5.3 人类可读的数据格式

**数据存储**：
```
~/.huaqi/
├── memory/
│   ├── diary/              # Markdown 日记
│   ├── conversations/      # 对话历史
│   ├── personality.yaml    # 人格配置
│   └── growth.yaml         # 成长数据
├── drafts/                 # 内容草稿
└── config.yaml             # 全局配置
```

**优势**：
- ✅ 直接编辑，无需工具
- ✅ Git 版本控制友好
- ✅ Obsidian 兼容，与知识库互通
- ✅ 避免数据库锁定

### 5.4 插件化架构设计

#### 平台适配器模式

```python
class BasePlatformAdapter(ABC):
    @abstractmethod
    async def publish(self, content: PlatformContent) -> PublishResult:
        pass

# 实现
class XiaoHongShuAdapter(BasePlatformAdapter):
    async def publish(self, content):
        # 生成草稿，用户扫码确认
        pass
```

#### 数据源适配器模式

```python
class BaseDataSourceAdapter(ABC):
    @abstractmethod
    async def fetch_latest(self, query: str, limit: int) -> List[RawContent]:
        pass
```

**优势**：
- ✅ 易于扩展新平台/数据源
- ✅ 遵循开闭原则
- ✅ 测试友好

### 5.5 配置热重载

```python
class ConfigReloader(FileSystemEventHandler):
    """监听配置文件变更，Daemon 无需重启"""
    
    def on_modified(self, event):
        if event.src_path == self.config_path:
            asyncio.create_task(self._reload())
```

**优势**：
- ✅ 修改配置即时生效
- ✅ 无需重启服务
- ✅ 支持多模块协同更新

### 5.6 单用户架构（已简化）

```python
# 简化设计，单用户模式
def get_data_dir() -> Path:
    """获取数据目录，必须用户指定"""
    if env_dir := os.getenv("HUAQI_DATA_DIR"):
        return Path(env_dir).expanduser().resolve()
    
    # 返回 None 表示未配置，CLI 会报错
    return None

# 存储路径
~/.huaqi/memory/insights/   # 旧的 user_id 子目录已移除
```

**优势**：
- ✅ 简化代码逻辑
- ✅ 减少维护成本
- ✅ 符合个人使用场景

---

## 六、数据流与关键流程

### 6.1 对话流程

```
用户输入
    ↓
意图识别
    ↓
┌──────────────┐
│ 构建上下文    │ ←── 人格画像 + 近期记忆
└──────────────┘
    ↓
LLM 生成回复
    ↓
┌──────────────┐
│ 后处理       │ ←── 提取记忆、更新画像
└──────────────┘
    ↓
保存对话历史
    ↓
返回响应
```

### 6.2 内容流水线流程

```
定时触发 / 手动触发
    ↓
┌──────────────┐
│ Fetch        │ ←── X/RSS 源抓取
└──────────────┘
    ↓
┌──────────────┐
│ Quality Check│ ←── 过滤低质量内容
└──────────────┘
    ↓
┌──────────────┐
│ Summarize    │ ←── AI 生成摘要
└──────────────┘
    ↓
┌──────────────┐
│ Generate     │ ←── 生成平台文案
└──────────────┘
    ↓
┌──────────────┐
│ Interrupt    │ ←── 人机协同（用户确认）
└──────────────┘
    ↓
┌──────────────┐
│ Publish      │ ←── 发布或保存草稿
└──────────────┘
```

### 6.3 人格更新流程

```
日记写入 / 对话结束
    ↓
触发分析
    ↓
提取关键信息
    ↓
┌──────────────┐
│ 画像冲突检测  │
└──────────────┘
    ↓
    ├──→ 无冲突 → 增量更新
    │
    └──→ 有冲突 → 人机确认 → 用户选择版本
    ↓
保存新版本
    ↓
Git Commit
```

---

## 七、技术栈总结

| 类别 | 技术 | 版本 | 用途 |
|------|------|------|------|
| **语言** | Python | 3.9+ | 主要开发语言 |
| **CLI** | Typer | ≥0.12 | 命令行框架 |
| **UI** | Rich, Prompt Toolkit | ≥13.0, ≥3.0 | 终端美化、交互 |
| **Agent** | LangGraph | ≥0.2.0 | 状态驱动 Agent |
| **LLM** | LangChain, OpenAI | ≥0.3.0 | 模型抽象层 |
| **调度** | APScheduler | ≥4.0 | 定时任务 |
| **向量** | Chroma | ≥0.5.0 | 向量数据库 |
| **搜索** | rank-bm25 | ≥0.2.0 | BM25 检索 |
| **数据** | Pydantic, YAML | ≥2.0, ≥6.0 | 数据验证、配置 |
| **同步** | GitPython | ≥3.1.0 | Git 操作 |
| **日志** | structlog | ≥24.0 | 结构化日志 |
| **监控** | watchdog | ≥4.0 | 文件监听 |

---

## 八、项目路线图

### 8.1 当前状态

| Phase | 功能 | 状态 |
|-------|------|------|
| P1 | 基础对话系统 | ✅ 完成 |
| P2 | 记忆系统 (日记 + 对话历史) | ✅ 完成 |
| P3 | 技能追踪与目标管理 | ✅ 完成 |
| P4 | APScheduler 定时任务 | ✅ 完成 |
| P5 | 内容流水线 (X/RSS → 小红书) | ✅ 完成 |
| P6 | 人机协同中断恢复 | ✅ 完成 |
| P7 | 数据隔离与用户管理 | ✅ 完成 (已简化为单用户) |
| P8 | 配置热重载与数据迁移 | ✅ 完成 |

### 8.2 未来规划

| Phase | 功能 | 预计时间 |
|-------|------|----------|
| P9 | 语音日记 | 待定 |
| P10 | 图片剪藏 | 待定 |
| P11 | 多平台发布 | 待定 |
| P12 | Web 界面 | 待定 |
| P13 | 移动端 | 待定 |

---

## 九、关键文件索引

| 文件路径 | 作用 | 重要程度 |
|----------|------|----------|
| `cli.py` | CLI 入口，命令定义 | ⭐⭐⭐⭐⭐ |
| `huaqi_src/agent/graph/chat.py` | 对话工作流 | ⭐⭐⭐⭐⭐ |
| `huaqi_src/agent/state.py` | 状态定义 | ⭐⭐⭐⭐⭐ |
| `huaqi_src/agent/nodes/chat_nodes.py` | 对话节点 | ⭐⭐⭐⭐ |
| `huaqi_src/core/personality_simple.py` | 人格引擎 | ⭐⭐⭐⭐ |
| `huaqi_src/core/growth_simple.py` | 成长系统 | ⭐⭐⭐⭐ |
| `huaqi_src/core/schema.py` | Schema 系统 | ⭐⭐⭐⭐ |
| `huaqi_src/core/adaptive_understanding.py` | 自适应理解 | ⭐⭐⭐⭐ |
| `huaqi_src/memory/vector/hybrid_search.py` | 混合检索 | ⭐⭐⭐⭐⭐ |
| `huaqi_src/pipeline/core.py` | 内容流水线 | ⭐⭐⭐⭐ |
| `huaqi_src/scheduler/manager.py` | 定时任务 | ⭐⭐⭐⭐ |
| `docs/PRD.md` | 产品需求文档 | ⭐⭐⭐ |
| `docs/TECH_SPEC.md` | 技术规范 | ⭐⭐⭐⭐ |
| `docs/ARCHITECTURE.md` | 架构说明 | ⭐⭐⭐⭐ |

---

## 十、总结

Huaqi 是一个架构清晰、设计优雅的个人 AI 同伴系统。其核心设计理念包括：

1. **状态驱动架构**：LangGraph 提供的状态机模式，让对话流程可控、可持久化
2. **混合检索策略**：BM25 + 向量检索结合，兼容性强、效果优秀
3. **人类可读存储**：Markdown + YAML 格式，Git 友好，避免数据库锁定
4. **插件化设计**：适配器模式支持多平台、多数据源扩展
5. **隐私优先**：本地存储、用户控制、可选同步
6. **简化单用户**：移除多用户复杂度，专注个人使用场景

这些设计使 Huaqi 不仅能作为工具使用，更能作为长期陪伴用户的数字伙伴，随着交互而成长，真正实现"养育 AI"的理念。

---

**文档版本**: v1.1  
**生成时间**: 2026-03-28  
**更新说明**: 已更新为单用户版本架构
