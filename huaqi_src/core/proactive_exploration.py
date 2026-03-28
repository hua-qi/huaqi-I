"""主动探索机制（单用户版本）

基于多维用户理解的智能触发系统
- 实时信号检测（情绪、话题）
- 深度分析信号（趋势、成长）
- 维度变化检测
- 内容交互信号
- 时间触发
"""

import json
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

from .analysis_engine import AnalysisResult
from .deep_analysis import DeepAnalysisResult, DeepAnalysisScheduler, EmotionalTrajectory
from .flexible_store import get_flexible_store
from .llm import LLMManager, Message


class ExplorationTrigger(str, Enum):
    """探索触发类型"""
    # 基于实时分析
    EMOTION_ALERT = "emotion_alert"           # 情绪异常
    TOPIC_FOLLOWUP = "topic_followup"         # 话题跟进
    
    # 基于深度分析  
    TREND_CELEBRATION = "trend_celebration"   # 趋势庆祝
    GROWTH_RECOGNITION = "growth_recognition" # 成长认可
    CONCERN_CHECKIN = "concern_checkin"       # 关心检查
    
    # 基于维度变化
    NEW_DIMENSION = "new_dimension"           # 新维度发现
    DIMENSION_CHANGE = "dimension_change"     # 维度值变化
    
    # 基于内容
    CONTENT_RECOMMENDATION = "content_recommend"  # 内容推荐
    CONTENT_FOLLOWUP = "content_followup"     # 内容跟进
    
    # 基于时间
    SCHEDULED_REVIEW = "scheduled_review"     # 定期回顾
    MILESTONE_REMINDER = "milestone_reminder" # 里程碑提醒


@dataclass
class ExplorationOpportunity:
    """探索机会"""
    opportunity_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    trigger_type: ExplorationTrigger = ExplorationTrigger.SCHEDULED_REVIEW
    priority: int = 5  # 1-10
    
    # 消息内容
    suggested_message: str = ""           # 建议消息模板
    generated_message: str = ""           # LLM生成的最终消息
    
    # 上下文
    context: Dict[str, Any] = field(default_factory=dict)
    
    # 时间控制
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    expires_at: str = ""                  # 过期时间
    min_interval_minutes: int = 60        # 最小触发间隔
    
    # 状态
    is_executed: bool = False
    executed_at: Optional[str] = None
    user_response: Optional[str] = None
    response_evaluated: Optional[bool] = None  # 用户回应是否积极
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "trigger_type": self.trigger_type.value,
            "priority": self.priority,
            "suggested_message": self.suggested_message,
            "generated_message": self.generated_message,
            "context": self.context,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "min_interval_minutes": self.min_interval_minutes,
            "is_executed": self.is_executed,
            "executed_at": self.executed_at,
            "user_response": self.user_response,
            "response_evaluated": self.response_evaluated,
        }


