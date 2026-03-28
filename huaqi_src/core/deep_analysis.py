"""LLM 深度分析模块

跨时间维度的聚合分析，发现深层模式：
- 情绪轨迹
- 话题演变
- 价值观推断
- 认知模式
- 成长信号
"""

import json
import uuid
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from collections import defaultdict

from .analysis_engine import AnalysisResult
from .flexible_store import get_flexible_store
from .llm import LLMManager, Message


@dataclass
class EmotionalTrajectory:
    """情绪轨迹"""
    overall_trend: str = "stable"  # improving/declining/fluctuating/stable
    trend_confidence: float = 0.5
    turning_points: List[Dict[str, Any]] = field(default_factory=list)
    cycle_pattern: Optional[str] = None  # 周期性规律
    negative_triggers: List[str] = field(default_factory=list)
    recovery_speed: str = "moderate"  # fast/moderate/slow
    current_stage: str = "neutral"  # positive/negative/neutral
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_trend": self.overall_trend,
            "trend_confidence": self.trend_confidence,
            "turning_points": self.turning_points,
            "cycle_pattern": self.cycle_pattern,
            "negative_triggers": self.negative_triggers,
            "recovery_speed": self.recovery_speed,
            "current_stage": self.current_stage,
        }


@dataclass
class TopicEvolution:
    """话题演变"""
    topic: str = ""
    status: str = ""  # emerging/growing/persistent/declining/resolved
    first_seen: str = ""
    last_seen: str = ""
    mention_frequency_trend: str = "stable"  # increasing/decreasing/stable
    depth_progression: str = ""  # 深度变化
    related_topics: List[str] = field(default_factory=list)
    resolution_signals: List[str] = field(default_factory=list)
    is_active: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "status": self.status,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "mention_frequency_trend": self.mention_frequency_trend,
            "depth_progression": self.depth_progression,
            "related_topics": self.related_topics,
            "resolution_signals": self.resolution_signals,
            "is_active": self.is_active,
        }


@dataclass
class ValueInference:
    """价值观推断"""
    name: str = ""
    importance_score: float = 0.0  # 0-1
    evidence: List[str] = field(default_factory=list)
    manifestation: str = ""  # 在生活中的体现
    conflicts_with: List[str] = field(default_factory=list)
    stability: str = "stable"  # stable/emerging/shifting
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "importance_score": self.importance_score,
            "evidence": self.evidence,
            "manifestation": self.manifestation,
            "conflicts_with": self.conflicts_with,
            "stability": self.stability,
        }


@dataclass
class CognitivePattern:
    """认知模式"""
    pattern_name: str = ""  # 如：成长型思维、完美主义、防御性悲观
    description: str = ""
    manifestations: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    impact: str = ""  # 对决策和行为的影响
    adaptability: str = "moderate"  # high/moderate/low
    confidence: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "pattern_name": self.pattern_name,
            "description": self.description,
            "manifestations": self.manifestations,
            "triggers": self.triggers,
            "impact": self.impact,
            "adaptability": self.adaptability,
            "confidence": self.confidence,
        }


@dataclass
class GrowthIndicator:
    """成长信号"""
    type: str = ""  # skill/mindset/emotion/relationship/career
    description: str = ""
    detected_at: str = ""
    evidence: List[str] = field(default_factory=list)
    significance: str = "medium"  # low/medium/high
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "description": self.description,
            "detected_at": self.detected_at,
            "evidence": self.evidence,
            "significance": self.significance,
        }


