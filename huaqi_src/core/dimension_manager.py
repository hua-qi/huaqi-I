"""维度管理器

管理动态维度的累积、验证和固化
"""

import json
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field
from collections import defaultdict

from .schema import (
    SchemaRegistry, DimensionSchema, DimensionValue, DimensionType,
    DimensionSource, get_schema_registry
)
from .analysis_engine import AnalysisResult
from .config_paths import get_memory_dir


@dataclass
class DimensionFrequency:
    """维度频次统计"""
    dimension_name: str
    dimension_type: DimensionType
    value_distribution: Dict[str, int] = field(default_factory=dict)
    total_occurrences: int = 0
    first_seen: str = ""
    last_seen: str = ""
    confidence_avg: float = 0.0
    
    def record_occurrence(self, value: Any, confidence: float, timestamp: str):
        """记录一次出现"""
        value_key = str(value)
        self.value_distribution[value_key] = self.value_distribution.get(value_key, 0) + 1
        self.total_occurrences += 1
        
        if not self.first_seen:
            self.first_seen = timestamp
        self.last_seen = timestamp
        
        # 更新平均置信度
        self.confidence_avg = (
            (self.confidence_avg * (self.total_occurrences - 1) + confidence)
            / self.total_occurrences
        )


@dataclass
class PromotionCandidate:
    """待固化的维度候选"""
    dimension_name: str
    dimension_type: DimensionType
    description: str
    frequency: int
    confidence_avg: float
    value_consistency: float  # 值一致性（0-1）
    sample_values: List[Any] = field(default_factory=list)
    reason: str = ""  # 推荐理由


