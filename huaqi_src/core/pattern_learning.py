"""长期模式学习系统

从用户的日记、对话、动态维度中学习长期行为模式，生成洞察报告。

核心特性：
- 情绪周期识别（每周/每月模式）
- 话题偏好追踪
- 行为模式分析
- 周报/月报自动生成
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
from collections import Counter, defaultdict
from enum import Enum
import json
import math

from .config_paths import get_memory_dir
from .diary_simple import DiaryStore, DiaryEntry
from .flexible_store import FlexibleStore, AnalysisResult
from .schema import get_schema_registry


class PatternType(str, Enum):
    """模式类型"""
    EMOTION_CYCLE = "emotion_cycle"      # 情绪周期
    TOPIC_TREND = "topic_trend"          # 话题趋势
    BEHAVIOR_PATTERN = "behavior"        # 行为模式
    TRIGGER_ASSOCIATION = "trigger"      # 触发关联
    GROWTH_TRAJECTORY = "growth"         # 成长轨迹


class InsightSeverity(str, Enum):
    """洞察严重程度/重要性"""
    INFO = "info"        # 信息性
    POSITIVE = "positive"  # 积极
    WARNING = "warning"   # 警告
    ATTENTION = "attention"  # 需要关注


@dataclass
class PatternInsight:
    """模式洞察"""
    insight_id: str = field(default_factory=lambda: str(datetime.now().timestamp()))
    pattern_type: PatternType = PatternType.EMOTION_CYCLE
    title: str = ""
    description: str = ""
    severity: InsightSeverity = InsightSeverity.INFO
    confidence: float = 0.5              # 置信度 0-1
    evidence: List[str] = field(default_factory=list)
    related_dates: List[str] = field(default_factory=list)
    recommendation: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    valid_until: datetime = field(default_factory=lambda: datetime.now() + timedelta(days=30))
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "insight_id": self.insight_id,
            "pattern_type": self.pattern_type.value,
            "title": self.title,
            "description": self.description,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "related_dates": self.related_dates,
            "recommendation": self.recommendation,
            "generated_at": self.generated_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PatternInsight":
        return cls(
            insight_id=data.get("insight_id", ""),
            pattern_type=PatternType(data.get("pattern_type", "emotion_cycle")),
            title=data.get("title", ""),
            description=data.get("description", ""),
            severity=InsightSeverity(data.get("severity", "info")),
            confidence=data.get("confidence", 0.5),
            evidence=data.get("evidence", []),
            related_dates=data.get("related_dates", []),
            recommendation=data.get("recommendation", ""),
            generated_at=datetime.fromisoformat(data.get("generated_at", datetime.now().isoformat())),
            valid_until=datetime.fromisoformat(data.get("valid_until", datetime.now().isoformat())),
        )


@dataclass
class WeeklyReport:
    """周报"""
    week_start: str                    # 周一开始日期
    week_end: str                      # 周日结束日期
    emotion_summary: str               # 情绪概览
    emotion_trend: str                 # 趋势：improving / stable / declining
    avg_emotion_score: float           # 平均情绪分 0-10
    emotion_volatility: float          # 情绪波动性
    top_topics: List[Tuple[str, int]]  # 热门话题及提及次数
    insights: List[PatternInsight]     # 本周洞察
    recommendations: List[str]         # 建议
    generated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "week_start": self.week_start,
            "week_end": self.week_end,
            "emotion_summary": self.emotion_summary,
            "emotion_trend": self.emotion_trend,
            "avg_emotion_score": self.avg_emotion_score,
            "emotion_volatility": self.emotion_volatility,
            "top_topics": self.top_topics,
            "insights": [i.to_dict() for i in self.insights],
            "recommendations": self.recommendations,
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class MonthlyReport:
    """月报"""
    month: str                         # 月份 (YYYY-MM)
    emotion_summary: str               # 情绪概览
    emotion_change: float              # 与上月相比变化 (+/-)
    highlight_moments: List[str]       # 高光时刻
    topic_evolution: Dict[str, Any]    # 话题演变
    behavior_changes: List[str]        # 行为变化
    growth_metrics: Dict[str, float]   # 成长指标
    insights: List[PatternInsight]     # 月度洞察
    next_month_goals: List[str]        # 下月建议目标
    generated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "month": self.month,
            "emotion_summary": self.emotion_summary,
            "emotion_change": self.emotion_change,
            "highlight_moments": self.highlight_moments,
            "topic_evolution": self.topic_evolution,
            "behavior_changes": self.behavior_changes,
            "growth_metrics": self.growth_metrics,
            "insights": [i.to_dict() for i in self.insights],
            "next_month_goals": self.next_month_goals,
            "generated_at": self.generated_at.isoformat(),
        }


class PatternLearningEngine:
    """模式学习引擎"""
    
    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or get_memory_dir()
        
        # 存储
        self.diary_store = DiaryStore(self.memory_dir)
        self.flexible_store = FlexibleStore(self.memory_dir)
        
        # 历史洞察
        self.insights: List[PatternInsight] = []
        self.weekly_reports: List[WeeklyReport] = []
        self.monthly_reports: List[MonthlyReport] = []
        
        # 加载历史
        self._load_history()
    
    def _load_history(self):
        """加载历史报告和洞察"""
        # 加载洞察
        insights_path = self.memory_dir / "pattern_insights.jsonl"
        if insights_path.exists():
            with open(insights_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            self.insights.append(PatternInsight.from_dict(data))
                        except Exception:
                            pass
        
        # 加载周报
        weekly_path = self.memory_dir / "weekly_reports.jsonl"
        if weekly_path.exists():
            with open(weekly_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            # 手动解析周报（非标准 dataclass）
                            report = WeeklyReport(
                                week_start=data["week_start"],
                                week_end=data["week_end"],
                                emotion_summary=data["emotion_summary"],
                                emotion_trend=data["emotion_trend"],
                                avg_emotion_score=data["avg_emotion_score"],
                                emotion_volatility=data["emotion_volatility"],
                                top_topics=[(t[0], t[1]) for t in data["top_topics"]],
                                insights=[PatternInsight.from_dict(i) for i in data["insights"]],
                                recommendations=data["recommendations"],
                                generated_at=datetime.fromisoformat(data["generated_at"]),
                            )
                            self.weekly_reports.append(report)
                        except Exception:
                            pass
    
    def _save_insight(self, insight: PatternInsight):
        """保存洞察"""
        insights_path = self.memory_dir / "pattern_insights.jsonl"
        insights_path.parent.mkdir(parents=True, exist_ok=True)
        with open(insights_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(insight.to_dict(), ensure_ascii=False) + "\n")
    
    def _save_weekly_report(self, report: WeeklyReport):
        """保存周报"""
        weekly_path = self.memory_dir / "weekly_reports.jsonl"
        weekly_path.parent.mkdir(parents=True, exist_ok=True)
        with open(weekly_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(report.to_dict(), ensure_ascii=False) + "\n")
    
    def analyze_emotion_cycle(self, days: int = 30) -> List[PatternInsight]:
        """分析情绪周期
        
        识别：
        - 每周几情绪最低/最高
        - 情绪波动模式
        - 长期情绪趋势
        """
        insights = []
        
        # 获取数据
        diaries = self.diary_store.list_entries(limit=days)
        results = self.flexible_store.get_results(days=days, limit=100)
        
        if len(diaries) < 7 or len(results) < 10:
            return insights
        
        # 1. 星期几情绪分析
        weekday_emotions = defaultdict(list)
        for result in results:
            emotion = result.get_dimension_value("emotion.primary")
            intensity = result.get_dimension_value("emotion.intensity") or 5
            
            # 转换为分数 (0-10)
            emotion_scores = {
                "happy": 8, "excited": 9, "grateful": 8, "hopeful": 7, "proud": 8,
                "neutral": 5,
                "tired": 4, "confused": 4,
                "sad": 2, "anxious": 3, "angry": 2, "frustrated": 3, "lonely": 2, "guilty": 3,
            }
            score = emotion_scores.get(emotion, 5)
            
            dt = datetime.fromisoformat(result.timestamp)
            weekday_emotions[dt.weekday()].append(score)
        
        # 计算平均值
        weekday_avg = {}
        for weekday, scores in weekday_emotions.items():
            if len(scores) >= 3:  # 至少3个数据点
                weekday_avg[weekday] = sum(scores) / len(scores)
        
        if weekday_avg:
            # 找出情绪最低和最高的一天
            worst_day = min(weekday_avg, key=weekday_avg.get)
            best_day = max(weekday_avg, key=weekday_avg.get)
            
            weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
            
            if weekday_avg[worst_day] < 4:
                insights.append(PatternInsight(
                    pattern_type=PatternType.EMOTION_CYCLE,
                    title=f"{weekdays[worst_day]}情绪低落",
                    description=f"你的情绪在{weekdays[worst_day]}通常较低（平均{weekday_avg[worst_day]:.1f}/10），可能是工作压力或周期性疲劳导致。",
                    severity=InsightSeverity.INFO,
                    confidence=len(weekday_emotions[worst_day]) / 10,
                    evidence=[f"{weekdays[worst_day]}情绪记录"],
                    recommendation=f"尝试在{weekdays[worst_day]}晚上安排放松活动，提前准备应对策略。",
                ))
            
            if weekday_avg[best_day] > 6 and best_day != worst_day:
                insights.append(PatternInsight(
                    pattern_type=PatternType.EMOTION_CYCLE,
                    title=f"{weekdays[best_day]}情绪较好",
                    description=f"你的情绪在{weekdays[best_day]}通常较好（平均{weekday_avg[best_day]:.1f}/10）。",
                    severity=InsightSeverity.POSITIVE,
                    confidence=len(weekday_emotions[best_day]) / 10,
                    recommendation=f"可以把重要决策或社交安排在{weekdays[best_day]}。",
                ))
        
        # 2. 情绪趋势分析
        if len(results) >= 14:
            recent_scores = []
            older_scores = []
            
            mid_point = len(results) // 2
            for i, result in enumerate(results):
                emotion = result.get_dimension_value("emotion.primary")
                emotion_scores = {
                    "happy": 8, "excited": 9, "grateful": 8, "hopeful": 7, "proud": 8,
                    "neutral": 5,
                    "tired": 4, "confused": 4,
                    "sad": 2, "anxious": 3, "angry": 2, "frustrated": 3, "lonely": 2, "guilty": 3,
                }
                score = emotion_scores.get(emotion, 5)
                
                if i < mid_point:
                    older_scores.append(score)
                else:
                    recent_scores.append(score)
            
            if recent_scores and older_scores:
                recent_avg = sum(recent_scores) / len(recent_scores)
                older_avg = sum(older_scores) / len(older_scores)
                change = recent_avg - older_avg
                
                if change > 1:
                    insights.append(PatternInsight(
                        pattern_type=PatternType.GROWTH_TRAJECTORY,
                        title="情绪持续改善",
                        description=f"最近的情绪比上半月提升了 {change:.1f} 分，这是个好趋势！",
                        severity=InsightSeverity.POSITIVE,
                        confidence=0.7,
                        recommendation="继续保持当前的节奏，是什么让你感觉变好了？",
                    ))
                elif change < -1:
                    insights.append(PatternInsight(
                        pattern_type=PatternType.GROWTH_TRAJECTORY,
                        title="情绪有所下滑",
                        description=f"最近的情绪比上半月下降了 {abs(change):.1f} 分，可能需要关注一下。",
                        severity=InsightSeverity.WARNING,
                        confidence=0.7,
                        recommendation="最近发生了什么变化吗？需要我帮你梳理一下吗？",
                    ))
        
        return insights
    
    def analyze_topic_trends(self, days: int = 30) -> List[PatternInsight]:
        """分析话题趋势"""
        insights = []
        
        results = self.flexible_store.get_results(days=days, limit=100)
        if len(results) < 10:
            return insights
        
        # 统计话题
        topic_counter = Counter()
        for result in results:
            topics = result.get_dimension_value("topics") or []
            if isinstance(topics, list):
                topic_counter.update(topics)
        
        if not topic_counter:
            return insights
        
        # 热门话题
        top_topics = topic_counter.most_common(5)
        
        # 持续关注的话题（出现3次以上）
        recurring = [(t, c) for t, c in top_topics if c >= 3]
        if recurring:
            topic_str = "、".join([f"{t}({c}次)" for t, c in recurring[:3]])
            insights.append(PatternInsight(
                pattern_type=PatternType.TOPIC_TREND,
                title="持续关注的话题",
                description=f"最近你最关注：{topic_str}",
                severity=InsightSeverity.INFO,
                confidence=0.8,
                evidence=[f"话题 '{t}' 出现 {c} 次" for t, c in recurring],
                recommendation="这些话题对你很重要，需要我帮你深入分析或制定行动计划吗？",
            ))
        
        return insights
    
    def generate_weekly_report(self) -> Optional[WeeklyReport]:
        """生成周报"""
        # 计算本周时间范围
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_start + timedelta(days=6)
        
        # 获取本周数据
        diaries = self.diary_store.list_entries(
            start_date=week_start.strftime("%Y-%m-%d"),
            end_date=week_end.strftime("%Y-%m-%d"),
            limit=10
        )
        results = self.flexible_store.get_results(days=7, limit=50)
        
        if len(diaries) < 3 and len(results) < 5:
            return None
        
        # 计算情绪统计
        emotion_scores = []
        emotions_list = []
        for result in results:
            emotion = result.get_dimension_value("emotion.primary")
            intensity = result.get_dimension_value("emotion.intensity") or 5
            
            emotion_scores.append(intensity)
            emotions_list.append(emotion)
        
        if not emotion_scores:
            return None
        
        avg_score = sum(emotion_scores) / len(emotion_scores)
        
        # 计算波动性（标准差）
        if len(emotion_scores) > 1:
            variance = sum((x - avg_score) ** 2 for x in emotion_scores) / len(emotion_scores)
            volatility = math.sqrt(variance)
        else:
            volatility = 0
        
        # 情绪趋势
        if len(emotion_scores) >= 4:
            first_half = emotion_scores[:len(emotion_scores)//2]
            second_half = emotion_scores[len(emotion_scores)//2:]
            trend = "improving" if sum(second_half) > sum(first_half) else "declining" if sum(second_half) < sum(first_half) else "stable"
        else:
            trend = "stable"
        
        # 热门话题
        topic_counter = Counter()
        for result in results:
            topics = result.get_dimension_value("topics") or []
            if isinstance(topics, list):
                topic_counter.update(topics)
        top_topics = topic_counter.most_common(5)
        
        # 生成洞察
        insights = []
        insights.extend(self.analyze_emotion_cycle(days=7))
        insights.extend(self.analyze_topic_trends(days=7))
        
        # 生成建议
        recommendations = []
        if trend == "declining":
            recommendations.append("这周情绪有些下滑，周末可以安排一些放松活动。")
        elif trend == "improving":
            recommendations.append("这周情绪在变好，继续保持！")
        
        if volatility > 3:
            recommendations.append("情绪波动较大，试试每天写3件感恩的事来稳定情绪。")
        
        # 情绪概览文字
        if avg_score >= 7:
            emotion_summary = "整体积极"
        elif avg_score >= 5:
            emotion_summary = "情绪平稳"
        elif avg_score >= 3:
            emotion_summary = "略有低落"
        else:
            emotion_summary = "需要关注"
        
        report = WeeklyReport(
            week_start=week_start.strftime("%Y-%m-%d"),
            week_end=week_end.strftime("%Y-%m-%d"),
            emotion_summary=emotion_summary,
            emotion_trend=trend,
            avg_emotion_score=avg_score,
            emotion_volatility=volatility,
            top_topics=top_topics,
            insights=insights,
            recommendations=recommendations if recommendations else ["继续记录日记，我会更了解你。"],
        )
        
        # 保存
        self._save_weekly_report(report)
        self.weekly_reports.append(report)
        
        # 保存洞察
        for insight in insights:
            self._save_insight(insight)
            self.insights.append(insight)
        
        return report
    
    def format_weekly_report(self, report: WeeklyReport) -> str:
        """格式化周报为可读文本"""
        lines = [
            f"📊 本周洞察 ({report.week_start} ~ {report.week_end})",
            "",
            f"情绪概览：{report.emotion_summary}（平均 {report.avg_emotion_score:.1f}/10）",
        ]
        
        if report.emotion_trend == "improving":
            lines.append("情绪趋势：↗️ 上升")
        elif report.emotion_trend == "declining":
            lines.append("情绪趋势：↘️ 下降")
        else:
            lines.append("情绪趋势：➡️ 平稳")
        
        if report.top_topics:
            topic_str = "、".join([t[0] for t in report.top_topics[:3]])
            lines.append(f"热门话题：{topic_str}")
        
        if report.insights:
            lines.append("")
            lines.append("💡 发现")
            for insight in report.insights[:3]:
                lines.append(f"  • {insight.title}：{insight.description}")
        
        if report.recommendations:
            lines.append("")
            lines.append("🎯 建议")
            for rec in report.recommendations[:2]:
                lines.append(f"  • {rec}")
        
        return "\n".join(lines)
    
    def get_active_insights(self) -> List[PatternInsight]:
        """获取当前有效的洞察"""
        now = datetime.now()
        return [i for i in self.insights if i.valid_until >= now]
    
    def get_latest_weekly_report(self) -> Optional[WeeklyReport]:
        """获取最新周报"""
        if not self.weekly_reports:
            return None
        return sorted(self.weekly_reports, key=lambda x: x.generated_at, reverse=True)[0]


# 全局实例
_pattern_engine: Optional[PatternLearningEngine] = None


def get_pattern_engine(memory_dir: Optional[Path] = None) -> PatternLearningEngine:
    """获取全局模式学习引擎"""
    global _pattern_engine
    if _pattern_engine is None:
        _pattern_engine = PatternLearningEngine(memory_dir)
    return _pattern_engine
