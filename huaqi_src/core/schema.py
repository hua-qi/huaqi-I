"""动态 Schema 定义系统

支持声明式、可扩展的维度定义
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable, Type
from enum import Enum
import json


class DimensionType(str, Enum):
    """维度数据类型"""
    CATEGORY = "category"       # 枚举值
    SCORE = "score"            # 0-1 分数
    SCALE = "scale"            # 1-10 量表
    TEXT = "text"              # 文本描述
    LIST = "list"              # 列表
    BOOLEAN = "boolean"        # 布尔值
    JSON = "json"              # 任意 JSON


class DimensionSource(str, Enum):
    """维度来源"""
    SYSTEM = "system"          # 系统内置
    DYNAMIC = "dynamic"        # 动态发现
    PROMOTED = "promoted"      # 动态提升为系统维度


@dataclass
class DimensionSchema:
    """维度 Schema 定义"""
    
    dimension_id: str
    dimension_name: str
    dimension_type: DimensionType
    description: str
    
    # 可选值（CATEGORY 类型用）
    allowed_values: Optional[List[str]] = None
    
    # 验证规则
    validation_rules: Dict[str, Any] = field(default_factory=dict)
    
    # 元数据
    source: DimensionSource = DimensionSource.SYSTEM
    version: int = 1
    created_at: str = field(default_factory=lambda: __import__('datetime').datetime.now().isoformat())
    
    # LLM 提取提示词片段
    extraction_prompt: str = ""
    
    # 是否启用
    is_enabled: bool = True
    
    # 优先级（影响 LLM 关注程度）
    priority: int = 5  # 1-10
    
    def validate(self, value: Any) -> bool:
        """验证值是否符合 schema"""
        if value is None:
            return True
        
        if self.dimension_type == DimensionType.CATEGORY:
            if self.allowed_values and value not in self.allowed_values:
                return False
        
        elif self.dimension_type == DimensionType.SCORE:
            if not isinstance(value, (int, float)) or not 0 <= value <= 1:
                return False
        
        elif self.dimension_type == DimensionType.SCALE:
            if not isinstance(value, int) or not 1 <= value <= 10:
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension_id": self.dimension_id,
            "dimension_name": self.dimension_name,
            "dimension_type": self.dimension_type.value,
            "description": self.description,
            "allowed_values": self.allowed_values,
            "validation_rules": self.validation_rules,
            "source": self.source.value,
            "version": self.version,
            "created_at": self.created_at,
            "extraction_prompt": self.extraction_prompt,
            "is_enabled": self.is_enabled,
            "priority": self.priority,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DimensionSchema":
        return cls(
            dimension_id=data["dimension_id"],
            dimension_name=data["dimension_name"],
            dimension_type=DimensionType(data["dimension_type"]),
            description=data["description"],
            allowed_values=data.get("allowed_values"),
            validation_rules=data.get("validation_rules", {}),
            source=DimensionSource(data.get("source", "system")),
            version=data.get("version", 1),
            created_at=data.get("created_at", ""),
            extraction_prompt=data.get("extraction_prompt", ""),
            is_enabled=data.get("is_enabled", True),
            priority=data.get("priority", 5),
        )


class SchemaRegistry:
    """Schema 注册表 - 管理所有维度定义"""
    
    def __init__(self):
        self._schemas: Dict[str, DimensionSchema] = {}
        self._listeners: List[Callable[[str, DimensionSchema], None]] = []
    
    def register(self, schema: DimensionSchema) -> None:
        """注册维度 Schema"""
        self._schemas[schema.dimension_id] = schema
        
        # 通知监听器
        for listener in self._listeners:
            try:
                listener("registered", schema)
            except Exception:
                pass
    
    def unregister(self, dimension_id: str) -> None:
        """注销维度 Schema"""
        if dimension_id in self._schemas:
            schema = self._schemas.pop(dimension_id)
            for listener in self._listeners:
                try:
                    listener("unregistered", schema)
                except Exception:
                    pass
    
    def get(self, dimension_id: str) -> Optional[DimensionSchema]:
        """获取维度 Schema"""
        return self._schemas.get(dimension_id)
    
    def list_all(self) -> List[DimensionSchema]:
        """列出所有 Schema"""
        return list(self._schemas.values())
    
    def list_enabled(self) -> List[DimensionSchema]:
        """列出启用的 Schema"""
        return [s for s in self._schemas.values() if s.is_enabled]
    
    def list_by_type(self, source: DimensionSource) -> List[DimensionSchema]:
        """按来源列出 Schema"""
        return [s for s in self._schemas.values() if s.source == source]
    
    def list_by_priority(self, min_priority: int = 1) -> List[DimensionSchema]:
        """按优先级列出 Schema"""
        return [
            s for s in self._schemas.values() 
            if s.priority >= min_priority and s.is_enabled
        ]
    
    def add_listener(self, listener: Callable[[str, DimensionSchema], None]) -> None:
        """添加 Schema 变更监听器"""
        self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[str, DimensionSchema], None]) -> None:
        """移除监听器"""
        if listener in self._listeners:
            self._listeners.remove(listener)
    
    def save_to_file(self, path: str) -> None:
        """保存 Schema 到文件"""
        data = {
            "version": 1,
            "schemas": [s.to_dict() for s in self._schemas.values()]
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def load_from_file(self, path: str) -> None:
        """从文件加载 Schema"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        for schema_data in data.get("schemas", []):
            schema = DimensionSchema.from_dict(schema_data)
            self.register(schema)


