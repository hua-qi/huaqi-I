# Huaqi Code Agent - 技术方案文档

## 1. 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 关联 PRD | PRD.md |

---

## 2. 技术选型

### 2.1 核心技术栈

| 层次 | 技术 | 版本要求 | 选型理由 |
|------|------|---------|---------|
| **Agent 框架** | LangGraph | ≥0.2.0 | 状态驱动、人机协同、持久化 |
| **LLM 接口** | LangChain | ≥0.3.0 | 模型无关、生态丰富 |
| **定时任务** | APScheduler | ≥4.0 | 简单可靠、持久化支持 |
| **向量存储** | Chroma | ≥0.5.0 | 本地优先、零配置 |
| **CLI 框架** | Typer | ≥0.12 | 类型安全、自动生成帮助 |
| **数据处理** | Pydantic | ≥2.0 | 类型安全、序列化 |
| **异步** | asyncio | 内置 | Python 原生异步 |
| **日志** | structlog | ≥24.0 | 结构化日志 |

### 2.2 目录结构

```
/Users/lianzimeng/workspace/huaqi/
├── huaqi/                          # 主包
│   ├── __init__.py
│   ├── cli.py                      # CLI 入口（简化）
│   ├── daemon.py                   # 常驻服务入口
│   ├── config/
│   │   ├── __init__.py
│   │   ├── models.py               # Pydantic 配置模型
│   │   └── manager.py              # 配置加载/保存
│   │
│   ├── core/                       # 领域核心（保留并增强）
│   │   ├── personality/
│   │   │   ├── __init__.py
│   │   │   ├── models.py           # PersonalityProfile
│   │   │   ├── engine.py           # PersonalityEngine
│   │   │   └── updater.py          # 自动更新逻辑
│   │   │
│   │   ├── growth/
│   │   │   ├── __init__.py
│   │   │   ├── models.py           # Skill, Goal, Habit
│   │   │   └── tracker.py          # GrowthTracker
│   │   │
│   │   └── diary/
│   │       ├── __init__.py
│   │       ├── models.py           # DiaryEntry
│   │       ├── store.py            # DiaryStore
│   │       └── search.py           # 日记搜索（混合）
│   │
│   ├── memory/                     # 记忆系统（增强）
│   │   ├── __init__.py
│   │   ├── vector/
│   │   │   ├── __init__.py
│   │   │   ├── client.py           # Chroma 封装
│   │   │   ├── embedder.py         # Embedding 服务
│   │   │   └── hybrid_search.py    # BM25 + 向量混合
│   │   │
│   │   ├── storage/
│   │   │   ├── __init__.py
│   │   │   └── markdown.py         # Markdown 存储（保留）
│   │   │
│   │   └── processors/             # 扩展：多媒体处理
│   │       ├── __init__.py
│   │       ├── base.py             # BaseMemoryProcessor
│   │       └── text.py             # 文本处理器
│   │
│   ├── agent/                      # LangGraph Agent（新增）
│   │   ├── __init__.py
│   │   ├── graph/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py             # 对话 workflow
│   │   │   ├── content.py          # 内容流水线
│   │   │   └── insight.py          # 洞察生成 workflow
│   │   │
│   │   ├── nodes/
│   │   │   ├── __init__.py
│   │   │   ├── chat_nodes.py       # 对话相关节点
│   │   │   ├── diary_nodes.py      # 日记相关节点
│   │   │   ├── content_nodes.py    # 内容处理节点
│   │   │   └── tools.py            # Agent 工具集
│   │   │
│   │   ├── state.py                # AgentState 定义
│   │   └── runner.py               # Agent 运行器封装
│   │
│   ├── scheduler/                  # 定时任务（新增）
│   │   ├── __init__.py
│   │   ├── manager.py              # APScheduler 封装
│   │   ├── triggers.py             # 触发器定义
│   │   └── handlers.py             # 任务处理器
│   │
│   ├── pipeline/                   # 内容流水线（新增）
│   │   ├── __init__.py
│   │   ├── base.py                 # 流水线抽象
│   │   ├── orchestrator.py         # 流程编排
│   │   │
│   │   ├── sources/                # 数据源适配器
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # BaseDataSourceAdapter
│   │   │   ├── twitter.py          # X/Twitter 适配器
│   │   │   ├── rss.py              # RSS 适配器
│   │   │   └── hackernews.py       # HN 适配器
│   │   │
│   │   ├── platforms/              # 发布平台适配器
│   │   │   ├── __init__.py
│   │   │   ├── base.py             # BasePlatformAdapter
│   │   │   └── xiaohongshu.py      # 小红书适配器
│   │   │
│   │   └── processors/             # 内容处理器
│   │       ├── __init__.py
│   │       ├── summarizer.py       # 总结生成
│   │       └── generator.py        # 文案生成
│   │
│   ├── llm/                        # LLM 抽象层（保留）
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseLLMProvider
│   │   ├── factory.py              # 工厂模式创建
│   │   └── providers/
│   │       ├── __init__.py
│   │       ├── openai.py           # OpenAI 兼容（含 kimi）
│   │       └── local.py            # Ollama 本地模型
│   │
│   ├── sync/                       # Git 同步（保留）
│   │   ├── __init__.py
│   │   └── git_manager.py
│   │
│   └── utils/                      # 工具函数
│       ├── __init__.py
│       ├── logging.py              # 日志配置
│       └── exceptions.py           # 自定义异常
│
├── tests/                          # 测试
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
├── docs/                           # 文档
│   ├── PRD.md                      # 产品需求
│   ├── TECH_SPEC.md                # 本文件
│   ├── ARCHITECTURE.md             # 架构说明
│   └── API.md                      # 接口文档
│
├── scripts/                        # 脚本工具
│   ├── setup.sh                    # 安装脚本
│   └── migrate.sh                  # 数据迁移
│
├── pyproject.toml                  # 项目配置
├── requirements.txt                # 依赖（开发用）
└── README.md                       # 项目说明
```

