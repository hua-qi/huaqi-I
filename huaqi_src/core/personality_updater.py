"""人格画像自动更新

通过分析日记和对话，识别用户画像变化，
并支持人工确认机制。
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from .personality_simple import PersonalityProfile, PersonalityEngine
from .diary_simple import DiaryStore


class UpdateType(Enum):
    """画像更新类型"""
    INTEREST = "interest"         # 兴趣变化
    GOAL = "goal"                 # 目标变化
    PREFERENCE = "preference"     # 偏好变化
    VALUE = "value"               # 价值观变化
    PATTERN = "pattern"           # 行为模式变化


@dataclass
class ProfileChange:
    """画像变化项"""
    type: UpdateType
    field: str                    # 字段名
    old_value: Any
    new_value: Any
    confidence: float             # 置信度 0-1
    evidence: List[str] = field(default_factory=list)  # 证据文本
    reasoning: str = ""           # 推理过程


@dataclass
class ProfileUpdateProposal:
    """画像更新提案"""
    id: str
    created_at: datetime
    changes: List[ProfileChange]
    source_entries: List[Dict]    # 来源的日记/对话
    status: str = "pending"       # pending/approved/rejected
    reviewed_at: Optional[datetime] = None
    review_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat(),
            "changes": [
                {
                    "type": c.type.value,
                    "field": c.field,
                    "old_value": c.old_value,
                    "new_value": c.new_value,
                    "confidence": c.confidence,
                    "evidence": c.evidence,
                    "reasoning": c.reasoning,
                }
                for c in self.changes
            ],
            "source_entries": self.source_entries,
            "status": self.status,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_notes": self.review_notes,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "ProfileUpdateProposal":
        changes = [
            ProfileChange(
                type=UpdateType(c["type"]),
                field=c["field"],
                old_value=c["old_value"],
                new_value=c["new_value"],
                confidence=c["confidence"],
                evidence=c.get("evidence", []),
                reasoning=c.get("reasoning", ""),
            )
            for c in data.get("changes", [])
        ]
        return cls(
            id=data["id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            changes=changes,
            source_entries=data.get("source_entries", []),
            status=data.get("status", "pending"),
            reviewed_at=datetime.fromisoformat(data["reviewed_at"]) if data.get("reviewed_at") else None,
            review_notes=data.get("review_notes"),
        )


class ProfileAnalyzer:
    """画像分析器
    
    分析日记内容，识别画像变化
    """
    
    def __init__(self, llm_client=None):
        self.llm_client = llm_client
    
    def analyze_entries(
        self,
        entries: List[Dict],
        current_profile: PersonalityProfile,
    ) -> List[ProfileChange]:
        """分析日记条目，识别画像变化
        
        Args:
            entries: 日记条目列表
            current_profile: 当前画像
            
        Returns:
            变化列表
        """
        if not entries:
            return []
        
        # 简化实现：基于关键词分析
        changes = []
        
        # 合并所有日记内容
        all_content = "\n".join(e.get("content", "") for e in entries)
        
        # 分析兴趣变化
        interest_changes = self._detect_interest_changes(all_content, current_profile)
        changes.extend(interest_changes)
        
        # 分析偏好变化
        preference_changes = self._detect_preference_changes(all_content, current_profile)
        changes.extend(preference_changes)
        
        return changes
    
    def _detect_interest_changes(
        self,
        content: str,
        profile: PersonalityProfile,
    ) -> List[ProfileChange]:
        """检测兴趣变化"""
        changes = []
        
        # 关键词映射
        interest_keywords = {
            "编程": ["编程", "代码", "开发", "python", "coding", "programming"],
            "阅读": ["读书", "阅读", "看书", "读了", "书名"],
            "写作": ["写作", "写文章", "博客", "公众号"],
            "运动": ["运动", "健身", "跑步", "瑜伽", "游泳"],
            "音乐": ["音乐", "吉他", "钢琴", "唱歌", "听歌"],
            "旅行": ["旅行", "旅游", "出行", "去", "玩"],
            "学习": ["学习", "上课", "课程", "学", "study"],
        }
        
        content_lower = content.lower()
        
        for interest, keywords in interest_keywords.items():
            mentions = sum(1 for kw in keywords if kw in content_lower)
            if mentions >= 3:  # 多次提到
                # 检查是否已记录
                current_interests = profile.custom_traits.get("interests", [])
                if interest not in current_interests:
                    changes.append(ProfileChange(
                        type=UpdateType.INTEREST,
                        field="interests",
                        old_value=current_interests,
                        new_value=current_interests + [interest],
                        confidence=min(mentions / 10, 0.9),
                        evidence=[f"提到'{interest}'相关话题 {mentions} 次"],
                        reasoning=f"日记中频繁提到'{interest}'相关内容",
                    ))
        
        return changes
    
    def _detect_preference_changes(
        self,
        content: str,
        profile: PersonalityProfile,
    ) -> List[ProfileChange]:
        """检测偏好变化"""
        changes = []
        
        # 检测情绪倾向变化
        positive_words = ["开心", "快乐", "满意", "顺利", "成功", "喜欢"]
        negative_words = ["焦虑", "压力", "困难", "挫折", "失败", "讨厌"]
        
        positive_count = sum(1 for w in positive_words if w in content)
        negative_count = sum(1 for w in negative_words if w in content)
        
        total = positive_count + negative_count
        if total > 0:
            positive_ratio = positive_count / total
            
            # 如果积极情绪明显且当前神经质分数较高
            if positive_ratio > 0.7 and profile.neuroticism < -0.5:
                changes.append(ProfileChange(
                    type=UpdateType.PATTERN,
                    field="neuroticism",
                    old_value=profile.neuroticism,
                    new_value=profile.neuroticism + 0.2,  # 向稳定方向调整
                    confidence=0.6,
                    evidence=[f"积极情绪词出现 {positive_count} 次", f"消极情绪词出现 {negative_count} 次"],
                    reasoning="日记中表现出较多的积极情绪，可能情绪稳定性有所提升",
                ))
        
        return changes
    
    def analyze_with_llm(
        self,
        entries: List[Dict],
        current_profile: PersonalityProfile,
    ) -> List[ProfileChange]:
        """使用 LLM 分析画像变化（更精准）"""
        if not self.llm_client or not entries:
            return []
        
        # 构建提示词
        entries_text = "\n\n".join([
            f"[{e.get('date', '未知日期')}] {e.get('content', '')[:500]}"
            for e in entries[:10]  # 最多10条
        ])
        
        prompt = f"""分析以下日记内容，识别用户画像的潜在变化。

