"""成长系统 - 单用户简化版

技能和目标存储在 memory/growth.yaml
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path
import yaml


@dataclass
class Skill:
    """技能"""
    name: str
    category: str
    current_level: str = "入门"
    target_level: str = "熟练"
    total_hours: float = 0.0
    last_practice: Optional[str] = None
    notes: str = ""


@dataclass
class Goal:
    """目标"""
    id: str
    title: str
    description: str = ""
    status: str = "active"
    progress: int = 0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class GrowthTracker:
    """成长追踪器 - 单用户"""

    def __init__(self, memory_dir: Path, git_committer=None):
        self.memory_dir = memory_dir
        self.growth_path = memory_dir / "growth.yaml"
        self.skills: Dict[str, Skill] = {}
        self.goals: Dict[str, Goal] = {}
        self._git_committer = git_committer
        self._load()
    
    def _load(self):
        """加载成长数据"""
        if self.growth_path.exists():
            with open(self.growth_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
                
                for name, skill_data in data.get("skills", {}).items():
                    self.skills[name] = Skill(**skill_data)
                
                for goal_id, goal_data in data.get("goals", {}).items():
                    self.goals[goal_id] = Goal(**goal_data)
    
    def save(self):
        """保存成长数据"""
        data = {
            "skills": {name: skill.__dict__ for name, skill in self.skills.items()},
            "goals": {goal.id: goal.__dict__ for goal in self.goals.values()},
        }
        with open(self.growth_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, allow_unicode=True)
    
    # ===== 技能管理 =====
    
    def add_skill(self, name: str, category: str, current: str = "入门", target: str = "熟练") -> Skill:
        """添加技能"""
        skill = Skill(name=name, category=category, current_level=current, target_level=target)
        self.skills[name] = skill
        self.save()
        return skill
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """获取技能"""
        return self.skills.get(name)
    
    def log_practice(self, name: str, hours: float, notes: str = "") -> bool:
        """记录练习"""
        if name not in self.skills:
            return False
        
        skill = self.skills[name]
        skill.total_hours += hours
        skill.last_practice = datetime.now().isoformat()
        if notes:
            skill.notes += f"\n{datetime.now().strftime('%Y-%m-%d')}: {notes}"
        
        self.save()
        return True
    
    def list_skills(self) -> List[Skill]:
        """列出所有技能"""
        return list(self.skills.values())
    
    # ===== 目标管理 =====
    
    def add_goal(self, title: str, description: str = "") -> Goal:
        """添加目标"""
        goal_id = f"goal_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        goal = Goal(id=goal_id, title=title, description=description)
        self.goals[goal_id] = goal
        self.save()
        return goal
    
    def update_goal(self, goal_id: str, progress: int) -> bool:
        """更新目标进度"""
        if goal_id not in self.goals:
            return False
        
        self.goals[goal_id].progress = min(100, max(0, progress))
        if progress >= 100:
            self.goals[goal_id].status = "completed"
        
        self.save()
        return True
    
    def complete_goal(self, goal_id: str) -> bool:
        """完成目标"""
        return self.update_goal(goal_id, 100)
    
    def delete_goal(self, goal_id: str) -> bool:
        """删除目标"""
        if goal_id not in self.goals:
            return False
        del self.goals[goal_id]
        self.save()
        return True
    
    def list_goals(self, status: str = None) -> List[Goal]:
        """列出目标"""
        goals = list(self.goals.values())
        if status:
            goals = [g for g in goals if g.status == status]
        return goals