@dataclass
class DeepAnalysisResult:
    """深度分析结果"""
    analysis_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    analysis_period_start: str = ""
    analysis_period_end: str = ""
    
    # 核心洞察
    core_insights: List[str] = field(default_factory=list)
    summary: str = ""  # 一句话总结
    
    # 具体维度
    emotional_trajectory: EmotionalTrajectory = field(default_factory=EmotionalTrajectory)
    topic_evolution: List[TopicEvolution] = field(default_factory=list)
    value_inference: List[ValueInference] = field(default_factory=list)
    cognitive_patterns: List[CognitivePattern] = field(default_factory=list)
    growth_indicators: List[GrowthIndicator] = field(default_factory=list)
    
    confidence_overall: float = 0.5
    analysis_timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "analysis_id": self.analysis_id,
            "analysis_period_start": self.analysis_period_start,
            "analysis_period_end": self.analysis_period_end,
            "core_insights": self.core_insights,
            "summary": self.summary,
            "emotional_trajectory": self.emotional_trajectory.to_dict(),
            "topic_evolution": [t.to_dict() for t in self.topic_evolution],
            "value_inference": [v.to_dict() for v in self.value_inference],
            "cognitive_patterns": [p.to_dict() for p in self.cognitive_patterns],
            "growth_indicators": [g.to_dict() for g in self.growth_indicators],
            "confidence_overall": self.confidence_overall,
            "analysis_timestamp": self.analysis_timestamp,
        }
    
    def has_significant_insight(self) -> bool:
        """是否有重大洞察"""
        # 情绪有重大改善
        if self.emotional_trajectory.overall_trend == "improving":
            return True
        
        # 有重要成长信号
        high_significance_growth = [g for g in self.growth_indicators if g.significance == "high"]
        if high_significance_growth:
            return True
        
        # 话题有重要进展
        resolved_topics = [t for t in self.topic_evolution if t.status == "resolved"]
        if resolved_topics:
            return True
        
        return False
    
    def get_context_for_prompt(self) -> str:
        """生成用于提示词的上下文"""
        parts = ["### 深度洞察"]
        
        # 情绪轨迹
        if self.emotional_trajectory.overall_trend != "stable":
            trend_desc = {
                "improving": "近期情绪整体向好",
                "declining": "近期情绪需要关注",
                "fluctuating": "近期情绪有所波动"
            }.get(self.emotional_trajectory.overall_trend, "")
            if trend_desc:
                parts.append(f"- {trend_desc}")
        
        # 核心话题
        active_topics = [t for t in self.topic_evolution if t.is_active][:2]
        for topic in active_topics:
            if topic.status == "emerging_and_growing":
                parts.append(f"- 最近开始关注{topic.topic}，且兴趣在增长")
            elif topic.status == "persistent":
                parts.append(f"- 持续关注{topic.topic}")
        
        # 价值观
        if self.value_inference:
            top_value = self.value_inference[0]
            parts.append(f"- 用户最看重：{top_value.name}")
        
        # 成长信号
        if self.growth_indicators:
            top_growth = self.growth_indicators[0]
            parts.append(f"- 近期成长：{top_growth.description}")
        
        return "\n".join(parts) if len(parts) > 1 else ""