---

## 3. 核心模块详细设计

### 3.1 Agent State 设计

```python
# huaqi/agent/state.py
from typing import Annotated, TypedDict, Optional, List
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage

class AgentState(TypedDict):
    """LangGraph 状态定义 - 所有 workflow 共享的基础状态"""
    
    # 基础对话
    messages: Annotated[List[BaseMessage], add_messages]
    
    # 用户上下文
    user_id: str
    personality_context: str          # 人格画像 prompt 片段
    recent_memories: List[str]        # 相关记忆片段
    
    # 意图与路由
    intent: Optional[str]             # chat / diary / content / skill
    intent_confidence: float
    
    # 工作流特定数据（动态）
    workflow_data: dict               # 各节点传递的数据
    
    # 人机协同
    interrupt_requested: bool
    interrupt_reason: Optional[str]
    interrupt_data: Optional[dict]    # 等待用户处理的数据
    
    # 错误与重试
    error: Optional[str]
    retry_count: int


class ContentPipelineState(AgentState):
    """内容流水线专用状态"""
    source_contents: List[RawContent]     # 抓取的内容
    selected_content: Optional[RawContent]
    summary: Optional[str]
    generated_posts: dict                 # {platform: content}
    user_modified_posts: Optional[dict]   # 用户修改后的
    publish_results: List[PublishResult]


class DiaryWorkflowState(AgentState):
    """日记工作流状态"""
    diary_date: Optional[str]
    diary_content: Optional[str]
    diary_mood: Optional[str]
    diary_tags: List[str]
    extracted_insights: Optional[dict]    # AI 提取的洞察
    personality_updates: Optional[dict]   # 画像更新建议
```

### 3.2 Chat Workflow 图结构

```python
# huaqi/agent/graph/chat.py
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from huaqi.agent.state import AgentState
from huaqi.agent.nodes import chat_nodes, diary_nodes, tools

def build_chat_graph():
    """构建对话 workflow 图"""
    
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("intent_classifier", chat_nodes.classify_intent)
    workflow.add_node("context_builder", chat_nodes.build_context)
    workflow.add_node("chat_response", chat_nodes.generate_response)
    workflow.add_node("diary_handler", diary_nodes.handle_diary_command)
    workflow.add_node("skill_handler", chat_nodes.handle_skill_command)
    workflow.add_node("memory_retriever", chat_nodes.retrieve_memories)
    workflow.add_node("save_conversation", chat_nodes.save_conversation)
    
    # 设置入口
    workflow.set_entry_point("intent_classifier")
    
    # 条件边：根据意图路由
    workflow.add_conditional_edges(
        "intent_classifier",
        lambda state: state["intent"],
        {
            "chat": "context_builder",
            "diary": "diary_handler",
            "skill": "skill_handler",
            "unknown": "context_builder"
        }
    )
    
    # 正常对话流程
    workflow.add_edge("context_builder", "memory_retriever")
    workflow.add_edge("memory_retriever", "chat_response")
    workflow.add_edge("chat_response", "save_conversation")
    workflow.add_edge("save_conversation", END)
    
    # 命令处理流程
    workflow.add_edge("diary_handler", "save_conversation")
    workflow.add_edge("skill_handler", "save_conversation")
    
    # 编译（启用持久化）
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)
```

### 3.3 Content Pipeline Workflow

```python
# huaqi/agent/graph/content.py
from langgraph.graph import StateGraph
from langgraph.types import interrupt
from huaqi.agent.state import ContentPipelineState
from huaqi.pipeline import sources, platforms

def build_content_pipeline():
    """内容流水线 workflow"""
    
    workflow = StateGraph(ContentPipelineState)
    
    # 节点定义
    workflow.add_node("fetch_content", content_nodes.fetch_from_sources)
    workflow.add_node("quality_check", content_nodes.check_quality)
    workflow.add_node("summarize", content_nodes.summarize_content)
    workflow.add_node("generate_posts", content_nodes.generate_platform_posts)
    workflow.add_node("human_review", content_nodes.request_human_review)  # Interrupt
    workflow.add_node("publish", content_nodes.publish_to_platforms)
    workflow.add_node("record_result", content_nodes.record_publish_result)
    
    # 流程
    workflow.set_entry_point("fetch_content")
    workflow.add_edge("fetch_content", "quality_check")
    
    # 质量检查条件分支
    workflow.add_conditional_edges(
        "quality_check",
        lambda state: "pass" if state["selected_content"] else "fail",
        {
            "pass": "summarize",
            "fail": END
        }
    )
    
    workflow.add_edge("summarize", "generate_posts")
    workflow.add_edge("generate_posts", "human_review")
    
    # 人机协同 - 等待用户确认
    workflow.add_edge("human_review", "publish")
    workflow.add_edge("publish", "record_result")
    workflow.add_edge("record_result", END)
    
    return workflow.compile()


# 节点实现示例
async def request_human_review(state: ContentPipelineState):
    """人机协同节点 - 请求用户确认"""
    
    # 生成预览页面或二维码
    preview_data = {
        "task_id": state.get("task_id"),
        "generated_posts": state["generated_posts"],
        "source_summary": state["summary"],
    }
    
    # LangGraph interrupt - 暂停等待用户输入
    user_decision = interrupt({
        "type": "content_review",
        "message": "请审核生成的内容",
        "preview_url": generate_preview_url(preview_data),
        "qr_code": generate_qr_code(preview_data),
        "actions": ["confirm", "edit", "reject"]
    })
    
    # 用户通过 CLI 命令恢复后，处理结果
    if user_decision["action"] == "confirm":
        return state
    elif user_decision["action"] == "edit":
        state["user_modified_posts"] = user_decision["modified_posts"]
        return state
    else:  # reject
        return {"error": "User rejected", "__end__": True}
```

