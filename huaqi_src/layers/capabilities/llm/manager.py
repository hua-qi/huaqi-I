"""LLM 接口抽象层

支持多提供商统一接口
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Iterator, Optional, List, Dict, Any, Callable, Union
from enum import Enum
import time
import json
import sys


class MessageRole(Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """对话消息"""
    role: MessageRole
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    reasoning_content: Optional[str] = None  # 用于支持 thinking 模式的模型

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "role": self.role.value,
            "content": self.content,
        }
        # 如果存在 reasoning_content，添加到字典中（某些模型需要）
        if self.reasoning_content is not None:
            result["reasoning_content"] = self.reasoning_content
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Message":
        """从字典创建消息"""
        role = MessageRole(data.get("role", "user"))
        content = data.get("content", "")
        reasoning_content = data.get("reasoning_content")
        return cls(
            role=role,
            content=content,
            reasoning_content=reasoning_content,
            metadata=data.get("metadata", {})
        )
    
    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role=MessageRole.SYSTEM, content=content)
    
    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role=MessageRole.USER, content=content)
    
    @classmethod
    def assistant(cls, content: str) -> "Message":
        return cls(role=MessageRole.ASSISTANT, content=content)


@dataclass
class LLMResponse:
    """LLM 响应"""
    content: str
    model: str
    usage: Dict[str, int] = field(default_factory=dict)
    latency_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    reasoning_content: Optional[str] = None  # 支持 thinking 模式的推理内容
    tool_calls: Optional[List[Dict[str, Any]]] = None  # 工具调用
    
    @property
    def input_tokens(self) -> int:
        return self.usage.get("input_tokens", 0)
    
    @property
    def output_tokens(self) -> int:
        return self.usage.get("output_tokens", 0)
    
    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class LLMConfig:
    """LLM 配置"""
    provider: str
    model: str
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 4000
    timeout: int = 60
    extra_params: Dict[str, Any] = field(default_factory=dict)


class BaseLLMProvider(ABC):
    """LLM 提供商基类"""
    
    name: str = "base"
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self._validate_config()
    
    @abstractmethod
    def _validate_config(self):
        """验证配置"""
        pass
    
    @abstractmethod
    def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """非流式对话"""
        pass
    
    @abstractmethod
    def chat_stream(self, messages: List[Message], **kwargs) -> Iterator[str]:
        """流式对话"""
        pass
    
    def count_tokens(self, text: str) -> int:
        """估算 token 数（粗略估计）"""
        # 中文约为 1 token / 字，英文约为 1 token / 4 字符
        return len(text) // 2 + 1


class OpenAIProvider(BaseLLMProvider):
    """OpenAI 提供商"""
    
    name = "openai"
    
    def _validate_config(self):
        if not self.config.api_key:
            raise ValueError("OpenAI 需要提供 api_key")
    
    def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """调用 OpenAI API"""
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
                timeout=self.config.timeout,
            )
            
            start_time = time.time()
            
            response = client.chat.completions.create(
                model=self.config.model,
                messages=[m.to_dict() for m in messages],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                **kwargs
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            return LLMResponse(
                content=response.choices[0].message.content,
                model=response.model,
                usage={
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                },
                latency_ms=latency_ms,
            )
            
        except ImportError:
            raise ImportError("请先安装 openai: pip install openai")
        except Exception as e:
            raise LLMError(f"OpenAI API 调用失败: {e}")
    
    def chat_stream(self, messages: List[Message], **kwargs) -> Iterator[str]:
        """流式调用 OpenAI API"""
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
                timeout=self.config.timeout,
            )
            
            stream = client.chat.completions.create(
                model=self.config.model,
                messages=[m.to_dict() for m in messages],
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                stream=True,
                **kwargs
            )
            
            for chunk in stream:
                # 处理空choices的情况
                if not chunk.choices:
                    continue
                # 安全地获取delta.content
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content
                    
        except ImportError:
            raise ImportError("请先安装 openai: pip install openai")
        except Exception as e:
            error_msg = str(e)
            if "timed out" in error_msg.lower() or "timeout" in error_msg.lower():
                raise LLMError(
                    f"LLM API 连接超时 ({self.config.timeout}秒)。\n"
                    f"请检查:\n"
                    f"1. API 地址是否正确: {self.config.api_base}\n"
                    f"2. 网络连接是否正常\n"
                    f"3. 如果使用内网地址，请确认 VPN 或网络环境"
                )
            # DeepSeek thinking 模式错误处理
            if "reasoning_content" in error_msg.lower() or "thinking" in error_msg.lower():
                # 降级到非流式调用
                try:
                    response = client.chat.completions.create(
                        model=self.config.model,
                        messages=[m.to_dict() for m in messages],
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens,
                        stream=False,
                        **kwargs
                    )
                    yield response.choices[0].message.content
                except Exception as retry_e:
                    raise LLMError(f"流式调用失败，非流式重试也失败: {retry_e}")
            raise LLMError(f"OpenAI API 流式调用失败: {e}")


class ClaudeProvider(BaseLLMProvider):
    """Claude 提供商"""
    
    name = "claude"
    
    def _validate_config(self):
        if not self.config.api_key:
            raise ValueError("Claude 需要提供 api_key")
    
    def _convert_messages(self, messages: List[Message]) -> tuple:
        """转换消息格式为 Claude 格式"""
        system = None
        claude_messages = []
        
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                system = msg.content
            else:
                claude_messages.append({
                    "role": "user" if msg.role == MessageRole.USER else "assistant",
                    "content": msg.content,
                })
        
        return system, claude_messages
    
    def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """调用 Claude API"""
        try:
            import anthropic
            
            client = anthropic.Anthropic(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
                timeout=self.config.timeout,
            )
            
            system, claude_messages = self._convert_messages(messages)
            
            start_time = time.time()
            
            response = client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system,
                messages=claude_messages,
                **kwargs
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            return LLMResponse(
                content=response.content[0].text,
                model=response.model,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
                latency_ms=latency_ms,
            )
            
        except ImportError:
            raise ImportError("请先安装 anthropic: pip install anthropic")
        except Exception as e:
            raise LLMError(f"Claude API 调用失败: {e}")
    
    def chat_stream(self, messages: List[Message], **kwargs) -> Iterator[str]:
        """流式调用 Claude API"""
        try:
            import anthropic
            
            client = anthropic.Anthropic(
                api_key=self.config.api_key,
                base_url=self.config.api_base,
                timeout=self.config.timeout,
            )
            
            system, claude_messages = self._convert_messages(messages)
            
            with client.messages.stream(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=system,
                messages=claude_messages,
                **kwargs
            ) as stream:
                for text in stream.text_stream:
                    yield text
                    
        except ImportError:
            raise ImportError("请先安装 anthropic: pip install anthropic")
        except Exception as e:
            raise LLMError(f"Claude API 流式调用失败: {e}")


class DummyProvider(BaseLLMProvider):
    """虚拟提供商（用于测试）"""
    
    name = "dummy"
    
    def _validate_config(self):
        pass
    
    def chat(self, messages: List[Message], **kwargs) -> LLMResponse:
        """返回固定回复"""
        return LLMResponse(
            content="这是一个虚拟回复。请配置真实的 LLM 提供商。",
            model="dummy",
            usage={"input_tokens": 10, "output_tokens": 10},
            latency_ms=100,
        )
    
    def chat_stream(self, messages: List[Message], **kwargs) -> Iterator[str]:
        """流式返回固定回复"""
        text = "这是一个虚拟回复。请配置真实的 LLM 提供商。"
        for word in text:
            yield word
            time.sleep(0.01)


class LLMError(Exception):
    """LLM 错误"""
    pass


class LLMManager:
    """LLM 管理器
    
    管理多个 LLM 提供商，支持动态切换
    """
    
    _providers: Dict[str, type[BaseLLMProvider]] = {
        "openai": OpenAIProvider,
        "claude": ClaudeProvider,
        "dummy": DummyProvider,
    }
    
    def __init__(self):
        self._active_provider: Optional[BaseLLMProvider] = None
        self._configs: Dict[str, LLMConfig] = {}
    
    def register_provider(self, name: str, provider_class: type[BaseLLMProvider]):
        """注册新的提供商"""
        self._providers[name] = provider_class
    
    def add_config(self, config: LLMConfig):
        """添加提供商配置"""
        self._configs[config.provider] = config
    
    def set_active(self, provider_name: str):
        """设置当前使用的提供商"""
        if provider_name not in self._configs:
            raise ValueError(f"未配置提供商: {provider_name}")
        
        if provider_name not in self._providers:
            raise ValueError(f"未知的提供商: {provider_name}")
        
        config = self._configs[provider_name]
        self._active_provider = self._providers[provider_name](config)
    
    def chat(self, messages: List[Message], stream: bool = False, **kwargs) -> Union[LLMResponse, Iterator[str]]:
        """对话
        
        Args:
            messages: 消息列表
            stream: 是否流式输出
            **kwargs: 额外的参数
            
        Returns:
            LLMResponse 或 Iterator[str]
        """
        if self._active_provider is None:
            # 尝试使用 dummy 或第一个可用配置
            if "dummy" in self._configs:
                self.set_active("dummy")
            elif self._configs:
                self.set_active(list(self._configs.keys())[0])
            else:
                raise LLMError("未配置任何 LLM 提供商")
        
        if stream:
            return self._active_provider.chat_stream(messages, **kwargs)
        else:
            return self._active_provider.chat(messages, **kwargs)
    
    def quick_chat(self, prompt: str, system: Optional[str] = None) -> str:
        """快速单轮对话
        
        Args:
            prompt: 用户输入
            system: 系统提示词
            
        Returns:
            str: 回复内容
        """
        messages = []
        if system:
            messages.append(Message.system(system))
        messages.append(Message.user(prompt))
        
        response = self.chat(messages)
        return response.content
    
    def list_providers(self) -> List[str]:
        """列出所有已配置的提供商"""
        return list(self._configs.keys())
    
    def get_active_provider(self) -> Optional[str]:
        """获取当前激活的提供商名称"""
        if self._active_provider:
            return self._active_provider.name
        return None


# 全局 LLM 管理器实例
_llm_manager: Optional[LLMManager] = None


def init_llm_manager() -> LLMManager:
    """初始化全局 LLM 管理器"""
    global _llm_manager
    _llm_manager = LLMManager()
    return _llm_manager


def get_llm_manager() -> LLMManager:
    """获取全局 LLM 管理器"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager
