"""自适应用户理解系统 - 统一门面

整合：
- Schema 管理
- 自适应分析引擎
- 维度管理器（累积与固化）
- 灵活存储

这是新架构的统一入口
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from .llm import LLMManager, get_llm_manager
from .schema import SchemaRegistry, DimensionSchema, get_schema_registry
from .analysis_engine import AnalysisResult, AdaptiveAnalysisEngine, get_analysis_engine
from .dimension_manager import DimensionManager, get_dimension_manager
from .flexible_store import FlexibleStore, get_flexible_store, ContentInteractionEvent
from .deep_analysis import DeepAnalyzer, DeepAnalysisResult, DeepAnalysisScheduler
from .proactive_exploration import (
    ProactiveExplorationEngine, ExplorationOpportunity, MessageGenerator, get_exploration_engine
)
from .config_paths import get_memory_dir


class AdaptiveUserUnderstanding:
    """自适应用户理解系统
    
    支持动态维度的完整用户理解解决方案
    """
    
    def __init__(
        self,
        llm_manager: Optional[LLMManager] = None,
        memory_dir: Optional[Path] = None,
    ):
        self.memory_dir = memory_dir or get_memory_dir()
        
        # 初始化各组件
        self.llm = llm_manager or get_llm_manager()
        self.schema = get_schema_registry()
        self.engine = get_analysis_engine(self.llm, self.schema)
        self.dim_manager = get_dimension_manager(self.schema, self.memory_dir)
        self.store = get_flexible_store(self.memory_dir)
        
        # 注册 Schema 变更监听器
        self.schema.add_listener(self._on_schema_change)
    
    def _on_schema_change(self, event: str, schema: DimensionSchema):
        """Schema 变更回调"""
        if event == "registered":
            print(f"[AdaptiveUnderstanding] 新维度注册: {schema.dimension_name}")
        elif event == "unregistered":
            print(f"[AdaptiveUnderstanding] 维度注销: {schema.dimension_name}")
    
    async def analyze(
        self,
        message: str,
        conversation_id: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> AnalysisResult:
        """
        分析用户消息
        
        完整流程：
        1. 使用当前 Schema 分析消息
        2. 处理 LLM 提出的新维度
        3. 保存结果
        4. 检查是否有维度需要固化
        
        Returns:
            分析结果
        """
        # 1. 分析消息
        result = await self.engine.analyze(
            message=message,
            conversation_id=conversation_id,
            context=context,
        )
        
        # 2. 处理新维度提案
        if result.proposed_dimensions:
            promoted = self.dim_manager.process_proposed_dimensions(result)
            if promoted:
                print(f"[AdaptiveUnderstanding] 本次固化了 {len(promoted)} 个新维度")
        
        # 3. 保存结果
        self.store.save_result(result)
        
        return result
    
    def get_context_for_response(
        self,
        current_result: Optional[AnalysisResult] = None,
    ) -> str:
        """
        获取用于回复生成的上下文
        """
        parts = []
        
        # 1. 当前分析结果
        if current_result:
            dim_context = self._format_dimensions_for_prompt(current_result)
            if dim_context:
                parts.append(dim_context)
        
        # 2. 历史模式（最近几次分析的聚合）
        recent_results = self.store.get_results(days=7, limit=10)
        if recent_results:
            pattern_context = self._format_pattern_for_prompt(recent_results)
            if pattern_context:
                parts.append(pattern_context)
        
        return "\n\n".join(parts) if parts else ""
    
    def _format_dimensions_for_prompt(self, result: AnalysisResult) -> str:
        """格式化维度为提示词"""
        lines = ["### 当前分析"]
        
        # 高置信度的维度
        for dim_id, dim_value in result.dimensions.items():
            if dim_value.confidence < 0.6:
                continue
            
            schema = self.schema.get(dim_id)
            if not schema:
                continue
            
            if dim_id == "emotion.primary":
                lines.append(f"- 情绪：{dim_value.value}（强度{result.get_dimension_value('emotion.intensity') or 5}）")
            elif dim_id == "intent.deep":
                lines.append(f"- 可能需要：{dim_value.value}")
            elif dim_id == "topics":
                topics = dim_value.value if isinstance(dim_value.value, list) else [dim_value.value]
                if topics:
                    lines.append(f"- 话题：{', '.join(str(t) for t in topics[:3])}")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def _format_pattern_for_prompt(self, results: List[AnalysisResult]) -> str:
        """格式化模式为提示词"""
        lines = ["### 近期模式"]
        
        # 情绪趋势
        emotions = [r.get_dimension_value("emotion.primary") for r in results if r.get_dimension("emotion.primary")]
        if emotions:
            recent_emotions = emotions[:5]
            lines.append(f"- 最近情绪：{', '.join(str(e) for e in recent_emotions)}")
        
        # 持续话题
        all_topics = []
        for r in results:
            topics = r.get_dimension_value("topics") or []
            if isinstance(topics, list):
                all_topics.extend(topics)
        
        from collections import Counter
        topic_counts = Counter(all_topics)
        recurring = [t for t, c in topic_counts.items() if c >= 2]
        if recurring:
            lines.append(f"- 持续关注：{', '.join(str(t) for t in recurring[:3])}")
        
        return "\n".join(lines) if len(lines) > 1 else ""
    
    def add_custom_dimension(
        self,
        dimension_name: str,
        dimension_type: str = "text",
        description: str = "",
    ) -> DimensionSchema:
        """
        手动添加自定义维度
        """
        from .schema import DimensionType
        
        dim_id = f"custom.{dimension_name.lower().replace(' ', '_')}"
        
        schema = DimensionSchema(
            dimension_id=dim_id,
            dimension_name=dimension_name,
            dimension_type=DimensionType(dimension_type),
            description=description or f"自定义维度：{dimension_name}",
            extraction_prompt=f"用户{dimension_name}是什么？",
        )
        
        self.schema.register(schema)
        return schema
    
    def get_promotion_candidates(self) -> List[Dict[str, Any]]:
        """
        获取候选固化的维度
        """
        candidates = self.dim_manager.get_promotion_candidates()
        return [
            {
                "dimension_name": c.dimension_name,
                "dimension_type": c.dimension_type.value,
                "frequency": c.frequency,
                "confidence_avg": round(c.confidence_avg, 2),
                "value_consistency": round(c.value_consistency, 2),
                "sample_values": c.sample_values,
                "reason": c.reason,
            }
            for c in candidates
        ]
    
    def manually_promote_dimension(self, dimension_name: str) -> Optional[DimensionSchema]:
        """
        手动固化维度
        """
        from .schema import DimensionType
        return self.dim_manager.manually_promote_dimension(
            dimension_name,
            DimensionType.TEXT,
        )
    
    def get_dimension_statistics(
        self,
        dimension_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        获取维度统计
        """
        return self.store.get_dimension_statistics(dimension_id, days)
    
    def query_by_dimension(
        self,
        dimension_id: str,
        value: Any,
        days: int = 30,
    ) -> List[AnalysisResult]:
        """
        按维度值查询历史
        """
        return self.store.query_by_dimension(dimension_id, value, days)
    
    def search_history(
        self,
        query: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        语义搜索历史
        """
        return self.store.search_by_text(query, top_k)
    
    def get_system_status(self) -> Dict[str, Any]:
        """
        获取系统状态
        """
        return {
            "registered_dimensions": len(self.schema.list_all()),
            "enabled_dimensions": len(self.schema.list_enabled()),
            "dynamic_discovered": self.dim_manager.get_statistics()["total_dynamic_discovered"],
            "promoted_dimensions": self.dim_manager.get_statistics()["total_promoted"],
            "promotion_candidates": len(self.get_promotion_candidates()),
        }
    
    def reset_dynamic_dimensions(self):
        """
        重置所有动态维度
        """
        self.dim_manager.reset()
        print("[AdaptiveUnderstanding] 动态维度已重置")

    # ===== 深度分析方法 =====

    async def deep_analyze(
        self,
        days: int = 30,
    ) -> Optional[DeepAnalysisResult]:
        """
        执行深度分析

        Args:
            days: 分析天数范围

        Returns:
            深度分析结果
        """
        analyzer = DeepAnalyzer(self.llm)
        return await analyzer.analyze(days)

    def get_deep_insights_for_prompt(self) -> str:
        """
        获取深度洞察用于回复生成
        """
        scheduler = DeepAnalysisScheduler(self.memory_dir)
        latest = scheduler.get_latest_analysis()

        if not latest:
            return ""

        return latest.get_context_for_prompt()

    def should_run_deep_analysis(self) -> bool:
        """判断是否应该运行深度分析"""
        scheduler = DeepAnalysisScheduler(self.memory_dir)
        return scheduler.should_trigger()

    # ===== 内容交互方法 =====

    def record_content_interaction(
        self,
        content_id: str,
        source: str,
        title: str,
        url: str,
        topics: List[str],
        actions: List[str],
        user_rating: Optional[int] = None,
        user_comment: str = "",
    ) -> None:
        """
        记录内容交互事件
        
        Args:
            content_id: 内容ID
            source: 来源 (x/twitter/rss)
            title: 内容标题
            url: 内容链接
            topics: 内容话题标签
            actions: 用户行为 [viewed, summarized, translated, saved, shared, skipped]
            user_rating: 用户评分 1-5
            user_comment: 用户评论
        """
        event = ContentInteractionEvent(
            content_id=content_id,
            source=source,
            title=title,
            url=url,
            topics=topics,
            actions=actions,
            user_rating=user_rating,
            user_comment=user_comment,
        )
        self.store.record_content_interaction(event)

    def get_content_interactions(
        self,
        days: int = 30,
        source: Optional[str] = None,
    ) -> List[ContentInteractionEvent]:
        """获取内容交互历史"""
        return self.store.get_content_interactions(days, source)

    def get_content_interaction_stats(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """获取内容交互统计"""
        return self.store.get_content_interaction_stats(days)

    def analyze_content_preference(
        self,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        分析用户内容偏好（基于交互历史）

        返回分析结果，可用于更新维度
        """
        stats = self.get_content_interaction_stats(days)

        # 提取高兴趣话题
        top_topics = [t[0] for t in stats.get("topic_distribution", [])[:5]]

        # 判断深度偏好
        actions = stats.get("action_distribution", {})
        summarized_count = actions.get("summarized", 0)
        viewed_count = actions.get("viewed", 0)
        skipped_count = actions.get("skipped", 0)

        depth_preference = "视情况"
        if summarized_count > viewed_count * 0.5:
            depth_preference = "深度阅读"
        elif skipped_count > viewed_count * 0.3:
            depth_preference = "浅层速览"
        else:
            depth_preference = "中等深度"

        # 计算分享倾向
        shared_count = actions.get("shared", 0)
        total_interactions = stats.get("total", 1)
        sharing_tendency = shared_count / total_interactions

        return {
            "top_topics": top_topics,
            "depth_preference": depth_preference,
            "sharing_tendency": round(sharing_tendency, 2),
            "source_preference": list(stats.get("source_distribution", {}).keys()),
            "avg_rating": stats.get("avg_rating", 0),
        }

    # ===== 主动探索方法 =====

    async def check_proactive_opportunities(
        self,
        minutes_since_last_interaction: int = 0,
    ) -> Optional[ExplorationOpportunity]:
        """
        检查主动探索机会

        Args:
            minutes_since_last_interaction: 距离上次互动的分钟数

        Returns:
            探索机会或 None
        """
        engine = get_exploration_engine()

        # 获取所有机会
        opportunities = await engine.detect_opportunities()

        if not opportunities:
            return None

        # 筛选合适的时机
        for opp in opportunities:
            if engine.should_trigger_now(opp, minutes_since_last_interaction):
                return opp

        return None

    async def generate_proactive_message(
        self,
        opportunity: ExplorationOpportunity,
    ) -> str:
        """
        生成主动消息

        Args:
            opportunity: 探索机会

        Returns:
            生成的消息
        """
        # 获取用户上下文
        context = self._get_user_context_for_proactive()

        # 生成消息
        generator = MessageGenerator(self.llm)
        message = await generator.generate(opportunity, context)

        # 记录生成的消息
        opportunity.generated_message = message

        return message

    def _get_user_context_for_proactive(self) -> Dict[str, Any]:
        """获取用于主动探索的用户上下文"""
        context = {}

        # 最新分析
        results = self.store.get_results(days=1, limit=1)
        if results:
            latest = results[0]
            context["recent_emotion"] = latest.get_dimension_value("emotion.primary")
            context["recent_topics"] = latest.get_dimension_value("topics")

        # 深度分析
        scheduler = DeepAnalysisScheduler(self.memory_dir)
        deep = scheduler.get_latest_analysis()
        if deep:
            context["emotional_trend"] = deep.emotional_trajectory.overall_trend
            context["active_topics"] = [t.topic for t in deep.topic_evolution if t.is_active]
            context["core_values"] = [v.name for v in deep.value_inference[:2]]

        # 问候语
        generator = MessageGenerator()
        context["greeting"] = generator._get_greeting()

        return context

    def mark_proactive_executed(
        self,
        opportunity: ExplorationOpportunity,
    ) -> None:
        """标记主动探索已执行"""
        engine = get_exploration_engine()
        engine.mark_executed(opportunity)

    def evaluate_proactive_response(
        self,
        opportunity: ExplorationOpportunity,
        user_response: str,
    ) -> bool:
        """
        评估用户回应是否积极

        Returns:
            True if positive
        """
        engine = get_exploration_engine()
        return engine.evaluate_response(opportunity, user_response)


# 全局实例
_adaptive_understanding: Optional[AdaptiveUserUnderstanding] = None


def get_adaptive_understanding(
    llm_manager: Optional[LLMManager] = None,
    memory_dir: Optional[Path] = None,
) -> AdaptiveUserUnderstanding:
    """获取全局自适应用户理解系统"""
    global _adaptive_understanding
    if _adaptive_understanding is None:
        _adaptive_understanding = AdaptiveUserUnderstanding(llm_manager, memory_dir)
    return _adaptive_understanding


def init_adaptive_understanding(
    llm_manager: LLMManager,
    memory_dir: Optional[Path] = None,
) -> AdaptiveUserUnderstanding:
    """初始化全局自适应用户理解系统"""
    global _adaptive_understanding
    _adaptive_understanding = AdaptiveUserUnderstanding(llm_manager, memory_dir)
    return _adaptive_understanding