class MessageGenerator:
    """消息生成器"""
    
    # 预定义模板（快速响应）
    TEMPLATES = {
        ExplorationTrigger.EMOTION_ALERT: [
            "最近感觉你有点{emotion}，想聊聊吗？我在这里听着呢 🤗",
            "注意到你似乎有些{emotion}，要不要说说发生了什么？",
            "感觉你最近状态不太对，需要陪聊吗？",
        ],
        ExplorationTrigger.TOPIC_FOLLOWUP: [
            "上次你说的{topic}，后来怎么样了？",
            "想跟进一下{topic}的情况，有什么进展吗？",
            "一直记得你说的{topic}，现在还好吗？",
        ],
        ExplorationTrigger.TREND_CELEBRATION: [
            "我注意到你最近{aspect}有改善，是发生了什么积极的变化吗？😊",
            "看到你的{trend}，真为你开心！想听听你的故事",
            "最近感觉你状态不错，继续保持！💪",
        ],
        ExplorationTrigger.GROWTH_RECOGNITION: [
            "看到你最近在{area}的进步，真为你骄傲！🎉",
            "注意到你的成长，想听听你是怎么做到的？",
            "你的改变让我印象深刻，想聊聊这个转变吗？",
        ],
        ExplorationTrigger.CONCERN_CHECKIN: [
            "之前你说{concern}，现在还好吗？",
            "一直想着你说的{topic}，有什么我可以支持的吗？",
            "关心一下你最近的状态，需要聊聊吗？",
        ],
        ExplorationTrigger.SCHEDULED_REVIEW: [
            "{greeting}！想和你回顾一下最近的进展，有什么想分享的吗？",
            "{greeting}！想听听你最近怎么样，有什么新鲜事吗？",
        ],
        ExplorationTrigger.CONTENT_RECOMMENDATION: [
            "看到你对{topic}感兴趣，推荐你这篇内容，可能会喜欢 📖",
            "基于你关注的{topic}，找到这个内容，想听听你的看法",
        ],
    }
    
    def __init__(self, llm_manager: Optional[LLMManager] = None):
        self.llm = llm_manager or LLMManager()
    
    async def generate(
        self,
        opportunity: ExplorationOpportunity,
        user_context: Dict[str, Any]
    ) -> str:
        """
        生成个性化主动消息
        """
        # 简单情况使用模板
        if opportunity.priority >= 8:  # 高优先级用LLM生成更自然
            return await self._generate_with_llm(opportunity, user_context)
        else:
            return self._generate_from_template(opportunity, user_context)
    
    def _generate_from_template(
        self,
        opportunity: ExplorationOpportunity,
        context: Dict[str, Any]
    ) -> str:
        """从模板生成消息"""
        import random
        
        templates = self.TEMPLATES.get(opportunity.trigger_type, ["想和你聊聊 😊"])
        template = random.choice(templates)
        
        # 填充变量
        message = template.format(**context)
        return message
    
    async def _generate_with_llm(
        self,
        opportunity: ExplorationOpportunity,
        context: Dict[str, Any]
    ) -> str:
        """使用LLM生成消息"""
        
        prompt = f"""生成一条温暖、自然的主动关心消息。

场景：{opportunity.trigger_type.value}
建议方向：{opportunity.suggested_message}

用户上下文：
{json.dumps(context, ensure_ascii=False, indent=2)}

要求：
1. 语气像朋友一样自然、温暖
2. 不要太正式或机械
3. 给对方留出回应空间（用问句或开放式表达）
4. 适当使用 emoji 增加亲和力
5. 长度适中（2-4句话，不超过100字）
6. 如果是关心类消息，要表达真诚而非敷衍

直接输出消息内容，不要其他说明。"""
        
        try:
            response = self.llm.chat([
                Message.system("你是温暖贴心的AI伙伴，擅长自然的人际沟通。"),
                Message.user(prompt)
            ])
            
            message = response.content.strip()
            
            # 清理可能的引号
            if message.startswith('"') and message.endswith('"'):
                message = message[1:-1]
            
            return message
            
        except Exception as e:
            # LLM失败回退到模板
            return self._generate_from_template(opportunity, context)
    
    def _get_greeting(self) -> str:
        """根据时间获取问候语"""
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "早上好"
        elif 12 <= hour < 14:
            return "中午好"
        elif 14 <= hour < 18:
            return "下午好"
        elif 18 <= hour < 22:
            return "晚上好"
        else:
            return "夜深了"