### 3.4 定时任务与 Agent 集成

```python
# huaqi/scheduler/manager.py
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.cron import CronTrigger

class SchedulerManager:
    """定时任务管理器"""
    
    def __init__(self, db_path: str = "~/.huaqi/scheduler.db"):
        jobstores = {
            'default': SQLAlchemyJobStore(url=f'sqlite:///{db_path}')
        }
        self.scheduler = AsyncIOScheduler(jobstores=jobstores)
        self.agent_runner = AgentRunner()  # 封装 Agent 执行
    
    def register_default_jobs(self, config: dict):
        """从配置注册默认任务"""
        for job_config in config.get("jobs", []):
            self.add_job(
                job_id=job_config["id"],
                task_name=job_config["task"],
                cron=job_config["cron"],
                kwargs=job_config.get("params", {})
            )
    
    def add_job(self, job_id: str, task_name: str, cron: str, kwargs: dict = None):
        """添加定时任务"""
        trigger = CronTrigger.from_crontab(cron)
        
        self.scheduler.add_job(
            func=self._execute_agent_task,
            trigger=trigger,
            id=job_id,
            kwargs={
                "task_name": task_name,
                "task_kwargs": kwargs or {}
            },
            replace_existing=True
        )
    
    async def _execute_agent_task(self, task_name: str, task_kwargs: dict):
        """执行 Agent 任务"""
        # 根据任务类型选择 workflow
        if task_name == "generate_morning_greeting":
            result = await self.agent_runner.run_chat_workflow(
                intent="chat",
                system_override="生成晨间问候，基于今日日程和近期日记"
            )
        elif task_name == "content_pipeline":
            result = await self.agent_runner.run_content_pipeline(
                sources=task_kwargs.get("sources", [])
            )
        elif task_name == "personality_update":
            result = await self.agent_runner.run_insight_workflow(
                workflow_type="personality_update"
            )
        
        # 记录执行结果
        await self._record_execution(task_name, result)
    
    def start(self):
        self.scheduler.start()
    
    def shutdown(self):
        self.scheduler.shutdown()
```

### 3.5 向量检索实现

```python
# huaqi/memory/vector/hybrid_search.py
import chromadb
from chromadb.utils import embedding_functions
import bm25s
import numpy as np
from typing import List

class HybridSearch:
    """BM25 + 向量混合检索"""
    
    def __init__(
        self,
        chroma_path: str,
        embedding_model: str = "BAAI/bge-small-zh",
        alpha: float = 0.7  # 向量权重
    ):
        self.alpha = alpha
        
        # Chroma 客户端
        self.client = chromadb.PersistentClient(path=chroma_path)
        
        # Embedding 函数
        self.embed_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=embedding_model
        )
        
        # 获取或创建集合
        self.collection = self.client.get_or_create_collection(
            name="memories",
            embedding_function=self.embed_fn
        )
    
    async def add(
        self,
        doc_id: str,
        content: str,
        metadata: dict,
        doc_type: str = "diary"  # diary | conversation | external
    ):
        """添加文档到索引"""
        self.collection.add(
            ids=[doc_id],
            documents=[content],
            metadatas=[{**metadata, "type": doc_type}]
        )
    
    async def search(
        self,
        query: str,
        top_k: int = 5,
        doc_type: str = None,
        recency_weight: float = 0.1
    ) -> List[dict]:
        """
        混合检索：向量相似度 + BM25 关键词 + 时间衰减
        """
        # 1. 向量检索
        vector_results = self.collection.query(
            query_texts=[query],
            n_results=top_k * 2,  # 召回更多，后续重排
            where={"type": doc_type} if doc_type else None
        )
        
        # 2. 计算 BM25 分数（如果数据量大，可用单独的 BM25 索引）
        # 简化：使用 Chroma 的 full-text search（如果启用）
        
        # 3. 融合分数
        final_scores = {}
        
        for i, doc_id in enumerate(vector_results["ids"][0]):
            vector_score = vector_results["distances"][0][i]
            # 距离转相似度（余弦距离）
            vector_sim = 1 - vector_score
            
            # 时间衰减因子
            metadata = vector_results["metadatas"][0][i]
            age_days = self._calculate_age(metadata.get("created_at"))
            recency_factor = np.exp(-recency_weight * age_days)
            
            # 融合分数
            final_score = self.alpha * vector_sim + (1 - self.alpha) * recency_factor
            final_scores[doc_id] = {
                "score": final_score,
                "content": vector_results["documents"][0][i],
                "metadata": metadata
            }
        
        # 4. 排序返回
        sorted_results = sorted(
            final_scores.items(),
            key=lambda x: x[1]["score"],
            reverse=True
        )[:top_k]
        
        return [{"id": rid, **data} for rid, data in sorted_results]
    
    def _calculate_age(self, created_at: str) -> float:
        from datetime import datetime
        created = datetime.fromisoformat(created_at)
        return (datetime.now() - created).days
```