当前画像：
- 性格开放度: {current_profile.openness}
- 责任心: {current_profile.conscientiousness}
- 外向性: {current_profile.extraversion}
- 宜人性: {current_profile.agreeableness}
- 情绪稳定性: {current_profile.neuroticism}
- 兴趣: {current_profile.custom_traits.get('interests', [])}

日记内容：
{entries_text}

请分析是否有以下变化：
1. 新的兴趣爱好
2. 价值观变化
3. 行为模式变化
4. 目标变化

以 JSON 格式返回：
{{
    "changes": [
        {{
            "type": "interest|value|pattern|goal",
            "field": "字段名",
            "new_value": "新值",
            "confidence": 0.8,
            "reasoning": "推理过程"
        }}
    ]
}}

如果没有明显变化，返回空数组。"""

        # TODO: 调用 LLM 进行分析
        # 简化版本返回空
        return []


class PersonalityUpdater:
    """人格画像更新管理器
    
    管理画像更新流程：
    1. 定期分析日记
    2. 生成更新提案
    3. 等待用户确认
    4. 应用更新
    """
    
    def __init__(self, memory_dir: Path = None):
        if memory_dir is None:
            from .config_paths import get_memory_dir
            memory_dir = get_memory_dir()
        self.memory_dir = memory_dir
        self.proposals_dir = memory_dir / "profile_updates"
        self.proposals_dir.mkdir(parents=True, exist_ok=True)
        
        self.diary_store = DiaryStore(memory_dir)
        self.personality_engine = PersonalityEngine(memory_dir)
        self.analyzer = ProfileAnalyzer()
    
    def analyze_recent(
        self,
        days: int = 7,
        min_confidence: float = 0.6,
    ) -> Optional[ProfileUpdateProposal]:
        """分析最近的日记，生成更新提案
        
        Args:
            days: 分析最近几天的日记
            min_confidence: 最低置信度阈值
            
        Returns:
            更新提案，如果没有变化则返回 None
        """
        # 计算日期范围
        from datetime import timedelta
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        # 获取最近的日记
        recent_entries = self.diary_store.list_entries(
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )
        
        if not recent_entries:
            print("[ProfileUpdater] 最近无日记，跳过分析")
            return None
        
        # 转换为字典
        entries_data = [
            {"date": e.date, "content": e.content, "mood": e.mood, "tags": e.tags}
            for e in recent_entries
        ]
        
        # 分析变化
        current_profile = self.personality_engine.profile
        changes = self.analyzer.analyze_entries(entries_data, current_profile)
        
        # 过滤低置信度的变化
        changes = [c for c in changes if c.confidence >= min_confidence]
        
        if not changes:
            print("[ProfileUpdater] 未检测到显著画像变化")
            return None
        
        # 创建提案
        proposal = ProfileUpdateProposal(
            id=f"profile_update_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            created_at=datetime.now(),
            changes=changes,
            source_entries=entries_data[:3],  # 只保留3条作为参考
        )
        
        # 保存提案
        self._save_proposal(proposal)
        
        return proposal
    
    def _save_proposal(self, proposal: ProfileUpdateProposal):
        """保存提案到文件"""
        filepath = self.proposals_dir / f"{proposal.id}.json"
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(proposal.to_dict(), f, ensure_ascii=False, indent=2)
    
    def list_pending_proposals(self) -> List[ProfileUpdateProposal]:
        """列出所有待审核的提案"""
        proposals = []
        
        for filepath in self.proposals_dir.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                if data.get("status") == "pending":
                    proposals.append(ProfileUpdateProposal.from_dict(data))
            except Exception as e:
                print(f"[ProfileUpdater] 读取提案失败: {e}")
        
        return sorted(proposals, key=lambda p: p.created_at, reverse=True)
    
    def get_proposal(self, proposal_id: str) -> Optional[ProfileUpdateProposal]:
        """获取指定提案"""
        filepath = self.proposals_dir / f"{proposal_id}.json"
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return ProfileUpdateProposal.from_dict(data)
    
    def approve_proposal(
        self,
        proposal_id: str,
        notes: str = None,
    ) -> bool:
        """批准并应用更新提案"""
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            return False
        
        # 应用变化
        profile = self.personality_engine.profile
        
        for change in proposal.changes:
            if hasattr(profile, change.field):
                setattr(profile, change.field, change.new_value)
            else:
                # 自定义字段
                if change.field not in profile.custom_traits:
                    profile.custom_traits[change.field] = {}
                profile.custom_traits[change.field] = change.new_value
        
        # 保存画像
        self.personality_engine.save(profile)
        
        # 更新提案状态
        proposal.status = "approved"
        proposal.reviewed_at = datetime.now()
        proposal.review_notes = notes
        self._save_proposal(proposal)
        
        print(f"[ProfileUpdater] 已应用更新: {proposal_id}")
        return True
    
    def reject_proposal(
        self,
        proposal_id: str,
        notes: str = None,
    ) -> bool:
        """拒绝更新提案"""
        proposal = self.get_proposal(proposal_id)
        if proposal is None:
            return False
        
        proposal.status = "rejected"
        proposal.reviewed_at = datetime.now()
        proposal.review_notes = notes
        self._save_proposal(proposal)
        
        print(f"[ProfileUpdater] 已拒绝更新: {proposal_id}")
        return True
    
    def get_update_summary(self, proposal: ProfileUpdateProposal) -> str:
        """生成更新摘要文本"""
        lines = [
            f"📊 人格画像更新提案",
            f"创建时间: {proposal.created_at.strftime('%Y-%m-%d %H:%M')}",
            f"",
            f"检测到 {len(proposal.changes)} 项变化:",
        ]
        
        for i, change in enumerate(proposal.changes, 1):
            lines.extend([
                f"\n{i}. {change.type.value} - 置信度 {change.confidence:.0%}",
                f"   字段: {change.field}",
                f"   变化: {change.old_value} → {change.new_value}",
                f"   推理: {change.reasoning}",
            ])
        
        return "\n".join(lines)
