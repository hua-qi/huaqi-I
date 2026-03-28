"""自适应分析引擎

支持动态维度的统一分析引擎
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

from .schema import (
    SchemaRegistry, DimensionSchema, DimensionValue, DimensionType,
    get_schema_registry
)
from .llm import LLMManager, Message
from .config_paths import get_memory_dir


@dataclass
class AnalysisResult:
    """分析结果"""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    message_id: str = ""
    message_content: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 维度值 - 统一存储
    dimensions: Dict[str, DimensionValue] = field(default_factory=dict)
    
    # 元信息
    analysis_duration_ms: float = 0.0
    llm_calls: int = 0
    
    # 动态发现的新维度提案
    proposed_dimensions: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_dimension(self, dimension_id: str) -> Optional[DimensionValue]:
        """获取指定维度的值"""
        return self.dimensions.get(dimension_id)
    
    def get_dimension_value(self, dimension_id: str) -> Any:
        """获取维度值（仅值）"""
        dim = self.dimensions.get(dimension_id)
        return dim.value if dim else None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "result_id": self.result_id,
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "message_content": self.message_content[:500],
            "timestamp": self.timestamp,
            "dimensions": {
                k: v.to_dict() for k, v in self.dimensions.items()
            },
            "analysis_duration_ms": self.analysis_duration_ms,
            "llm_calls": self.llm_calls,
            "proposed_dimensions": self.proposed_dimensions,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AnalysisResult":
        return cls(
            result_id=data.get("result_id", ""),
            conversation_id=data.get("conversation_id", ""),
            message_id=data.get("message_id", ""),
            message_content=data.get("message_content", ""),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
            dimensions={
                k: DimensionValue.from_dict(v)
                for k, v in data.get("dimensions", {}).items()
            },
            analysis_duration_ms=data.get("analysis_duration_ms", 0),
            llm_calls=data.get("llm_calls", 0),
            proposed_dimensions=data.get("proposed_dimensions", []),
        )


class AdaptiveAnalysisEngine:
    """自适应分析引擎"""
    
    def __init__(
        self,
        llm_manager: Optional[LLMManager] = None,
        schema_registry: Optional[SchemaRegistry] = None,
    ):
        self.llm = llm_manager or LLMManager()
        self.schema = schema_registry or get_schema_registry()
    
    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        # 获取所有启用的维度
        schemas = self.schema.list_enabled()
        schemas.sort(key=lambda x: x.priority, reverse=True)
        
        # 构建维度描述
        dimension_descriptions = []
        for s in schemas:
            if s.extraction_prompt:
                desc = f"- {s.dimension_id}: {s.extraction_prompt}"
                if s.dimension_type == DimensionType.CATEGORY and s.allowed_values:
                    desc += f" 可选值: {', '.join(s.allowed_values)}"
                dimension_descriptions.append(desc)
        
        prompt = f"""你是一个专业的用户理解助手。请分析用户消息，提取多维度的洞察。

## 分析维度
{chr(10).join(dimension_descriptions)}

## 输出格式

请输出 JSON 格式：

{{
  "dimensions": {{
    "维度ID": {{
      "value": 值,
      "confidence": 0.0-1.0,
      "evidence": ["证据引用"]
    }}
  }},
  "proposed_dimensions": [
    {{
      "dimension_name": "新维度名称",
      "dimension_type": "category/score/scale/text/list/boolean",
      "value": 值,
      "confidence": 0.0-1.0,
      "evidence": ["证据"],
      "description": "这个维度描述什么",
      "why_relevant": "为什么这个维度对理解这个用户很重要"
    }}
  ]
}}

## 规则

1. 必须填写所有启用的维度
2. 如果没有明确信息，设置 confidence < 0.5
3. proposed_dimensions 只包含有意义的新发现
4. 不要捏造信息，只基于用户明确表达的内容

## 动态维度发现指南

除了标准维度，请特别观察并发现以下类型的动态维度：