### 3.6 人格画像更新

```python
# huaqi/core/personality/updater.py
from datetime import datetime, timedelta
from typing import Optional

class PersonalityUpdater:
    """人格画像自动更新器"""
    
    def __init__(
        self,
        llm_provider,
        confirmation_threshold: str = "medium",
        auto_update: bool = True
    ):
        self.llm = llm_provider
        self.threshold = confirmation_threshold
        self.auto_update = auto_update
    
    async def analyze_diary_for_updates(
        self,
        diary_entry: DiaryEntry,
        current_profile: PersonalityProfile
    ) -> Optional[PersonalityUpdate]:
        """分析日记，检测画像是否需要更新"""
        
        prompt = f"""
        基于以下日记内容，分析用户的人格特征变化：
        
        当前画像：
        {current_profile.to_prompt()}
        
        新日记：
        {diary_entry.content}
        
        请分析：
        1. 是否有新的人格特征显现？
        2. 现有特征是否有显著变化？
        3. 变化的重要性（低/中/高）
        
        输出格式：
        ```json
        {{
            "has_changes": true/false,
            "changes": [
                {{
                    "trait": "特征名",
                    "old_value": "原值",
                    "new_value": "新值",
                    "confidence": 0.8,
                    "importance": "medium"
                }}
            ],
            "reasoning": "分析理由"
        }}
        ```
        """
        
        response = await self.llm.chat([{"role": "user", "content": prompt}])
        analysis = parse_json_response(response)
        
        if not analysis["has_changes"]:
            return None
        
        # 根据重要性决定是否需人工确认
        needs_confirmation = any(
            c["importance"] in ["high"] or 
            (c["importance"] == "medium" and self.threshold in ["always", "medium"])
            for c in analysis["changes"]
        )
        
        return PersonalityUpdate(
            changes=analysis["changes"],
            reasoning=analysis["reasoning"],
            needs_confirmation=needs_confirmation,
            source_diary=diary_entry.date
        )
    
    async def generate_update_confirmation(
        self,
        update: PersonalityUpdate
    ) -> dict:
        """生成用户确认界面所需数据"""
        return {
            "type": "personality_update",
            "message": f"检测到人格画像可能需要更新",
            "changes": update.changes,
            "reasoning": update.reasoning,
            "source": update.source_diary,
            "actions": ["accept", "reject", "modify"]
        }
```

---

## 4. 数据迁移方案

### 4.1 从 v1 到 v2 的迁移

```python
# scripts/migrate_v1_to_v2.py
"""
迁移清单：
1. 配置文件格式升级
2. 记忆索引重建（新增向量索引）
3. 日记数据扫描，生成初始向量
4. 对话历史导入向量库
"""

import asyncio
from pathlib import Path
from huaqi.config.manager import ConfigManager
from huaqi.memory.vector.client import VectorClient
from huaqi.core.diary.store import DiaryStore

async def migrate():
    print("开始数据迁移...")
    
    # 1. 备份旧数据
    backup_dir = Path.home() / ".huaqi" / "backups" / f"pre_v2_{datetime.now().strftime('%Y%m%d')}"
    backup_old_data(backup_dir)
    
    # 2. 加载旧配置，转换为新格式
    old_config = load_old_config()
    new_config = convert_config(old_config)
    ConfigManager().save(new_config)
    
    # 3. 重建向量索引
    vector_client = VectorClient()
    await vector_client.initialize()
    
    # 4. 扫描所有日记，建立向量索引
    diary_store = DiaryStore()
    entries = diary_store.list_all()
    
    for entry in entries:
        content = f"{entry.title}\n{entry.content}"
        await vector_client.add(
            doc_id=f"diary_{entry.date}",
            content=content,
            metadata={
                "type": "diary",
                "date": entry.date,
                "mood": entry.mood,
                "tags": entry.tags
            }
        )
    
    # 5. 扫描对话历史
    conversations = load_conversations()
    for conv in conversations:
        content = format_conversation(conv)
        await vector_client.add(...)
    
    print(f"迁移完成！共索引 {len(entries)} 篇日记，{len(conversations)} 次对话")

if __name__ == "__main__":
    asyncio.run(migrate())
```

### 4.2 Embedding 模型与数据库迁移

