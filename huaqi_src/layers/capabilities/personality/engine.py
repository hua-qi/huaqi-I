"""个性引擎

配置存储在 memory/personality.yaml
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from pathlib import Path
import yaml


@dataclass
class PersonalityProfile:
    """个性档案"""
    name: str = "Huaqi"
    version: str = "1.0"
    
    # 性格维度
    openness: float = 0.5
    conscientiousness: float = 0.7
    extraversion: float = 0.3
    agreeableness: float = 0.8
    neuroticism: float = -0.3
    
    # 沟通风格
    tone: str = "warm"
    formality: float = 0.4
    verbosity: float = 0.6
    humor: float = 0.3
    empathy: float = 0.8
    
    # 价值观
    values: List[str] = field(default_factory=lambda: [
        "成长优于稳定",
        "真诚优于讨好",
        "引导优于指令",
        "长期优于短期"
    ])
    
    # 角色定位
    role: str = "同伴"
    relationship: str = "peer"
    
    # 语言偏好
    language_style: str = "zh"
    use_emoji: bool = True
    use_markdown: bool = True
    
    # 行为模式
    proactivity: float = 0.5
    follow_up: bool = True
    give_advice: bool = True
    challenge_user: bool = True
    
    # 自定义
    custom_traits: Dict[str, Any] = field(default_factory=dict)


class PersonalityEngine:
    """个性引擎 - 单用户"""
    
    PRESETS = {
        "companion": PersonalityProfile(name="Huaqi", tone="warm", role="同伴", empathy=0.8),
        "mentor": PersonalityProfile(name="Huaqi", tone="professional", role="导师", challenge_user=True),
        "friend": PersonalityProfile(name="Huaqi", tone="playful", role="朋友", humor=0.6),
        "assistant": PersonalityProfile(name="Huaqi", tone="professional", role="助手", formality=0.7),
    }
    
    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir
        self.profile_path = memory_dir / "personality.yaml"
        self.profile = self._load_or_create()
    
    def _load_or_create(self) -> PersonalityProfile:
        """加载或创建个性档案"""
        if self.profile_path.exists():
            with open(self.profile_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return PersonalityProfile(**data)
        
        profile = PersonalityProfile()
        self.save(profile)
        return profile
    
    def save(self, profile: PersonalityProfile = None):
        """保存个性档案"""
        if profile is None:
            profile = self.profile
        
        with open(self.profile_path, "w", encoding="utf-8") as f:
            yaml.dump(asdict(profile), f, allow_unicode=True)
    
    def apply_preset(self, preset_name: str):
        """应用预设"""
        if preset_name in self.PRESETS:
            self.profile = self.PRESETS[preset_name]
            self.save()
    
    def update(self, **kwargs):
        """更新个性参数"""
        for key, value in kwargs.items():
            if hasattr(self.profile, key):
                setattr(self.profile, key, value)
        self.save()
    
    def to_prompt(self) -> str:
        """转换为系统提示词，优先从 PromptLoader 加载模板。"""
        p = self.profile
        proactivity_text = "主动关心用户的进展" if p.proactivity > 0.5 else "等待用户主动分享"
        challenge_text = "适当挑战用户的想法" if p.challenge_user else "支持用户的决定"
        advice_text = "适时给出建议" if p.give_advice else "倾听为主"
        emoji_text = "适当使用 emoji" if p.use_emoji else "保持专业"
        markdown_text = "可以使用 Markdown" if p.use_markdown else "使用纯文本"

        try:
            from huaqi_src.prompts.loader import get_prompt_loader
            loader = get_prompt_loader()
            system, _ = loader.load(
                "layers.capabilities.personality.engine",
                name=p.name, role=p.role, tone=p.tone,
                formality=p.formality, empathy=p.empathy,
                values="\n".join(f"- {v}" for v in p.values),
                proactivity_text=proactivity_text,
                challenge_text=challenge_text,
                advice_text=advice_text,
                language_style=p.language_style,
                emoji_text=emoji_text,
                markdown_text=markdown_text,
            )
            return system or ""
        except Exception:
            return (
                f"你是 {p.name}，用户的个人 AI {p.role}。\n"
                f"\n"
                f"沟通风格: {p.tone}\n"
                f"正式程度: {p.formality}\n"
                f"共情水平: {p.empathy}\n"
                f"\n"
                f"价值观:\n"
                f"{chr(10).join(f'- {v}' for v in p.values)}\n"
                f"\n"
                f"行为准则:\n"
                f"- {proactivity_text}\n"
                f"- {challenge_text}\n"
                f"- {advice_text}\n"
                f"\n"
                f"语言风格:\n"
                f"- 使用 {p.language_style} 交流\n"
                f"- {emoji_text}\n"
                f"- {markdown_text}\n"
            )