# 全局 Schema 注册表
_schema_registry: Optional[SchemaRegistry] = None


def get_schema_registry() -> SchemaRegistry:
    """获取全局 Schema 注册表"""
    global _schema_registry
    if _schema_registry is None:
        _schema_registry = SchemaRegistry()
        _register_builtin_schemas()
    return _schema_registry


def _register_builtin_schemas():
    """注册内置维度 Schema"""
    registry = get_schema_registry()
    
    # 情绪维度
    registry.register(DimensionSchema(
        dimension_id="emotion.primary",
        dimension_name="主导情绪",
        dimension_type=DimensionType.CATEGORY,
        description="用户当前的主导情绪",
        allowed_values=[
            "happy", "sad", "anxious", "angry", "excited",
            "tired", "neutral", "confused", "grateful", "hopeful",
            "frustrated", "lonely", "proud", "guilty"
        ],
        extraction_prompt="用户当前的主导情绪是什么？",
        priority=10,
    ))
    
    registry.register(DimensionSchema(
        dimension_id="emotion.intensity",
        dimension_name="情绪强度",
        dimension_type=DimensionType.SCALE,
        description="情绪的强烈程度",
        extraction_prompt="情绪强度 1-10？",
        priority=9,
    ))
    
    # 意图维度
    registry.register(DimensionSchema(
        dimension_id="intent.surface",
        dimension_name="表面意图",
        dimension_type=DimensionType.TEXT,
        description="用户表面上在做什么",
        extraction_prompt="用户表面上在做什么？",
        priority=9,
    ))
    
    registry.register(DimensionSchema(
        dimension_id="intent.deep",
        dimension_name="深层意图",
        dimension_type=DimensionType.TEXT,
        description="用户真正想要什么",
        extraction_prompt="用户真正想要什么？",
        priority=9,
    ))
    
    # 话题维度
    registry.register(DimensionSchema(
        dimension_id="topics",
        dimension_name="话题",
        dimension_type=DimensionType.LIST,
        description="用户提及的话题",
        extraction_prompt="用户提及了哪些话题？",
        priority=7,
    ))
    
    # 立场维度
    registry.register(DimensionSchema(
        dimension_id="stances",
        dimension_name="立场",
        dimension_type=DimensionType.JSON,
        description="用户对不同话题的立场",
        extraction_prompt="用户对不同话题持什么立场？",
        priority=6,
    ))
    
    # 事实维度
    registry.register(DimensionSchema(
        dimension_id="facts",
        dimension_name="事实",
        dimension_type=DimensionType.JSON,
        description="从消息中提取的事实信息",
        extraction_prompt="从消息中提取哪些事实？",
        priority=7,
    ))
    
    # ===== 内容偏好维度 =====
    registry.register(DimensionSchema(
        dimension_id="content.topic_interest",
        dimension_name="内容话题兴趣",
        dimension_type=DimensionType.LIST,
        description="用户对哪些话题的内容表现出兴趣",
        extraction_prompt="用户对哪些话题的内容表现出兴趣？",
        priority=6,
    ))
    
    registry.register(DimensionSchema(
        dimension_id="content.depth_preference",
        dimension_name="内容深度偏好",
        dimension_type=DimensionType.CATEGORY,
        description="用户喜欢快速浏览还是深入阅读",
        allowed_values=["浅层速览", "中等深度", "深度阅读", "视情况"],
        extraction_prompt="用户喜欢快速浏览还是深入阅读？",
        priority=5,
    ))
    
    registry.register(DimensionSchema(
        dimension_id="content.sharing_tendency",
        dimension_name="内容分享倾向",
        dimension_type=DimensionType.SCORE,
        description="用户有多强的内容分享意愿",
        extraction_prompt="用户有多强的内容分享意愿（0-1）？",
        priority=5,
    ))
    
    registry.register(DimensionSchema(
        dimension_id="content.source_trust",
        dimension_name="内容来源信任度",
        dimension_type=DimensionType.JSON,
        description="用户对不同内容来源的信任程度",
        extraction_prompt="用户更信任哪些内容来源？",
        priority=4,
    ))
    
    registry.register(DimensionSchema(
        dimension_id="content.language_preference",
        dimension_name="内容语言偏好",
        dimension_type=DimensionType.CATEGORY,
        description="用户偏好中文原创还是英文翻译内容",
        allowed_values=["中文原创", "英文原文", "中英文均可", "视内容而定"],
        extraction_prompt="用户偏好中文还是英文内容？",
        priority=4,
    ))


class DimensionValue:
    """维度值"""
    
    def __init__(
        self,
        dimension_id: str,
        value: Any,
        confidence: float = 1.0,
        evidence: Optional[List[str]] = None,
        timestamp: Optional[str] = None,
    ):
        self.dimension_id = dimension_id
        self.value = value
        self.confidence = confidence
        self.evidence = evidence or []
        self.timestamp = timestamp or __import__('datetime').datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "dimension_id": self.dimension_id,
            "value": self.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DimensionValue":
        return cls(
            dimension_id=data["dimension_id"],
            value=data["value"],
            confidence=data.get("confidence", 1.0),
            evidence=data.get("evidence", []),
            timestamp=data.get("timestamp"),
        )