```python
# huaqi/memory/migration.py
class EmbeddingMigrator:
    """
    Embedding 模型迁移器
    支持切换 embedding 模型和向量数据库
    关键设计：原始文本永久保留，向量可重建
    """
    
    async def migrate_embedding_model(
        self,
        old_model: str,
        new_model: str,
        batch_size: int = 100
    ):
        """
        迁移策略：
        1. 导出所有原始文本（不导向量，因为模型变了向量失效）
        2. 用新模型重新计算
        3. 分批写入新集合
        4. 原子性切换
        """
        # 1. 导出原始数据
        old_client = VectorClient(embedding_model=old_model)
        all_docs = old_client.export_all()  # 只导文本和元数据
        
        # 2. 创建新客户端
        new_client = VectorClient(embedding_model=new_model)
        new_collection = f"memories_{new_model.replace('/', '_')}"
        
        # 3. 分批重建
        for batch in chunked(all_docs, batch_size):
            await new_client.add_batch(batch)
        
        # 4. 原子切换
        old_client.backup()
        new_client.activate(collection_name=new_collection)
        
    async def migrate_vector_store(
        self,
        source_store: BaseVectorStore,
        target_store: BaseVectorStore
    ):
        """迁移向量存储（Chroma -> Milvus/Pinecone）"""
        all_docs = await source_store.export_all()
        await target_store.import_batch(all_docs)


# 向量存储抽象接口
class BaseVectorStore(ABC):
    """向量存储抽象 - 支持 Chroma/Milvus/Pinecone 切换"""
    
    @abstractmethod
    async def add(self, doc_id: str, content: str, metadata: dict): ...
    
    @abstractmethod
    async def search(self, query: str, **kwargs) -> list: ...
    
    @abstractmethod
    async def export_all(self) -> list[dict]:
        """导出所有原始数据（用于迁移）"""
        ...
    
    @abstractmethod
    async def import_batch(self, data: list[dict]):
        """批量导入（用于迁移）"""
        ...

class ChromaStore(BaseVectorStore): ...
class MilvusStore(BaseVectorStore): ...
class PineconeStore(BaseVectorStore): ...
```

---

## 5. 扩展功能实现

### 5.1 配置热重载

```python
# huaqi/config/hot_reload.py
import asyncio
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigReloader(FileSystemEventHandler):
    """配置文件热重载 - Daemon 无需重启"""
    
    def __init__(self, config_path: str, daemon: "HuaqiDaemon"):
        self.config_path = config_path
        self.daemon = daemon
        self.last_reload = 0
        self.debounce_seconds = 1
    
    def on_modified(self, event):
        if event.src_path == self.config_path:
            now = time.time()
            if now - self.last_reload < self.debounce_seconds:
                return
            
            self.last_reload = now
            asyncio.create_task(self._reload())
    
    async def _reload(self):
        """热重载配置"""
        logger.info("检测到配置变更，正在热重载...")
        
        # 1. 加载并验证新配置
        try:
            new_config = load_config(self.config_path)
            if not validate_config(new_config):
                logger.error("配置无效，跳过重载")
                return
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            return
        
        # 2. 更新各模块配置
        self.daemon.update_config(new_config)
        
        # 3. 检查定时任务变更
        if self.daemon.scheduler.has_changes(new_config):
            self.daemon.scheduler.reload_jobs(new_config)
            logger.info("定时任务已更新")
        
        # 4. 检查 LLM 配置变更
        if self.daemon.llm_manager.has_changes(new_config):
            self.daemon.llm_manager.reload(new_config)
            logger.info("LLM 配置已更新")
        
        logger.info("配置热重载完成")


# Daemon 集成
class HuaqiDaemon:
    def __init__(self):
        self.config = load_config()
        self.setup_components()
        self.setup_hot_reload()
    
    def setup_hot_reload(self):
        """设置配置热重载监听"""
        config_path = get_config_file_path()
        self.reloader = ConfigReloader(config_path, self)
        
        self.observer = Observer()
        self.observer.schedule(
            self.reloader,
            path=os.path.dirname(config_path),
            recursive=False
        )
        self.observer.start()
    
    def update_config(self, new_config: AppConfig):
        """更新配置（不停机）"""
        old_config = self.config
        self.config = new_config
        
        # 通知所有组件配置变更
        for component in self.components:
            if hasattr(component, 'on_config_change'):
                component.on_config_change(old_config, new_config)
```

### 5.2 多用户架构预留

```python
# huaqi/core/multitenancy.py
"""
多用户架构预留设计
当前单用户模式，但数据模型预留 user_id，支持未来扩展
"""

from contextvars import ContextVar

# 当前用户上下文（类似 Flask g）
current_user_id: ContextVar[str] = ContextVar('user_id', default='default')


def get_current_user_id() -> str:
    """获取当前用户 ID"""
    return current_user_id.get()


def set_current_user_id(user_id: str):
    """设置当前用户上下文"""
    current_user_id.set(user_id)


# 数据模型预留 user_id
@dataclass
class DiaryEntry:
    user_id: str  # 预留
    date: str
    content: str
    ...


# 存储层按用户隔离
class UserIsolatedStorage:
    """用户隔离存储基类"""
    
    def get_user_data_dir(self, user_id: str = None) -> Path:
        """获取用户数据目录"""
        uid = user_id or get_current_user_id()
        return Path.home() / ".huaqi" / "users" / uid
    
    def get_vector_collection(self, user_id: str = None) -> str:
        """获取用户向量集合名"""
        uid = user_id or get_current_user_id()
        return f"memories_{uid}"


# Chroma 用户隔离
class ChromaUserStore(UserIsolatedStorage):
    """按用户隔离的向量存储"""
    
    def get_collection(self, user_id: str = None):
        collection_name = self.get_vector_collection(user_id)
        return self.client.get_or_create_collection(collection_name)


# 文件存储用户隔离
class FileUserStore(UserIsolatedStorage):
    """按用户隔离的文件存储"""
    
    def get_diary_dir(self, user_id: str = None) -> Path:
        return self.get_user_data_dir(user_id) / "diary"
    
    def get_conversation_dir(self, user_id: str = None) -> Path:
        return self.get_user_data_dir(user_id) / "conversations"
```

---

## 6. 测试策略

### 6.1 单元测试

