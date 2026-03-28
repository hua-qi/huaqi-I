"""主动关怀触发系统

基于用户情绪状态、日记内容、对话历史，智能触发关怀消息。

核心特性：
- 多层触发条件过滤
- 智能频率控制（防骚扰）
- 上下文感知的关怀内容
- 用户反馈学习
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta
from pathlib import Path
from enum import Enum
import json
import re

from .config_paths import get_memory_dir
from .diary_simple import DiaryStore
from .flexible_store import FlexibleStore
from .user_profile import get_profile_manager


class TriggerType(str, Enum):
    """关怀触发类型"""
    EMOTION_LOW = "emotion_low"          # 情绪低落
    EMOTION_HIGH_ANXIETY = "high_anxiety"  # 高焦虑
    WORK_STRESS = "work_stress"          # 工作压力
    SLEEP_ISSUE = "sleep_issue"          # 睡眠问题
    KEYWORD_ALERT = "keyword_alert"      # 关键词预警
    SILENCE_TOO_LONG = "silence"         # 沉默太久
    PATTERN_PREDICT = "pattern_predict"  # 模式预测


class CarePriority(str, Enum):
    """关怀优先级"""
    LOW = "low"          # 轻度关怀
    NORMAL = "normal"    # 正常关怀
    HIGH = "high"        # 高优先级（必须触发）
    URGENT = "urgent"    # 紧急（如自杀倾向关键词）


@dataclass
class CareRecord:
    """关怀记录"""
    record_id: str = field(default_factory=lambda: str(datetime.now().timestamp()))
    trigger_type: TriggerType = TriggerType.EMOTION_LOW
    trigger_reason: str = ""
    care_content: str = ""
    priority: CarePriority = CarePriority.NORMAL
    user_response: Optional[str] = None
    user_feedback: Optional[str] = None  # helpful / neutral / annoying
    created_at: datetime = field(default_factory=datetime.now)
    acknowledged: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "trigger_type": self.trigger_type.value,
            "trigger_reason": self.trigger_reason,
            "care_content": self.care_content,
            "priority": self.priority.value,
            "user_response": self.user_response,
            "user_feedback": self.user_feedback,
            "created_at": self.created_at.isoformat(),
            "acknowledged": self.acknowledged,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CareRecord":
        return cls(
            record_id=data.get("record_id", ""),
            trigger_type=TriggerType(data.get("trigger_type", "emotion_low")),
            trigger_reason=data.get("trigger_reason", ""),
            care_content=data.get("care_content", ""),
            priority=CarePriority(data.get("priority", "normal")),
            user_response=data.get("user_response"),
            user_feedback=data.get("user_feedback"),
            created_at=datetime.fromisoformat(data.get("created_at", datetime.now().isoformat())),
            acknowledged=data.get("acknowledged", False),
        )


@dataclass
class CareConfig:
    """关怀配置"""
    enabled: bool = True                          # 是否启用
    level: str = "normal"                         # 关怀级别：minimal / normal / intensive
    max_per_day: int = 1                          # 每天最多触发次数
    max_per_week: int = 3                         # 每周最多触发次数
    quiet_hours_start: int = 22                   # 安静时段开始（22:00）
    quiet_hours_end: int = 8                      # 安静时段结束（08:00）
    min_silence_hours: int = 6                    # 最小沉默时长（小时）
    emotion_threshold: float = 0.3                # 情绪阈值（低于此触发）
    anxiety_threshold: int = 7                    # 焦虑阈值（高于此触发）
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "level": self.level,
            "max_per_day": self.max_per_day,
            "max_per_week": self.max_per_week,
            "quiet_hours_start": self.quiet_hours_start,
            "quiet_hours_end": self.quiet_hours_end,
            "min_silence_hours": self.min_silence_hours,
            "emotion_threshold": self.emotion_threshold,
            "anxiety_threshold": self.anxiety_threshold,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CareConfig":
        return cls(
            enabled=data.get("enabled", True),
            level=data.get("level", "normal"),
            max_per_day=data.get("max_per_day", 1),
            max_per_week=data.get("max_per_week", 3),
            quiet_hours_start=data.get("quiet_hours_start", 22),
            quiet_hours_end=data.get("quiet_hours_end", 8),
            min_silence_hours=data.get("min_silence_hours", 6),
            emotion_threshold=data.get("emotion_threshold", 0.3),
            anxiety_threshold=data.get("anxiety_threshold", 7),
        )


class ProactiveCareEngine:
    """主动关怀引擎"""
    
    # 预警关键词
    ALERT_KEYWORDS = [
        ("不想活", CarePriority.URGENT),
        ("活着没意思", CarePriority.URGENT),
        ("想死", CarePriority.URGENT),
        ("自杀", CarePriority.URGENT),
        ("撑不下去了", CarePriority.HIGH),
        ("好累", CarePriority.NORMAL),
        ("好烦", CarePriority.NORMAL),
        ("压力好大", CarePriority.NORMAL),
        ("失眠", CarePriority.NORMAL),
        ("睡不着", CarePriority.NORMAL),
    ]
    
    def __init__(self, memory_dir: Optional[Path] = None):
        self.memory_dir = memory_dir or get_memory_dir()
        self.config = self._load_config()
        
        # 存储
        self.diary_store = DiaryStore(self.memory_dir)
        self.flexible_store = FlexibleStore(self.memory_dir)
        self.care_records: List[CareRecord] = []
        
        # 加载历史记录
        self._load_care_records()
    
    def _load_config(self) -> CareConfig:
        """加载配置"""
        config_path = self.memory_dir / "care_config.json"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                return CareConfig.from_dict(json.load(f))
        return CareConfig()
    
    def save_config(self):
        """保存配置"""
        config_path = self.memory_dir / "care_config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)
    
    def _load_care_records(self):
        """加载关怀记录"""
        records_path = self.memory_dir / "care_records.jsonl"
        if records_path.exists():
            with open(records_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            data = json.loads(line)
                            self.care_records.append(CareRecord.from_dict(data))
                        except Exception:
                            pass
    
    def _save_care_record(self, record: CareRecord):
        """保存关怀记录"""
        records_path = self.memory_dir / "care_records.jsonl"
        records_path.parent.mkdir(parents=True, exist_ok=True)
        with open(records_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record.to_dict(), ensure_ascii=False) + "\n")
    
    def check_and_trigger(self, last_user_message_time: Optional[datetime] = None) -> Optional[CareRecord]:
        """检查并触发关怀
        
        返回: 触发的关怀记录，未触发返回 None
        """
        if not self.config.enabled:
            return None
        
        # 第一层：数据充足性检查
        if not self._check_data_sufficiency():
            return None
        
        # 第二层：频率控制
        if not self._check_frequency_limit():
            return None
        
        # 第三层：时机检查
        if not self._check_timing(last_user_message_time):
            return None
        
        # 第四层：情绪状态检查
        trigger = self._check_emotion_triggers()
        if not trigger:
            return None
        
        # 生成关怀内容
        care_content = self._generate_care_message(trigger)
        
        # 创建记录
        record = CareRecord(
            trigger_type=trigger["type"],
            trigger_reason=trigger["reason"],
            care_content=care_content,
            priority=trigger["priority"],
        )
        
        # 保存
        self._save_care_record(record)
        self.care_records.append(record)
        
        return record
    
    def _check_data_sufficiency(self) -> bool:
        """检查数据充足性"""
        # 检查日记数量
        diaries = self.diary_store.list_entries(limit=10)
        if len(diaries) < 3:
            return False
        
        # 检查动态维度记录
        results = self.flexible_store.get_results(days=7, limit=10)
        if len(results) < 5:
            return False
        
        return True
    
    def _check_frequency_limit(self) -> bool:
        """检查频率限制"""
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())
        
        # 今天已触发次数
        today_count = sum(
            1 for r in self.care_records
            if r.created_at >= today_start
        )
        if today_count >= self.config.max_per_day:
            return False
        
        # 本周已触发次数
        week_count = sum(
            1 for r in self.care_records
            if r.created_at >= week_start
        )
        if week_count >= self.config.max_per_week:
            return False
        
        return True
    
    def _check_timing(self, last_user_message_time: Optional[datetime]) -> bool:
        """检查时机"""
        now = datetime.now()
        
        # 检查安静时段
        current_hour = now.hour
        if self.config.quiet_hours_start <= current_hour or current_hour < self.config.quiet_hours_end:
            return False
        
        # 检查沉默时长
        if last_user_message_time:
            silence_duration = now - last_user_message_time
            if silence_duration < timedelta(hours=self.config.min_silence_hours):
                return False
        
        return True
    
    def _check_emotion_triggers(self) -> Optional[Dict[str, Any]]:
        """检查情绪触发条件"""
        
        # 1. 检查关键词预警（最高优先级）
        recent_diaries = self.diary_store.list_entries(limit=3)
        for diary in recent_diaries:
            content = diary.content.lower()
            for keyword, priority in self.ALERT_KEYWORDS:
                if keyword in content:
                    return {
                        "type": TriggerType.KEYWORD_ALERT,
                        "reason": f"检测到关键词: {keyword}",
                        "priority": priority,
                        "context": diary.content[:100],
                    }
        
        # 2. 检查最近情绪
        results = self.flexible_store.get_results(days=3, limit=10)
        if not results:
            return None
        
        # 分析情绪
        negative_count = 0
        high_anxiety_count = 0
        total_anxiety = 0
        
        for result in results:
            emotion = result.get_dimension_value("emotion.primary")
            intensity = result.get_dimension_value("emotion.intensity")
            
            if emotion in ["sad", "anxious", "angry", "frustrated", "lonely"]:
                negative_count += 1
            
            if intensity and isinstance(intensity, (int, float)):
                total_anxiety += intensity
                if intensity >= self.config.anxiety_threshold:
                    high_anxiety_count += 1
        
        # 检查连续负面情绪
        if negative_count >= min(3, len(results)):
            return {
                "type": TriggerType.EMOTION_LOW,
                "reason": f"最近 {negative_count} 次对话情绪低落",
                "priority": CarePriority.NORMAL,
                "context": None,
            }
        
        # 检查高焦虑
        if high_anxiety_count >= 2:
            return {
                "type": TriggerType.EMOTION_HIGH_ANXIETY,
                "reason": f"最近 {high_anxiety_count} 次焦虑强度 ≥ {self.config.anxiety_threshold}",
                "priority": CarePriority.NORMAL,
                "context": None,
            }
        
        # 3. 检查日记情绪
        if len(recent_diaries) >= 2:
            negative_diaries = sum(
                1 for d in recent_diaries
                if d.mood and d.mood in ["sad", "anxious", "angry", "tired", "down"]
            )
            if negative_diaries >= 2:
                return {
                    "type": TriggerType.EMOTION_LOW,
                    "reason": f"最近 {negative_diaries} 篇日记情绪不佳",
                    "priority": CarePriority.NORMAL,
                    "context": None,
                }
        
        return None
    
    def _generate_care_message(self, trigger: Dict[str, Any]) -> str:
        """生成关怀消息"""
        trigger_type = trigger["type"]
        priority = trigger["priority"]
        
        # 根据触发类型和优先级生成内容
        templates = {
            TriggerType.KEYWORD_ALERT: {
                CarePriority.URGENT: [
                    "我注意到你好像遇到了很难的事情。我在这里，愿意听你说。",
                    "你看起来很难受。你不是一个人，我在这里陪着你。",
                ],
                CarePriority.HIGH: [
                    "感觉你最近压力很大，想聊聊吗？",
                    "看你最近好像不太顺利，需要我陪你聊聊吗？",
                ],
            },
            TriggerType.EMOTION_LOW: {
                CarePriority.NORMAL: [
                    "感觉你最近心情不太好，想聊聊吗？",
                    "看你最近情绪有点低落，我在这里陪着你。",
                    "最近是不是遇到什么烦心事了？想说说吗？",
                ],
                CarePriority.LOW: [
                    "今天感觉怎么样？",
                    "想聊聊最近的事吗？",
                ],
            },
            TriggerType.EMOTION_HIGH_ANXIETY: {
                CarePriority.NORMAL: [
                    "感觉你最近有点焦虑，试试深呼吸？我在呢。",
                    "你好像压力有点大，需要我帮你理理思路吗？",
                ],
            },
        }
        
        # 获取模板
        type_templates = templates.get(trigger_type, {})
        priority_templates = type_templates.get(priority, ["想聊聊吗？"])
        
        # 随机选择或根据上下文选择
        import random
        return random.choice(priority_templates)
    
    def record_user_response(self, record_id: str, response: str):
        """记录用户回复"""
        for record in self.care_records:
            if record.record_id == record_id:
                record.user_response = response
                record.acknowledged = True
                break
    
    def record_user_feedback(self, record_id: str, feedback: str):
        """记录用户反馈（helpful / neutral / annoying）"""
        for record in self.care_records:
            if record.record_id == record_id:
                record.user_feedback = feedback
                break
    
    def get_recent_cares(self, days: int = 7) -> List[CareRecord]:
        """获取近期关怀记录"""
        cutoff = datetime.now() - timedelta(days=days)
        return [r for r in self.care_records if r.created_at >= cutoff]
    
    def get_care_stats(self) -> Dict[str, Any]:
        """获取关怀统计"""
        total = len(self.care_records)
        acknowledged = sum(1 for r in self.care_records if r.acknowledged)
        helpful = sum(1 for r in self.care_records if r.user_feedback == "helpful")
        
        return {
            "total_cares": total,
            "acknowledged": acknowledged,
            "acknowledgment_rate": acknowledged / total if total > 0 else 0,
            "helpful_count": helpful,
            "helpful_rate": helpful / total if total > 0 else 0,
        }
    
    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
        self.save_config()


# 全局实例
_care_engine: Optional[ProactiveCareEngine] = None


def get_care_engine(memory_dir: Optional[Path] = None) -> ProactiveCareEngine:
    """获取全局关怀引擎"""
    global _care_engine
    if _care_engine is None:
        _care_engine = ProactiveCareEngine(memory_dir)
    return _care_engine