### 1. 行为模式
- 活跃时段：用户通常在什么时间发消息？（晨型人/夜猫子/不规律）
- 回复模式：回复速度快还是慢？消息长还是短？
- 沟通风格：直接还是委婉？开放还是保守？

### 2. 决策模式
- 果断还是犹豫？
- 独立决策还是寻求建议？
- 需要多少信息才能做决定？

### 3. 内容偏好（如果涉及内容交互）
- 对什么话题表现出持续兴趣？
- 喜欢快速浏览还是深入阅读？
- 倾向于保存还是分享？
- 对哪些来源的内容更信任？

### 4. 情绪模式
- 情绪波动大还是稳定？
- 什么情境容易触发特定情绪？
- 情绪恢复速度快还是慢？

发现有意义的行为模式时，请提出为新维度。
"""
        return prompt
    
    async def analyze(
        self,
        message: str,
        conversation_id: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        """
        分析消息
        
        Args:
            message: 用户消息
            conversation_id: 对话ID
            context: 上下文信息
            
        Returns:
            分析结果
        """
        import time
        start_time = time.time()
        
        # 构建提示词
        system_prompt = self._build_system_prompt()
        
        user_prompt = f"""请分析用户消息。

## 上下文
{chr(10).join([f"{k}: {v}" for k, v in (context or {}).items()])}

## 用户消息
{message}
"""
        
        try:
            # 调用 LLM
            response = self.llm.chat([
                Message.system(system_prompt),
                Message.user(user_prompt)
            ])
            
            # 解析结果
            content = self._extract_json(response.content)
            data = json.loads(content)
            
            # 构建分析结果
            result = AnalysisResult(
                conversation_id=conversation_id,
                message_id=str(uuid.uuid4()),
                message_content=message,
            )
            
            # 解析维度值
            for dim_id, dim_data in data.get("dimensions", {}).items():
                result.dimensions[dim_id] = DimensionValue(
                    dimension_id=dim_id,
                    value=dim_data.get("value"),
                    confidence=dim_data.get("confidence", 0.5),
                    evidence=dim_data.get("evidence", []),
                )
            
            # 解析新维度提案
            result.proposed_dimensions = data.get("proposed_dimensions", [])
            
            result.llm_calls = 1
            result.analysis_duration_ms = (time.time() - start_time) * 1000
            
            return result
            
        except Exception as e:
            # 返回空结果
            return AnalysisResult(
                conversation_id=conversation_id,
                message_id=str(uuid.uuid4()),
                message_content=message,
                analysis_duration_ms=(time.time() - start_time) * 1000,
            )
    
    def _extract_json(self, content: str) -> str:
        """提取 JSON"""
        content = content.strip()
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        content = content.strip()
        
        if content.startswith("{") and content.endswith("}"):
            return content
        
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            return content[start:end+1]
        
        return content
    
    def add_dimension(self, schema: DimensionSchema) -> None:
        """动态添加维度"""
        self.schema.register(schema)
    
    def remove_dimension(self, dimension_id: str) -> None:
        """移除维度"""
        self.schema.unregister(dimension_id)
    
    def get_analysis_prompt_addition(self) -> str:
        """获取用于提示词的分析要求"""
        schemas = self.schema.list_enabled()
        schemas.sort(key=lambda x: x.priority, reverse=True)
        
        lines = ["### 用户理解维度"]
        for s in schemas[:10]:  # 最多显示10个
            lines.append(f"- {s.dimension_name}: {s.description}")
        
        return "\n".join(lines)


# 全局引擎
_analysis_engine: Optional[AdaptiveAnalysisEngine] = None


def get_analysis_engine(
    llm_manager: Optional[LLMManager] = None,
    schema_registry: Optional[SchemaRegistry] = None,
) -> AdaptiveAnalysisEngine:
    """获取全局分析引擎"""
    global _analysis_engine
    if _analysis_engine is None:
        _analysis_engine = AdaptiveAnalysisEngine(llm_manager, schema_registry)
    return _analysis_engine