```python
# tests/unit/test_hybrid_search.py
import pytest
from huaqi.memory.vector.hybrid_search import HybridSearch

@pytest.fixture
def search_engine(tmp_path):
    return HybridSearch(chroma_path=str(tmp_path / "chroma"))

@pytest.mark.asyncio
async def test_hybrid_search_basic(search_engine):
    # 添加测试数据
    await search_engine.add("doc1", "今天学习了 Python", {"type": "diary"})
    await search_engine.add("doc2", "Python 是一门编程语言", {"type": "note"})
    
    # 搜索
    results = await search_engine.search("学习编程", top_k=2)
    
    assert len(results) == 2
    assert results[0]["id"] == "doc1"  # 更相关
```

### 6.2 集成测试

```python
# tests/integration/test_chat_workflow.py
@pytest.mark.asyncio
async def test_chat_workflow_with_memory():
    """测试完整对话流程，包含记忆检索"""
    graph = build_chat_graph()
    
    # 先添加一条日记
    await add_test_diary("我喜欢编程")
    
    # 执行对话
    result = await graph.ainvoke({
        "messages": [{"role": "user", "content": "你还记得我喜欢什么吗？"}]
    })
    
    # 验证回复包含记忆
    assert "编程" in result["messages"][-1]["content"]
```

### 6.3 性能测试

```python
# tests/perf/test_retrieval_perf.py
@pytest.mark.benchmark
async def test_vector_search_performance():
    """测试万级数据检索性能"""
    search_engine = create_engine_with_10k_docs()
    
    start = time.time()
    results = await search_engine.search("测试查询")
    elapsed = time.time() - start
    
    assert elapsed < 0.1  # 100ms 内
```

---

## 7. 中断任务恢复机制

### 7.1 CLI 恢复实现

```python
# huaqi/cli.py - 中断恢复命令

@app.command()
async def resume(task_id: Optional[str] = None):
    """
    恢复暂停的任务
    可通过对话直接恢复，也可显式指定 task_id
    """
    # 1. 查询待处理的中断任务
    pending = await get_pending_interrupts()
    
    if not pending:
        print("没有待处理的任务")
        return
    
    if not task_id:
        # 列出所有待处理任务
        print("待处理任务：")
        for task in pending:
            print(f"  {task.id}: {task.type} - {task.description}")
        print("\n使用 `huaqi resume <task_id>` 恢复特定任务")
        return
    
    # 2. 加载任务状态
    task = await load_interrupt_task(task_id)
    if not task:
        print(f"任务 {task_id} 不存在或已过期")
        return
    
    # 3. 展示待确认内容
    print(f"任务: {task.description}")
    print(f"内容:\n{task.interrupt_data['preview']}\n")
    
    # 4. 获取用户决策
    action = await prompt_user("请选择操作", ["confirm", "edit", "reject"])
    
    if action == "edit":
        modified = await edit_content(task.interrupt_data['content'])
        user_input = {"action": "edit", "modified_content": modified}
    else:
        user_input = {"action": action}
    
    # 5. 恢复 Agent 执行
    result = await resume_agent_task(task_id, user_input)
    print(f"任务已恢复: {result}")


# 主对话循环中自动检测待处理任务
async def chat_loop():
    while True:
        # 检查是否有待处理的中断任务
        pending = await get_pending_interrupts()
        if pending:
            print(f"\n[系统] 你有 {len(pending)} 个待处理任务，输入 `resume` 查看")
        
        user_input = await prompt("huaqi> ")
        
        # 检测恢复意图
        if user_input.strip().lower() in ["resume", "恢复", "继续"]:
            await resume()
            continue
        
        # 检测确认意图（如 "确认任务 task_001"）
        if match := re.match(r"确认任务\s+(\w+)", user_input):
            await resume(match.group(1))
            continue
        
        # 正常对话流程
        result = await agent_runner.run(user_input)
        print(result)
```

### 7.2 Agent 恢复实现

```python
# huaqi/agent/runner.py

class AgentRunner:
    """Agent 运行器 - 支持中断和恢复"""
    
    async def resume_task(
        self,
        task_id: str,
        user_input: dict,
        graph_type: str = "content"
    ):
        """
        恢复中断的任务
        """
        # 1. 加载之前的 checkpoint
        config = {"configurable": {"thread_id": task_id}}
        
        # 2. 根据类型选择 graph
        graph = self.get_graph(graph_type)
        
        # 3. 恢复执行（LangGraph 自动从 checkpoint 恢复）
        result = await graph.ainvoke(
            {"user_decision": user_input},
            config=config
        )
        
        return result
```

---

## 8. 部署与运维

### 8.1 开发模式启动

```bash
# 开发模式（CLI 交互）
poetry run huaqi chat

# 开发模式（Daemon）
poetry run huaqi daemon start --foreground
```

### 8.2 生产部署

```bash
# 使用 systemd（Linux）
sudo cp scripts/huaqi-daemon.service /etc/systemd/system/
sudo systemctl enable huaqi-daemon
sudo systemctl start huaqi-daemon

# 查看日志
journalctl -u huaqi-daemon -f
```

### 8.3 监控指标

| 指标 | 收集方式 | 告警阈值 |
|------|---------|---------|
| 对话响应延迟 | LangSmith | > 3s |
| API 调用错误率 | 日志统计 | > 5% |
| 向量库大小 | 定时检查 | > 10GB |
| 定时任务失败 | APScheduler 事件 | 连续 3 次失败 |
| 人机协同超时 | 任务状态检查 | > 24h |

