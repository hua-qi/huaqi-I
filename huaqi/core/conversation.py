"""对话管理系统

整合用户、LLM、记忆，实现完整的对话流程
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Iterator
from datetime import datetime
from pathlib import Path
import json
import uuid

from .config import ConfigManager
from .llm import LLMManager, Message, LLMResponse, init_llm_manager
from .memory_extractor import MemoryExtractor, SimpleMemoryExtractor
from ..memory.storage.user_isolated import UserMemoryManager
from ..memory.storage.markdown_store import MarkdownMemoryStore
from ..memory.storage.vector_store import UserVectorStore, OpenAIEmbedding, DummyEmbedding



@dataclass
class ConversationTurn:
    """对话回合"""
    id: str
    timestamp: datetime
    user_message: str
    assistant_response: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_message": self.user_message,
            "assistant_response": self.assistant_response,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationTurn":
        return cls(
            id=data["id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            user_message=data["user_message"],
            assistant_response=data["assistant_response"],
            metadata=data.get("metadata", {}),
        )


@dataclass
class ConversationSession:
    """对话会话"""
    session_id: str
    user_id: str
    started_at: datetime
    turns: List[ConversationTurn] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def message_count(self) -> int:
        return len(self.turns) * 2  # user + assistant
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "started_at": self.started_at.isoformat(),
            "turns": [t.to_dict() for t in self.turns],
            "context": self.context,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationSession":
        return cls(
            session_id=data["session_id"],
            user_id=data["user_id"],
            started_at=datetime.fromisoformat(data["started_at"]),
            turns=[ConversationTurn.from_dict(t) for t in data.get("turns", [])],
            context=data.get("context", {}),
        )


class ConversationManager:
    """对话管理器"""
    
    def __init__(
        self,
        config_manager: ConfigManager,
        llm_manager: Optional[LLMManager] = None,
        user_id: Optional[str] = None,
    ):
        self.config_manager = config_manager
        self.user_id = user_id or config_manager.current_user_id
        self.llm_manager = llm_manager or init_llm_manager()
        self.memory_manager = UserMemoryManager(config_manager, self.user_id)
        
        self._current_session: Optional[ConversationSession] = None
        self._system_prompt: Optional[str] = None
        
        # 初始化向量存储
        self._init_vector_store()
        
        # 初始化记忆提取器
        self.memory_extractor = MemoryExtractor(
            llm_manager=self.llm_manager,
            memory_manager=self.memory_manager
        )
        
        # 加载配置
        self._load_config()
    
    def _init_vector_store(self):
        """初始化向量存储"""
        try:
            # 尝试使用 OpenAI Embedding
            config = self.config_manager.load_config(self.user_id)
            active_llm = config.llm_providers.get(config.llm_default_provider)
            
            if active_llm and active_llm.api_key:
                embedding_provider = OpenAIEmbedding(
                    api_key=active_llm.api_key,
                    model=config.memory.embedding_model
                )
            else:
                # 使用虚拟 Embedding
                embedding_provider = DummyEmbedding()
            
            self.vector_store = UserVectorStore(
                base_dir=self.config_manager.get_user_data_dir(self.user_id).parent.parent,
                user_id=self.user_id,
                embedding_provider=embedding_provider
            )
            
        except Exception:
            # 失败时使用虚拟 Embedding
            self.vector_store = UserVectorStore(
                base_dir=self.config_manager.get_user_data_dir(self.user_id).parent.parent,
                user_id=self.user_id,
                embedding_provider=DummyEmbedding()
            )
    
    def _load_config(self):
        """加载配置"""
        config = self.config_manager.load_config(self.user_id)
        
        # 配置 LLM
        for name, provider_config in config.llm_providers.items():
            from .llm import LLMConfig
            llm_config = LLMConfig(
                provider=name,
                model=provider_config.model,
                api_key=provider_config.api_key,
                api_base=provider_config.api_base,
                temperature=provider_config.temperature,
                max_tokens=provider_config.max_tokens,
            )
            self.llm_manager.add_config(llm_config)
        
        # 设置默认提供商
        if config.llm_default_provider:
            try:
                self.llm_manager.set_active(config.llm_default_provider)
            except:
                # 如果设置失败，使用 dummy
                from .llm import LLMConfig
                self.llm_manager.add_config(LLMConfig(
                    provider="dummy",
                    model="dummy",
                ))
                self.llm_manager.set_active("dummy")
        
        # 加载系统提示词
        self._system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self, user_query: Optional[str] = None) -> str:
        """构建系统提示词，包含相关记忆上下文"""
        # 基础系统提示词
        base_prompt = """你是 Huaqi，用户的个人 AI 同伴。你的核心理念是"不是使用 AI，而是养育 AI"。