class DimensionManager:
    """维度管理器"""
    
    PROMOTION_THRESHOLD = 5  # 固化阈值：出现次数
    CONSISTENCY_THRESHOLD = 0.6  # 一致性阈值
    
    def __init__(
        self,
        schema_registry: Optional[SchemaRegistry] = None,
        memory_dir: Optional[Path] = None,
    ):
        self.schema = schema_registry or get_schema_registry()
        self.memory_dir = memory_dir or get_memory_dir()
        
        # 动态维度累积
        self._dynamic_frequencies: Dict[str, DimensionFrequency] = defaultdict(
            lambda: DimensionFrequency("", DimensionType.TEXT)
        )
        
        # 已固化的动态维度
        self._promoted_dimensions: set = set()
        
        # 加载历史数据
        self._load_state()
    
    def _get_state_path(self) -> Path:
        """获取状态文件路径"""
        state_dir = self.memory_dir / "dimension_manager"
        state_dir.mkdir(parents=True, exist_ok=True)
        return state_dir / "state.json"
    
    def _load_state(self):
        """加载状态"""
        state_path = self._get_state_path()
        if state_path.exists():
            with open(state_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._promoted_dimensions = set(data.get("promoted", []))
    
    def _save_state(self):
        """保存状态"""
        state_path = self._get_state_path()
        with open(state_path, "w", encoding="utf-8") as f:
            json.dump({
                "promoted": list(self._promoted_dimensions),
                "last_saved": datetime.now().isoformat(),
            }, f, ensure_ascii=False)
    
    def process_proposed_dimensions(self, result: AnalysisResult) -> List[DimensionSchema]:
        """
        处理 LLM 提出的新维度
        
        Returns:
            被固化的维度列表
        """
        promoted = []
        
        for proposal in result.proposed_dimensions:
            dim_name = proposal.get("dimension_name", "")
            dim_type_str = proposal.get("dimension_type", "text")
            value = proposal.get("value")
            confidence = proposal.get("confidence", 0.5)
            
            if not dim_name:
                continue
            
            # 转换为标准类型
            try:
                dim_type = DimensionType(dim_type_str)
            except ValueError:
                dim_type = DimensionType.TEXT
            
            # 记录频次
            if dim_name not in self._dynamic_frequencies:
                self._dynamic_frequencies[dim_name] = DimensionFrequency(
                    dimension_name=dim_name,
                    dimension_type=dim_type,
                )
            
            freq = self._dynamic_frequencies[dim_name]
            freq.record_occurrence(value, confidence, result.timestamp)
            
            # 检查是否应该固化
            if self._should_promote(dim_name, freq):
                schema = self._promote_dimension(dim_name, freq, proposal)
                if schema:
                    promoted.append(schema)
        
        if promoted:
            self._save_state()
        
        return promoted
    
    def _should_promote(self, dim_name: str, freq: DimensionFrequency) -> bool:
        """判断是否应固化维度"""
        # 已经固化过
        if dim_name in self._promoted_dimensions:
            return False
        
        # 频次不足
        if freq.total_occurrences < self.PROMOTION_THRESHOLD:
            return False
        
        # 置信度不足
        if freq.confidence_avg < 0.5:
            return False
        
        # 检查值一致性（CATEGORY类型）
        if freq.dimension_type == DimensionType.CATEGORY:
            if freq.value_distribution:
                max_count = max(freq.value_distribution.values())
                consistency = max_count / freq.total_occurrences
                if consistency < self.CONSISTENCY_THRESHOLD:
                    return False
        
        return True
    
    def _promote_dimension(
        self,
        dim_name: str,
        freq: DimensionFrequency,
        proposal: Dict[str, Any],
    ) -> Optional[DimensionSchema]:
        """固化维度为标准维度"""
        
        dim_id = f"dynamic.{dim_name.lower().replace(' ', '_')}"
        
        # 检查是否已存在
        if self.schema.get(dim_id):
            return None
        
        # 构建 allowed_values（CATEGORY类型）
        allowed_values = None
        if freq.dimension_type == DimensionType.CATEGORY and freq.value_distribution:
            allowed_values = list(freq.value_distribution.keys())
        
        # 创建 Schema
        schema = DimensionSchema(
            dimension_id=dim_id,
            dimension_name=dim_name,
            dimension_type=freq.dimension_type,
            description=proposal.get("description", f"动态发现的维度：{dim_name}"),
            allowed_values=allowed_values,
            source=DimensionSource.PROMOTED,
            extraction_prompt=f"用户{dim_name}是什么？",
            priority=5,
        )
        
        # 注册
        self.schema.register(schema)
        self._promoted_dimensions.add(dim_name)
        
        print(f"[DimensionManager] 维度已固化: {dim_name} -> {dim_id}")
        
        return schema
    
    def get_promotion_candidates(self, min_frequency: int = 3) -> List[PromotionCandidate]:
        """获取候选固化的维度"""
        candidates = []
        
        for dim_name, freq in self._dynamic_frequencies.items():
            if dim_name in self._promoted_dimensions:
                continue
            
            if freq.total_occurrences < min_frequency:
                continue
            
            # 计算值一致性
            consistency = 0.0
            if freq.value_distribution:
                max_count = max(freq.value_distribution.values())
                consistency = max_count / freq.total_occurrences
            
            candidates.append(PromotionCandidate(
                dimension_name=dim_name,
                dimension_type=freq.dimension_type,
                description=f"动态发现的维度，共出现 {freq.total_occurrences} 次",
                frequency=freq.total_occurrences,
                confidence_avg=freq.confidence_avg,
                value_consistency=consistency,
                sample_values=list(freq.value_distribution.keys())[:5],
                reason=f"出现 {freq.total_occurrences} 次，平均置信度 {freq.confidence_avg:.2f}",
            ))
        
        # 按频次排序
        candidates.sort(key=lambda x: x.frequency, reverse=True)
        return candidates
    
    def manually_promote_dimension(
        self,
        dim_name: str,
        dim_type: DimensionType = DimensionType.TEXT,
        description: str = "",
    ) -> Optional[DimensionSchema]:
        """手动固化维度"""
        dim_id = f"dynamic.{dim_name.lower().replace(' ', '_')}"
        
        schema = DimensionSchema(
            dimension_id=dim_id,
            dimension_name=dim_name,
            dimension_type=dim_type,
            description=description or f"手动固化的维度：{dim_name}",
            source=DimensionSource.PROMOTED,
            priority=5,
        )
        
        self.schema.register(schema)
        self._promoted_dimensions.add(dim_name)
        self._save_state()
        
        return schema
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            "total_dynamic_discovered": len(self._dynamic_frequencies),
            "total_promoted": len(self._promoted_dimensions),
            "promotion_candidates": len(self.get_promotion_candidates()),
            "system_dimensions": len(self.schema.list_by_type(DimensionSource.SYSTEM)),
            "promoted_dimensions": len(self.schema.list_by_type(DimensionSource.PROMOTED)),
        }
    
    def reset(self):
        """重置所有动态维度"""
        self._dynamic_frequencies.clear()
        self._promoted_dimensions.clear()
        
        # 注销所有 PROMOTED 维度
        for schema in self.schema.list_by_type(DimensionSource.PROMOTED):
            self.schema.unregister(schema.dimension_id)
        
        self._save_state()


# 全局管理器
_dimension_manager: Optional[DimensionManager] = None


def get_dimension_manager(
    schema_registry: Optional[SchemaRegistry] = None,
    memory_dir: Optional[Path] = None,
) -> DimensionManager:
    """获取全局维度管理器"""
    global _dimension_manager
    if _dimension_manager is None:
        _dimension_manager = DimensionManager(schema_registry, memory_dir)
    return _dimension_manager