---

## 9. 附录

### 9.1 关键依赖版本

```toml
[tool.poetry.dependencies]
python = "^3.10"
langgraph = "^0.2.0"
langchain = "^0.3.0"
langchain-openai = "^0.2.0"
apscheduler = "^4.0.0a"
chromadb = "^0.5.0"
typer = "^0.12.0"
pydantic = "^2.0.0"
pydantic-settings = "^2.0.0"
structlog = "^24.0.0"
aiohttp = "^3.9.0"
watchdog = "^4.0.0"  # 配置热重载
```

### 9.2 环境变量

```bash
# LLM API
KIMI_API_KEY=sk-...
OPENAI_API_KEY=sk-...

# 配置
HUAQI_CONFIG_DIR=~/.huaqi
HUAQI_LOG_LEVEL=INFO
HUAQI_ENV=development  # production
```

### 9.3 关键设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 框架 | LangGraph | 状态管理、人机协同、持久化 |
| 向量数据库 | Chroma | 本地优先、零运维、足够性能 |
| 定时任务 | APScheduler | 简单、Python 原生、持久化 |
| CLI 框架 | Typer | 类型安全、自动文档 |
| 配置文件 | YAML | 人类可读、注释支持 |
| 数据格式 | Markdown | Git 友好、长期可读 |
| 配置热重载 | watchdog | 无需重启 Daemon |
| 多用户预留 | ContextVar | 轻量、可扩展 |
| Embedding 迁移 | 文本永久保留 | 向量可重建，数据安全 |

---

## 10. 中断任务恢复机制

### 10.1 CLI 恢复实现

```python
# huaqi/cli.py - 中断恢复命令

@app.command()
async def resume(task_id: Optional[str] = None):
    """
    恢复暂停的任务
    可通过对话直接恢复，也可显式指定 task_id
    """
    # 1. 查询待处理的中断任务
    pending = await get_pending_interrupts()
    
    if not pending:
        print("没有待处理的任务")
        return
    
    if not task_id:
        # 列出所有待处理任务
        print("待处理任务：")
        for task in pending:
            print(f"  {task.id}: {task.type} - {task.description}")
        print("\n使用 `huaqi resume <task_id>` 恢复特定任务")
        return
    
    # 2. 加载任务状态
    task = await load_interrupt_task(task_id)
    if not task:
        print(f"任务 {task_id} 不存在或已过期")
        return
    
    # 3. 展示待确认内容
    print(f"任务: {task.description}")
    print(f"内容:\n{task.interrupt_data['preview']}\n")
    
    # 4. 获取用户决策
    action = await prompt_user("请选择操作", ["confirm", "edit", "reject"])
    
    if action == "edit":
        modified = await edit_content(task.interrupt_data['content'])
        user_input = {"action": "edit", "modified_content": modified}
    else:
        user_input = {"action": action}
    
    # 5. 恢复 Agent 执行
    result = await resume_agent_task(task_id, user_input)
    print(f"任务已恢复: {result}")


# 主对话循环中自动检测待处理任务
async def chat_loop():
    while True:
        # 检查是否有待处理的中断任务
        pending = await get_pending_interrupts()
        if pending:
            print(f"\n[系统] 你有 {len(pending)} 个待处理任务，输入 `resume` 查看")
        
        user_input = await prompt("huaqi> ")
        
        # 检测恢复意图
        if user_input.strip().lower() in ["resume", "恢复", "继续"]:
            await resume()
            continue
        
        # 检测确认意图（如 "确认任务 task_001"）
        if match := re.match(r"确认任务\s+(\w+)", user_input):
            await resume(match.group(1))
            continue
        
        # 正常对话流程
        result = await agent_runner.run(user_input)
        print(result)
```

### 10.2 Agent 恢复实现

```python
# huaqi/agent/runner.py

class AgentRunner:
    """Agent 运行器 - 支持中断和恢复"""
    
    async def resume_task(
        self,
        task_id: str,
        user_input: dict,
        graph_type: str = "content"
    ):
        """
        恢复中断的任务
        """
        # 1. 加载之前的 checkpoint
        config = {"configurable": {"thread_id": task_id}}
        
        # 2. 根据类型选择 graph
        graph = self.get_graph(graph_type)
        
        # 3. 恢复执行（LangGraph 自动从 checkpoint 恢复）
        result = await graph.ainvoke(
            {"user_decision": user_input},
            config=config
        )
        
        return result
```

---

## 11. 部署与运维

### 11.1 开发模式启动

```bash
# 开发模式（CLI 交互）
poetry run huaqi chat

# 开发模式（Daemon）
poetry run huaqi daemon start --foreground
```

### 11.2 生产部署

```bash
# 使用 systemd（Linux）
sudo cp scripts/huaqi-daemon.service /etc/systemd/system/
sudo systemctl enable huaqi-daemon
sudo systemctl start huaqi-daemon

# 查看日志
journalctl -u huaqi-daemon -f
```

### 11.3 监控指标

| 指标 | 收集方式 | 告警阈值 |
|------|---------|---------|
| 对话响应延迟 | LangSmith | > 3s |
| API 调用错误率 | 日志统计 | > 5% |
| 向量库大小 | 定时检查 | > 10GB |
| 定时任务失败 | APScheduler 事件 | 连续 3 次失败 |
| 人机协同超时 | 任务状态检查 | > 24h |