class DeepAnalyzer:
    """深度分析引擎"""
    
    def __init__(self, llm_manager: Optional[LLMManager] = None):
        self.llm = llm_manager or LLMManager()
        self.store = get_flexible_store()
    
    async def analyze(
        self,
        days: int = 30,
    ) -> DeepAnalysisResult:
        """
        执行深度分析
        
        Args:
            days: 分析天数范围
            
        Returns:
            深度分析结果
        """
        # 1. 获取历史数据
        history = self.store.get_results(days=days)
        
        if not history:
            return DeepAnalysisResult(
                analysis_period_start=datetime.now().isoformat(),
                analysis_period_end=datetime.now().isoformat(),
                summary="暂无足够数据",
            )
        
        # 确定分析时间范围
        timestamps = [h.timestamp for h in history]
        start_time = min(timestamps)
        end_time = max(timestamps)
        
        # 2. 并行执行各维度分析
        emotional_traj = await self._analyze_emotional_trajectory(history)
        topic_evol = await self._analyze_topic_evolution(history)
        values = await self._infer_values(history)
        patterns = await self._detect_cognitive_patterns(history)
        growth = await self._identify_growth_signals(history)
        
        # 3. 综合洞察
        core_insights, summary = await self._synthesize_insights(
            emotional_traj, topic_evol, values, patterns, growth
        )
        
        # 4. 计算整体置信度
        confidence = self._calculate_overall_confidence(
            emotional_traj, topic_evol, values, patterns, growth
        )
        
        return DeepAnalysisResult(
            analysis_period_start=start_time,
            analysis_period_end=end_time,
            core_insights=core_insights,
            summary=summary,
            emotional_trajectory=emotional_traj,
            topic_evolution=topic_evol,
            value_inference=values,
            cognitive_patterns=patterns,
            growth_indicators=growth,
            confidence_overall=confidence,
        )
    
    def _extract_emotion_sequence(
        self,
        history: List[AnalysisResult]
    ) -> List[Dict[str, Any]]:
        """提取情绪序列"""
        sequence = []
        for result in sorted(history, key=lambda x: x.timestamp):
            emotion = result.get_dimension("emotion.primary")
            intensity = result.get_dimension("emotion.intensity")
            if emotion and emotion.confidence >= 0.5:
                sequence.append({
                    "timestamp": result.timestamp,
                    "emotion": emotion.value,
                    "intensity": intensity.value if intensity else 5,
                    "message": result.message_content[:100],
                })
        return sequence
    
    async def _analyze_emotional_trajectory(
        self,
        history: List[AnalysisResult]
    ) -> EmotionalTrajectory:
        """分析情绪轨迹"""
        emotion_sequence = self._extract_emotion_sequence(history)
        
        if len(emotion_sequence) < 5:
            return EmotionalTrajectory(
                overall_trend="stable",
                trend_confidence=0.3,
                current_stage="neutral"
            )
        
        prompt = f"""你是一个专业的情绪分析师。请基于用户的情绪时间线，分析情绪轨迹。

情绪时间线（最近{len(emotion_sequence)}条）：
{json.dumps(emotion_sequence[-20:], ensure_ascii=False, indent=2)}

请分析并输出JSON格式：
{{
  "overall_trend": "improving/declining/fluctuating/stable",
  "trend_confidence": 0.0-1.0,
  "turning_points": [
    {{
      "timestamp": "时间",
      "from_emotion": "之前情绪",
      "to_emotion": "之后情绪",
      "trigger": "可能的原因"
    }}
  ],
  "cycle_pattern": "发现的周期性规律，如'周五焦虑周末恢复'，没有则null",
  "negative_triggers": ["引发负面情绪的情境"],
  "recovery_speed": "fast/moderate/slow",
  "current_stage": "positive/negative/neutral"
}}

分析原则：
1. 基于数据趋势，不要过度推测
2. 转折点需要有明确的情绪变化证据
3. 如果没有明显趋势，设置低confidence"""
        
        try:
            response = self.llm.chat([
                Message.system("你是专业的情绪分析师，擅长发现情绪模式和趋势。"),
                Message.user(prompt)
            ])
            
            content = self._extract_json(response.content)
            data = json.loads(content)
            
            return EmotionalTrajectory(
                overall_trend=data.get("overall_trend", "stable"),
                trend_confidence=data.get("trend_confidence", 0.5),
                turning_points=data.get("turning_points", []),
                cycle_pattern=data.get("cycle_pattern"),
                negative_triggers=data.get("negative_triggers", []),
                recovery_speed=data.get("recovery_speed", "moderate"),
                current_stage=data.get("current_stage", "neutral"),
            )
        except Exception as e:
            return EmotionalTrajectory(
                overall_trend="stable",
                trend_confidence=0.3,
                current_stage="neutral"
            )
    
    def _extract_topic_sequence(
        self,
        history: List[AnalysisResult]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """提取话题序列"""
        topic_history = defaultdict(list)
        
        for result in sorted(history, key=lambda x: x.timestamp):
            topics = result.get_dimension_value("topics") or []
            if isinstance(topics, list):
                for topic in topics:
                    topic_history[topic].append({
                        "timestamp": result.timestamp,
                        "message": result.message_content[:100],
                    })
        
        return dict(topic_history)
    
    async def _analyze_topic_evolution(
        self,
        history: List[AnalysisResult]
    ) -> List[TopicEvolution]:
        """分析话题演变"""
        topic_history = self._extract_topic_sequence(history)
        
        if not topic_history:
            return []
        
        # 选择有代表性的话题（提及次数 >= 2）
        significant_topics = {
            k: v for k, v in topic_history.items()
            if len(v) >= 2
        }
        
        if not significant_topics:
            return []
        
        prompt = f"""分析用户关注话题的演变。

话题历史：
{json.dumps(significant_topics, ensure_ascii=False, indent=2)}

请分析每个话题并输出JSON格式：
{{
  "topics": [
    {{
      "topic": "话题名称",
      "status": "emerging/growing/persistent/declining/resolved",
      "mention_frequency_trend": "increasing/decreasing/stable",
      "depth_progression": "从...到...",
      "related_topics": ["相关话题"],
      "resolution_signals": ["如果已解决，说明解决信号"],
      "is_active": true/false
    }}
  ]
}}

状态定义：
- emerging: 刚出现，提及少
- growing: 提及频率增加
- persistent: 持续稳定关注
- declining: 提及频率减少
- resolved: 不再提及，已有解决方案"""
        
        try:
            response = self.llm.chat([
                Message.system("你是专业的用户研究分析师，擅长分析兴趣演变。"),
                Message.user(prompt)
            ])
            
            content = self._extract_json(response.content)
            data = json.loads(content)
            
            evolutions = []
            for t in data.get("topics", []):
                topic_name = t.get("topic", "")
                if topic_name in significant_topics:
                    history_list = significant_topics[topic_name]
                    evolutions.append(TopicEvolution(
                        topic=topic_name,
                        status=t.get("status", "persistent"),
                        first_seen=history_list[0]["timestamp"] if history_list else "",
                        last_seen=history_list[-1]["timestamp"] if history_list else "",
                        mention_frequency_trend=t.get("mention_frequency_trend", "stable"),
                        depth_progression=t.get("depth_progression", ""),
                        related_topics=t.get("related_topics", []),
                        resolution_signals=t.get("resolution_signals", []),
                        is_active=t.get("is_active", True),
                    ))
            
            return evolutions
        except Exception as e:
            return []
    
    async def _infer_values(
        self,
        history: List[AnalysisResult]
    ) -> List[ValueInference]:
        """推断价值观"""
        # 提取用户的立场表达和决策情境
        stance_data = []
        for result in history:
            stances = result.get_dimension_value("stances") or []
            if isinstance(stances, list):
                for s in stances:
                    if isinstance(s, dict) and s.get("confidence", 0) >= 0.6:
                        stance_data.append({
                            "timestamp": result.timestamp,
                            "topic": s.get("topic", ""),
                            "position": s.get("position", ""),
                            "factors_pro": s.get("factors_pro", []),
                            "factors_con": s.get("factors_con", []),
                        })
        
        if len(stance_data) < 3:
            return []
        
        prompt = f"""基于用户的立场表达，推断其核心价值观。

立场数据：
{json.dumps(stance_data[-10:], ensure_ascii=False, indent=2)}

请推断Top 5价值观并输出JSON：
{{
  "values": [
    {{
      "name": "价值观名称（如：成长、自由、关系、成就、安全）",
      "importance_score": 0.0-1.0,
      "evidence": ["原文引用作为证据"],
      "manifestation": "在生活中的具体体现",
      "conflicts_with": ["可能冲突的其他价值观"],
      "stability": "stable/emerging/shifting"
    }}
  ]
}}

原则：
1. 只基于明确证据
2. 重要性评分要合理分布
3. 注意用户在不同时间的立场变化"""
        
        try:
            response = self.llm.chat([
                Message.system("你是专业的价值观分析师，擅长从行为中推断核心价值。"),
                Message.user(prompt)
            ])
            
            content = self._extract_json(response.content)
            data = json.loads(content)
            
            values = []
            for v in data.get("values", []):
                values.append(ValueInference(
                    name=v.get("name", ""),
                    importance_score=v.get("importance_score", 0.5),
                    evidence=v.get("evidence", []),
                    manifestation=v.get("manifestation", ""),
                    conflicts_with=v.get("conflicts_with", []),
                    stability=v.get("stability", "stable"),
                ))
            
            return sorted(values, key=lambda x: x.importance_score, reverse=True)
        except Exception as e:
            return []
    
    async def _detect_cognitive_patterns(
        self,
        history: List[AnalysisResult]
    ) -> List[CognitivePattern]:
        """检测认知模式"""
        # 提取决策相关的洞察
        decision_data = []
        for result in history:
            intent = result.get_dimension("intent.deep")
            needs = result.get_dimension_value("intent.needs") or []
            if intent and "decision" in str(needs):
                decision_data.append({
                    "timestamp": result.timestamp,
                    "intent": intent.value,
                    "message": result.message_content[:150],
                })
        
        prompt = f"""分析用户的认知和决策模式。

决策情境（共{len(decision_data)}条）：
{json.dumps(decision_data[-10:], ensure_ascii=False, indent=2)}

请识别认知模式并输出JSON：
{{
  "patterns": [
    {{
      "pattern_name": "模式名称（如：完美主义、成长型思维、防御性悲观、拖延倾向）",
      "description": "模式描述",
      "manifestations": ["具体表现1", "具体表现2"],
      "triggers": ["触发情境"],
      "impact": "对决策和行为的影响",
      "adaptability": "high/moderate/low",
      "confidence": 0.0-1.0
    }}
  ]
}}

注意：
1. 只识别有明确证据的模式
2. 同时关注积极和需要关注的模式
3. confidence 基于证据充分程度"""
        
        try:
            response = self.llm.chat([
                Message.system("你是专业的认知行为分析师。"),
                Message.user(prompt)
            ])
            
            content = self._extract_json(response.content)
            data = json.loads(content)
            
            patterns = []
            for p in data.get("patterns", []):
                patterns.append(CognitivePattern(
                    pattern_name=p.get("pattern_name", ""),
                    description=p.get("description", ""),
                    manifestations=p.get("manifestations", []),
                    triggers=p.get("triggers", []),
                    impact=p.get("impact", ""),
                    adaptability=p.get("adaptability", "moderate"),
                    confidence=p.get("confidence", 0.5),
                ))
            
            return sorted(patterns, key=lambda x: x.confidence, reverse=True)
        except Exception as e:
            return []
    
    async def _identify_growth_signals(
        self,
        history: List[AnalysisResult]
    ) -> List[GrowthIndicator]:
        """识别成长信号"""
        prompt = f"""分析用户的成长信号。

分析材料：
- 共{len(history)}条对话记录
- 时间跨度：{history[0].timestamp if history else 'N/A'} 到 {history[-1].timestamp if history else 'N/A'}

请识别成长信号并输出JSON：
{{
  "growth_indicators": [
    {{
      "type": "skill/mindset/emotion/relationship/career",
      "description": "成长描述",
      "detected_at": "检测到的时间",
      "evidence": ["证据1", "证据2"],
      "significance": "low/medium/high"
    }}
  ]
}}

成长信号包括：
- 技能：开始学习新东西，技能提升
- 心态：思维模式积极转变
- 情绪：情绪管理能力提升
- 关系：人际关系改善
- 职业：职业发展进展

原则：
1. 基于明确的改善证据
2. 对比早期和近期的表现
3. 优先识别high significance的信号"""
        
        try:
            response = self.llm.chat([
                Message.system("你是专业的成长教练，善于发现进步和成长。"),
                Message.user(prompt)
            ])
            
            content = self._extract_json(response.content)
            data = json.loads(content)
            
            indicators = []
            for g in data.get("growth_indicators", []):
                indicators.append(GrowthIndicator(
                    type=g.get("type", ""),
                    description=g.get("description", ""),
                    detected_at=g.get("detected_at", ""),
                    evidence=g.get("evidence", []),
                    significance=g.get("significance", "medium"),
                ))
            
            return sorted(
                indicators,
                key=lambda x: {"high": 3, "medium": 2, "low": 1}.get(x.significance, 0),
                reverse=True
            )
        except Exception as e:
            return []
    
    async def _synthesize_insights(
        self,
        emotional_traj: EmotionalTrajectory,
        topic_evol: List[TopicEvolution],
        values: List[ValueInference],
        patterns: List[CognitivePattern],
        growth: List[GrowthIndicator],
    ) -> Tuple[List[str], str]:
        """综合洞察"""
        context = {
            "emotional_trend": emotional_traj.overall_trend,
            "current_stage": emotional_traj.current_stage,
            "active_topics": [t.topic for t in topic_evol if t.is_active][:3],
            "top_value": values[0].name if values else "",
            "main_pattern": patterns[0].pattern_name if patterns else "",
            "growth_count": len(growth),
        }
        
        prompt = f"""基于以下分析结果，生成核心洞察和一句话总结。

分析结果摘要：
{json.dumps(context, ensure_ascii=False, indent=2)}

请输出JSON：
{{
  "core_insights": [
    "洞察1：关于情绪/话题/价值观的重要发现",
    "洞察2：...",
    "洞察3：..."
  ],
  "summary": "一句话总结用户当前状态和趋势"
}}

洞察应该：
1. 有具体证据支持
2. 对理解用户有帮助
3. 可以指导后续互动策略"""
        
        try:
            response = self.llm.chat([
                Message.system("你是专业的用户研究专家，擅长提炼核心洞察。"),
                Message.user(prompt)
            ])
            
            content = self._extract_json(response.content)
            data = json.loads(content)
            
            return (
                data.get("core_insights", []),
                data.get("summary", "")
            )
        except Exception as e:
            return ([], "分析完成")
    
    def _calculate_overall_confidence(
        self,
        emotional_traj: EmotionalTrajectory,
        topic_evol: List[TopicEvolution],
        values: List[ValueInference],
        patterns: List[CognitivePattern],
        growth: List[GrowthIndicator],
    ) -> float:
        """计算整体置信度"""
        scores = []
        
        # 情绪轨迹置信度（权重 0.25）
        scores.append(0.25 * emotional_traj.trend_confidence)
        
        # 话题演变置信度（权重 0.2）
        if topic_evol:
            topic_conf = sum(1 for t in topic_evol if t.status != "") / len(topic_evol)
            scores.append(0.2 * topic_conf)
        
        # 价值观置信度（权重 0.2）
        if values:
            value_conf = sum(v.importance_score for v in values[:3]) / 3
            scores.append(0.2 * value_conf)
        
        # 认知模式置信度（权重 0.15）
        if patterns:
            pattern_conf = sum(p.confidence for p in patterns[:2]) / 2
            scores.append(0.15 * pattern_conf)
        
        # 成长信号（权重 0.2）
        if growth:
            growth_conf = len(growth) / 5  # 假设5个为满
            scores.append(0.2 * min(growth_conf, 1.0))
        
        return sum(scores)
    
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


class DeepAnalysisScheduler:
    """深度分析调度器"""
    
    def __init__(self, memory_dir: Optional[Any] = None):
        self.store = get_flexible_store(memory_dir)
        self.analyzer = DeepAnalyzer()
        self._last_analysis_time: Dict[str, datetime] = {}
    
    def should_trigger(self) -> bool:
        """判断是否应该触发深度分析"""
        # 1. 时间触发（距离上次分析 >= 24小时）
        last_time = self._last_analysis_time.get("default")
        if last_time:
            time_since = datetime.now() - last_time
            if time_since >= timedelta(hours=24):
                return True
        else:
            return True  # 首次分析
        
        # 2. 数据量触发
        new_data_count = self._get_new_data_count(user_id)
        if new_data_count >= 20:
            return True
        
        return False
    
    def _get_new_data_count(self) -> int:
        """获取上次分析后的新数据数量"""
        last_time = self._last_analysis_time.get("default")
        if not last_time:
            return 999  # 首次
        
        # 获取最近24小时的数据
        results = self.store.get_results(days=1)
        return len(results)
    
    async def run_analysis(self) -> Optional[DeepAnalysisResult]:
        """运行深度分析"""
        if not self.should_trigger():
            return None
        
        result = await self.analyzer.analyze(days=7)
        
        # 保存分析结果
        self._save_deep_analysis(result)
        
        # 更新时间
        self._last_analysis_time["default"] = datetime.now()
        
        return result
    
    def _save_deep_analysis(self, result: DeepAnalysisResult) -> None:
        """保存深度分析结果"""
        from .config_paths import get_memory_dir
        
        memory_dir = get_memory_dir()
        deep_dir = memory_dir / "deep_analysis"
        deep_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = deep_dir / f"{datetime.now().strftime('%Y-%m-%d')}.json"
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
        
        # 同时保存最新版本
        latest_path = deep_dir / "latest.json"
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)
    
    def get_latest_analysis(self) -> Optional[DeepAnalysisResult]:
        """获取最新深度分析"""
        from .config_paths import get_memory_dir
        
        memory_dir = get_memory_dir()
        latest_path = memory_dir / "deep_analysis" / "latest.json"
        
        if not latest_path.exists():
            return None
        
        try:
            with open(latest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return DeepAnalysisResult(
                    analysis_id=data.get("analysis_id", ""),
                    analysis_period_start=data.get("analysis_period_start", ""),
                    analysis_period_end=data.get("analysis_period_end", ""),
                    core_insights=data.get("core_insights", []),
                    summary=data.get("summary", ""),
                    emotional_trajectory=EmotionalTrajectory(**data.get("emotional_trajectory", {})),
                    topic_evolution=[TopicEvolution(**t) for t in data.get("topic_evolution", [])],
                    value_inference=[ValueInference(**v) for v in data.get("value_inference", [])],
                    cognitive_patterns=[CognitivePattern(**p) for p in data.get("cognitive_patterns", [])],
                    growth_indicators=[GrowthIndicator(**g) for g in data.get("growth_indicators", [])],
                    confidence_overall=data.get("confidence_overall", 0.5),
                    analysis_timestamp=data.get("analysis_timestamp", ""),
                )
        except Exception as e:
            return None
    
    async def run_scheduled_analysis(self) -> List[Tuple[str, DeepAnalysisResult]]:
        """运行定时分析（所有活跃用户）"""
        results = []
        
        # 这里应该获取所有活跃用户列表
        # 简化实现：分析有最近数据的用户
        
        return results