class ProactiveExplorationEngine:
    """主动探索引擎"""
    
    def __init__(self):
        self.store = get_flexible_store()
        self.scheduler = DeepAnalysisScheduler()
        self.message_gen = MessageGenerator()
        
        # 记录上次触发时间（避免频繁打扰）
        self._last_trigger_time: Optional[datetime] = None
        self._executed_opportunities: List[str] = []
    
    async def detect_opportunities(self) -> List[ExplorationOpportunity]:
        """
        检测主动探索机会
        """
        opportunities = []
        
        # 1. 检查实时信号
        latest_result = self._get_latest_result()
        if latest_result:
            opportunities.extend(self._check_realtime_signals(latest_result))
        
        # 2. 检查深度分析信号
        deep_result = self.scheduler.get_latest_analysis()
        if deep_result:
            opportunities.extend(self._check_deep_signals(deep_result))
        
        # 3. 检查维度变化
        opportunities.extend(self._check_dimension_changes())
        
        # 4. 检查内容交互信号
        opportunities.extend(self._check_content_signals())
        
        # 5. 检查时间触发
        opportunities.extend(self._check_time_triggers())
        
        # 去重（同一类型短时间内只保留一个）
        opportunities = self._deduplicate_opportunities(opportunities)
        
        # 按优先级排序
        opportunities.sort(key=lambda x: x.priority, reverse=True)
        
        return opportunities
    
    def _get_latest_result(self) -> Optional[AnalysisResult]:
        """获取最新分析结果"""
        results = self.store.get_results(days=1, limit=1)
        return results[0] if results else None
    
    def _check_realtime_signals(
        self,
        result: AnalysisResult
    ) -> List[ExplorationOpportunity]:
        """检查实时信号"""
        opportunities = []
        
        # 情绪异常检测
        emotion = result.get_dimension("emotion.primary")
        intensity = result.get_dimension("emotion.intensity")
        if emotion and emotion.value in ["sad", "anxious", "angry", "frustrated", "tired"]:
            if emotion.confidence >= 0.6:
                priority = 7
                if intensity and intensity.value >= 7:
                    priority = 9
                
                opportunities.append(ExplorationOpportunity(
                    trigger_type=ExplorationTrigger.EMOTION_ALERT,
                    priority=priority,
                    suggested_message=f"用户情绪低落: {emotion.value}",
                    context={
                        "emotion": emotion.value,
                        "intensity": intensity.value if intensity else 5,
                        "timestamp": result.timestamp,
                    },
                    expires_at=(datetime.now() + timedelta(hours=4)).isoformat(),
                    min_interval_minutes=120,  # 情绪警报2小时内不重复
                ))
        
        # 话题跟进检测
        topics = result.get_dimension_value("topics") or []
        for topic in topics:
            if isinstance(topic, str) and self._is_unfollowed_topic(topic):
                opportunities.append(ExplorationOpportunity(
                    trigger_type=ExplorationTrigger.TOPIC_FOLLOWUP,
                    priority=5,
                    suggested_message=f"跟进话题: {topic}",
                    context={"topic": topic},
                    expires_at=(datetime.now() + timedelta(days=3)).isoformat(),
                    min_interval_minutes=360,  # 6小时
                ))
        
        return opportunities
    
    def _check_deep_signals(
        self,
        result: DeepAnalysisResult
    ) -> List[ExplorationOpportunity]:
        """检查深度分析信号"""
        opportunities = []
        
        # 情绪趋势改善
        if result.emotional_trajectory.overall_trend == "improving":
            if result.emotional_trajectory.trend_confidence >= 0.6:
                opportunities.append(ExplorationOpportunity(
                    trigger_type=ExplorationTrigger.TREND_CELEBRATION,
                    priority=6,
                    suggested_message="情绪趋势改善庆祝",
                    context={
                        "trend": "improving",
                        "confidence": result.emotional_trajectory.trend_confidence,
                        "aspect": "情绪状态",
                    },
                    expires_at=(datetime.now() + timedelta(days=1)).isoformat(),
                    min_interval_minutes=720,  # 12小时
                ))
        
        # 情绪趋势下降（关心）
        if result.emotional_trajectory.overall_trend == "declining":
            opportunities.append(ExplorationOpportunity(
                trigger_type=ExplorationTrigger.CONCERN_CHECKIN,
                priority=8,
                suggested_message="情绪趋势下降关心",
                context={
                    "trend": "declining",
                    "concern": "近期情绪状态",
                },
                expires_at=(datetime.now() + timedelta(hours=6)).isoformat(),
                min_interval_minutes=240,  # 4小时
            ))
        
        # 成长信号
        for growth in result.growth_indicators:
            if growth.significance in ["high", "medium"]:
                opp_key = f"growth_{growth.description[:20]}"
                if not self._has_executed_recently(opp_key, days=7):
                    opportunities.append(ExplorationOpportunity(
                        trigger_type=ExplorationTrigger.GROWTH_RECOGNITION,
                        priority=7 if growth.significance == "high" else 5,
                        suggested_message=f"成长认可: {growth.description}",
                        context={
                            "area": growth.type,
                            "description": growth.description,
                            "significance": growth.significance,
                        },
                        expires_at=(datetime.now() + timedelta(days=2)).isoformat(),
                        min_interval_minutes=720,
                    ))
        
        # 话题解决庆祝
        for topic in result.topic_evolution:
            if topic.status == "resolved":
                opp_key = f"resolved_{topic.topic}"
                if not self._has_executed_recently(opp_key, days=14):
                    opportunities.append(ExplorationOpportunity(
                        trigger_type=ExplorationTrigger.TREND_CELEBRATION,
                        priority=6,
                        suggested_message=f"话题解决庆祝: {topic.topic}",
                        context={
                            "topic": topic.topic,
                            "resolution_signals": topic.resolution_signals,
                        },
                        expires_at=(datetime.now() + timedelta(days=1)).isoformat(),
                        min_interval_minutes=1440,  # 24小时
                    ))
        
        return opportunities
    
    def _check_dimension_changes(self) -> List[ExplorationOpportunity]:
        """检查维度变化"""
        opportunities = []
        # TODO: 实现维度变化检测
        return opportunities
    
    def _check_content_signals(self) -> List[ExplorationOpportunity]:
        """检查内容交互信号"""
        opportunities = []
        
        # 获取内容交互统计
        stats = self.store.get_content_interaction_stats(days=7)
        
        if stats.get("total", 0) >= 5:
            # 检测高兴趣话题
            top_topics = stats.get("topic_distribution", [])[:3]
            for topic, count in top_topics:
                if count >= 3:  # 一周内3次以上互动
                    opp_key = f"content_{topic}"
                    if not self._has_executed_recently(opp_key, days=7):
                        opportunities.append(ExplorationOpportunity(
                            trigger_type=ExplorationTrigger.CONTENT_RECOMMENDATION,
                            priority=4,
                            suggested_message=f"内容推荐: {topic}",
                            context={
                                "topic": topic,
                                "interaction_count": count,
                            },
                            expires_at=(datetime.now() + timedelta(days=2)).isoformat(),
                            min_interval_minutes=1440,
                        ))
        
        return opportunities
    
    def _check_time_triggers(self) -> List[ExplorationOpportunity]:
        """检查时间触发"""
        opportunities = []
        
        # 定期回顾（7天）
        last_scheduled = self._get_last_scheduled_time()
        if not last_scheduled or (datetime.now() - last_scheduled).days >= 7:
            opportunities.append(ExplorationOpportunity(
                trigger_type=ExplorationTrigger.SCHEDULED_REVIEW,
                priority=3,
                suggested_message="7天定期回顾",
                context={
                    "greeting": self.message_gen._get_greeting(),
                    "period": "这周",
                },
                expires_at=(datetime.now() + timedelta(days=1)).isoformat(),
                min_interval_minutes=10080,  # 7天
            ))
        
        return opportunities
    
    def _is_unfollowed_topic(self, topic: str) -> bool:
        """检查话题是否未跟进"""
        # 获取该话题的最近提及
        results = self.store.query_by_dimension("topics", topic, days=7)
        
        if len(results) < 2:
            return False  # 提及次数不够
        
        # 检查最近是否已跟进
        # 简化：如果3天内没有新提及，认为需要跟进
        latest = max(r.timestamp for r in results)
        latest_time = datetime.fromisoformat(latest)
        
        return (datetime.now() - latest_time).days >= 2
    
    def _has_executed_recently(self, key: str, days: int = 7) -> bool:
        """检查某类机会最近是否已执行"""
        # TODO: 实现基于持久化的检查
        return False
    
    def _get_last_scheduled_time(self) -> Optional[datetime]:
        """获取上次定期回顾时间"""
        # TODO: 实现持久化存储
        return None
    
    def _deduplicate_opportunities(
        self,
        opportunities: List[ExplorationOpportunity]
    ) -> List[ExplorationOpportunity]:
        """去重机会"""
        # 按类型分组，只保留优先级最高的
        by_type: Dict[str, ExplorationOpportunity] = {}
        
        for opp in opportunities:
            type_key = opp.trigger_type.value
            if type_key not in by_type or opp.priority > by_type[type_key].priority:
                by_type[type_key] = opp
        
        return list(by_type.values())
    
    def should_trigger_now(
        self,
        opportunity: ExplorationOpportunity,
        minutes_since_last_interaction: int
    ) -> bool:
        """
        判断是否应该现在触发
        
        Args:
            opportunity: 探索机会
            minutes_since_last_interaction: 距离上次互动的分钟数
        """
        # 检查是否已过期
        if opportunity.expires_at:
            if datetime.now() > datetime.fromisoformat(opportunity.expires_at):
                return False
        
        # 检查最小间隔
        if self._last_trigger_time:
            minutes_since_last = (datetime.now() - self._last_trigger_time).total_seconds() / 60
            if minutes_since_last < opportunity.min_interval_minutes:
                return False
        
        # 高优先级（>=8）随时可以触发
        if opportunity.priority >= 8:
            return True
        
        # 中等优先级（5-7）需要等待一段时间
        if opportunity.priority >= 5:
            return minutes_since_last_interaction >= 60  # 1小时
        
        # 低优先级需要等待更久
        return minutes_since_last_interaction >= 240  # 4小时
    
    def mark_executed(self, opportunity: ExplorationOpportunity) -> None:
        """标记机会已执行"""
        opportunity.is_executed = True
        opportunity.executed_at = datetime.now().isoformat()
        
        self._last_trigger_time = datetime.now()
        self._executed_opportunities.append(opportunity.opportunity_id)
    
    def evaluate_response(
        self,
        opportunity: ExplorationOpportunity,
        user_response: str
    ) -> bool:
        """
        评估用户回应是否积极
        
        Returns:
            True if positive, False if negative
        """
        # 简单规则判断
        positive_signals = ["好", "嗯", "是", "对", "谢谢", "可以", "行", "聊", "说"]
        negative_signals = ["不用", "不想", "别", "忙", "算了", "没", "不"]
        
        positive_count = sum(1 for s in positive_signals if s in user_response)
        negative_count = sum(1 for s in negative_signals if s in user_response)
        
        is_positive = positive_count > negative_count
        opportunity.response_evaluated = is_positive
        opportunity.user_response = user_response
        
        return is_positive


# 全局引擎
_exploration_engine: Optional[ProactiveExplorationEngine] = None


def get_exploration_engine() -> ProactiveExplorationEngine:
    """获取全局主动探索引擎"""
    global _exploration_engine
    if _exploration_engine is None:
        _exploration_engine = ProactiveExplorationEngine()
    return _exploration_engine