---

## 12. 附录

### 12.1 关键依赖版本

```toml
[tool.poetry.dependencies]
python = "^3.10"
langgraph = "^0.2.0"
langchain = "^0.3.0"
langchain-openai = "^0.2.0"
apscheduler = "^4.0.0a"
chromadb = "^0.5.0"
typer = "^0.12.0"
pydantic = "^2.0.0"
pydantic-settings = "^2.0.0"
structlog = "^24.0.0"
aiohttp = "^3.9.0"
watchdog = "^4.0.0"  # 配置热重载
```

### 12.2 环境变量

```bash
# LLM API
KIMI_API_KEY=sk-...
OPENAI_API_KEY=sk-...

# 配置
HUAQI_CONFIG_DIR=~/.huaqi
HUAQI_LOG_LEVEL=INFO
HUAQI_ENV=development  # production
```

### 12.3 关键设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 框架 | LangGraph | 状态管理、人机协同、持久化 |
| 向量数据库 | Chroma | 本地优先、零运维、足够性能 |
| 定时任务 | APScheduler | 简单、Python 原生、持久化 |
| CLI 框架 | Typer | 类型安全、自动文档 |
| 配置文件 | YAML | 人类可读、注释支持 |
| 数据格式 | Markdown | Git 友好、长期可读 |
| 配置热重载 | watchdog | 无需重启 Daemon |
| 多用户预留 | ContextVar | 轻量、可扩展 |
| Embedding 迁移 | 文本永久保留 | 向量可重建，数据安全 |

### 5.1 单元测试

```python
# tests/unit/test_hybrid_search.py
import pytest
from huaqi.memory.vector.hybrid_search import HybridSearch

@pytest.fixture
def search_engine(tmp_path):
    return HybridSearch(chroma_path=str(tmp_path / "chroma"))

@pytest.mark.asyncio
async def test_hybrid_search_basic(search_engine):
    # 添加测试数据
    await search_engine.add("doc1", "今天学习了 Python", {"type": "diary"})
    await search_engine.add("doc2", "Python 是一门编程语言", {"type": "note"})
    
    # 搜索
    results = await search_engine.search("学习编程", top_k=2)
    
    assert len(results) == 2
    assert results[0]["id"] == "doc1"  # 更相关
```

### 5.2 集成测试

```python
# tests/integration/test_chat_workflow.py
@pytest.mark.asyncio
async def test_chat_workflow_with_memory():
    """测试完整对话流程，包含记忆检索"""
    graph = build_chat_graph()
    
    # 先添加一条日记
    await add_test_diary("我喜欢编程")
    
    # 执行对话
    result = await graph.ainvoke({
        "messages": [{"role": "user", "content": "你还记得我喜欢什么吗？"}]
    })
    
    # 验证回复包含记忆
    assert "编程" in result["messages"][-1]["content"]
```

### 5.3 性能测试

```python
# tests/perf/test_retrieval_perf.py
@pytest.mark.benchmark
async def test_vector_search_performance():
    """测试万级数据检索性能"""
    search_engine = create_engine_with_10k_docs()
    
    start = time.time()
    results = await search_engine.search("测试查询")
    elapsed = time.time() - start
    
    assert elapsed < 0.1  # 100ms 内
```

---

## 6. 部署与运维

### 6.1 开发模式启动

```bash
# 开发模式（CLI 交互）
poetry run huaqi chat

# 开发模式（Daemon）
poetry run huaqi daemon start --foreground
```

### 6.2 生产部署

```bash
# 使用 systemd（Linux）
sudo cp scripts/huaqi-daemon.service /etc/systemd/system/
sudo systemctl enable huaqi-daemon
sudo systemctl start huaqi-daemon

# 查看日志
journalctl -u huaqi-daemon -f
```

### 6.3 监控指标

| 指标 | 收集方式 | 告警阈值 |
|------|---------|---------|
| 对话响应延迟 | LangSmith | > 3s |
| API 调用错误率 | 日志统计 | > 5% |
| 向量库大小 | 定时检查 | > 10GB |
| 定时任务失败 | APScheduler 事件 | 连续 3 次失败 |
| 人机协同超时 | 任务状态检查 | > 24h |

---

## 7. 附录

### 7.1 关键依赖版本

```toml
[tool.poetry.dependencies]
python = "^3.10"
langgraph = "^0.2.0"
langchain = "^0.3.0"
langchain-openai = "^0.2.0"
apscheduler = "^4.0.0a"
chromadb = "^0.5.0"
typer = "^0.12.0"
pydantic = "^2.0.0"
pydantic-settings = "^2.0.0"
structlog = "^24.0.0"
aiohttp = "^3.9.0"
```

### 7.2 环境变量

```bash
# LLM API
KIMI_API_KEY=sk-...
OPENAI_API_KEY=sk-...

# 配置
HUAQI_CONFIG_DIR=~/.huaqi
HUAQI_LOG_LEVEL=INFO
HUAQI_ENV=development  # production
```

### 7.3 关键设计决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| Agent 框架 | LangGraph | 状态管理、人机协同、持久化 |
| 向量数据库 | Chroma | 本地优先、零运维、足够性能 |
| 定时任务 | APScheduler | 简单、Python 原生、持久化 |
| CLI 框架 | Typer | 类型安全、自动文档 |
| 配置文件 | YAML | 人类可读、注释支持 |
| 数据格式 | Markdown | Git 友好、长期可读 |