你的特点：
1. 你是用户的同伴（Peer），不是工具或仆人
2. 你会记住用户的偏好、习惯和重要信息
3. 你会随着对话深入而变得更懂用户
4. 你的目标是帮助用户成长，而不仅仅是回答问题

在对话中：
- 保持友好、真诚的语气
- 主动关心用户的目标和进展
- 适时提醒用户之前提到过的重要事情
- 帮助用户整理思路、做出决策
- 鼓励用户尝试新事物、走出舒适区
"""
        
        # 加载用户档案
        user_profile = self._load_user_profile()
        if user_profile:
            base_prompt += f"\n\n## 用户档案\n\n{user_profile}\n"
        
        # 如果提供了查询，检索相关记忆
        if user_query:
            relevant_memories = self._retrieve_relevant_memories(user_query)
            if relevant_memories:
                base_prompt += f"\n\n## 相关记忆（你可能需要参考）\n\n{relevant_memories}\n"
        
        return base_prompt
    
    def _load_user_profile(self) -> Optional[str]:
        """加载用户档案"""
        try:
            profile_path = self.memory_manager.user_memory_dir / "identity" / "profile.md"
            if profile_path.exists():
                with open(profile_path, "r", encoding="utf-8") as f:
                    content = f.read()
                
                # 解析 frontmatter 和正文
                from ..memory.storage.markdown_store import MarkdownMemoryStore
                store = MarkdownMemoryStore(Path("/tmp"))
                _, body = store._parse_frontmatter(content)
                
                # 只取前 1000 字符作为提示
                return body[:1000] + "..." if len(body) > 1000 else body
        except Exception:
            pass
        
        return None
    
    def _retrieve_relevant_memories(self, query: str, top_k: int = 3) -> Optional[str]:
        """检索相关记忆"""
        try:
            results = self.vector_store.search_memories(query, top_k=top_k)
            
            if not results:
                return None
            
            memories_text = []
            for i, result in enumerate(results, 1):
                content = result.get("content", "")
                score = result.get("score", 0)
                
                # 只取高相关度的记忆
                if score >= 0.7:
                    memories_text.append(f"{i}. {content[:200]}...")
            
            return "\n".join(memories_text) if memories_text else None
            
        except Exception:
            return None
    
    def start_session(self) -> ConversationSession:
        """开始新会话"""
        self._current_session = ConversationSession(
            session_id=str(uuid.uuid4())[:8],
            user_id=self.user_id,
            started_at=datetime.now(),
        )
        return self._current_session
    
    def get_session(self) -> Optional[ConversationSession]:
        """获取当前会话"""
        return self._current_session
    
    def chat(self, user_input: str, stream: bool = False) -> str | Iterator[str]:
        """对话
        
        Args:
            user_input: 用户输入
            stream: 是否流式输出
            
        Returns:
            str 或 Iterator[str]
        """
        if self._current_session is None:
            self.start_session()
        
        # 1. 构建消息列表
        messages = self._build_messages(user_input)
        
        # 2. 调用 LLM
        if stream:
            return self._chat_stream(user_input, messages)
        else:
            return self._chat_sync(user_input, messages)
    
    def _build_messages(self, user_input: str) -> List[Message]:
        """构建消息列表"""
        messages = []
        
        # 系统提示词（包含相关记忆）
        system_prompt = self._build_system_prompt(user_input)
        messages.append(Message.system(system_prompt))
        
        # 历史对话（最近几轮）
        if self._current_session:
            history = self._current_session.turns[-5:]  # 最近5轮
            for turn in history:
                messages.append(Message.user(turn.user_message))
                messages.append(Message.assistant(turn.assistant_response))
        
        # 当前输入
        messages.append(Message.user(user_input))
        
        return messages
    
    def _chat_sync(self, user_input: str, messages: List[Message]) -> str:
        """同步对话"""
        try:
            response = self.llm_manager.chat(messages, stream=False)
            
            # 记录对话
            self._record_turn(user_input, response.content, {
                "model": response.model,
                "tokens": response.total_tokens,
                "latency_ms": response.latency_ms,
            })
            
            # 异步提取记忆（不阻塞对话）
            self._extract_memory_async(user_input, response.content)
            
            return response.content
            
        except Exception as e:
            error_msg = f"抱歉，对话出现了一些问题：{str(e)}"
            self._record_turn(user_input, error_msg, {"error": str(e)})
            return error_msg
    
    def _chat_stream(self, user_input: str, messages: List[Message]) -> Iterator[str]:
        """流式对话"""
        full_response = []
        
        try:
            for chunk in self.llm_manager.chat(messages, stream=True):
                full_response.append(chunk)
                yield chunk
            
            # 记录完整对话
            complete_response = "".join(full_response)
            self._record_turn(user_input, complete_response, {"stream": True})
            
            # 异步提取记忆
            self._extract_memory_async(user_input, complete_response)
            
        except Exception as e:
            error_msg = f"抱歉，对话出现了一些问题：{str(e)}"
            yield error_msg
            self._record_turn(user_input, error_msg, {"error": str(e), "stream": True})
    
    def _extract_memory_async(self, user_input: str, assistant_response: str):
        """异步提取记忆（简化版，不阻塞对话）"""
        try:
            # 使用简单提取器
            simple_extractor = SimpleMemoryExtractor()
            insights = simple_extractor.extract(user_input)
            
            # 保存到洞察文件
            for insight in insights:
                if insight["confidence"] >= 0.7:
                    self._save_insight(insight)
        except:
            pass
    
    def _save_insight(self, insight: Dict):
        """保存洞察"""
        try:
            insights_path = self.memory_manager.user_memory_dir / "patterns" / "insights.md"
            insights_path.parent.mkdir(parents=True, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            entry = f"- [{timestamp}] [{insight['category']}] {insight['content']}\n"
            
            if insights_path.exists():
                with open(insights_path, "a", encoding="utf-8") as f:
                    f.write(entry)
            else:
                with open(insights_path, "w", encoding="utf-8") as f:
                    f.write("---\ntype: insights\n---\n\n# 自动提取的洞察\n\n")
                    f.write(entry)
        except:
            pass
    
    def _record_turn(self, user_input: str, assistant_response: str, metadata: Dict[str, Any]):
        """记录对话回合"""
        if self._current_session is None:
            return
        
        turn = ConversationTurn(
            id=str(uuid.uuid4())[:8],
            timestamp=datetime.now(),
            user_message=user_input,
            assistant_response=assistant_response,
            metadata=metadata,
        )
        
        self._current_session.turns.append(turn)
        
        # 保存到文件
        self._save_session()
    
    def _save_session(self):
        """保存会话到 Markdown 文件"""
        if self._current_session is None:
            return
        
        # 使用 Markdown 存储
        conversations_dir = self.memory_manager.user_memory_dir / "conversations"
        store = MarkdownMemoryStore(conversations_dir)
        
        # 将 turns 转换为字典列表
        turns_data = [
            {
                "user_message": turn.user_message,
                "assistant_response": turn.assistant_response,
                "metadata": turn.metadata,
            }
            for turn in self._current_session.turns
        ]
        
        # 保存为 Markdown
        store.save_conversation(
            session_id=self._current_session.session_id,
            timestamp=self._current_session.started_at,
            turns=turns_data,
            metadata={
                "user_id": self._current_session.user_id,
                "message_count": self._current_session.message_count,
            }
        )
    
    def get_recent_sessions(self, limit: int = 10) -> List[ConversationSession]:
        """获取最近的会话"""
        conversations_dir = (
            self.memory_manager.user_memory_dir / "conversations"
        )
        store = MarkdownMemoryStore(conversations_dir)
        
        # 从 Markdown 文件加载
        conversations = store.list_conversations(limit=limit)
        
        sessions = []
        for conv_info in conversations:
            try:
                filepath = conversations_dir / conv_info["filepath"]
                conv_data = store.load_conversation(filepath)
                
                if conv_data:
                    session = ConversationSession(
                        session_id=conv_data["session_id"],
                        user_id=self.user_id,
                        started_at=datetime.fromisoformat(conv_data["created_at"]),
                        turns=[
                            ConversationTurn(
                                id=str(i),
                                timestamp=datetime.now(),  # Markdown 中不保存每轮时间
                                user_message=turn["user_message"],
                                assistant_response=turn["assistant_response"],
                                metadata=turn.get("metadata", {}),
                            )
                            for i, turn in enumerate(conv_data.get("turns", []))
                        ],
                    )
                    sessions.append(session)
            except:
                continue
        
        return sessions
    
    def clear_session(self):
        """清除当前会话"""
        self._current_session = None
    
    def export_session(self) -> Dict[str, Any]:
        """导出当前会话"""
        if self._current_session:
            return self._current_session.to_dict()
        return {}
