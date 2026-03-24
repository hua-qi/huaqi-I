"""记忆初始化器

帮助用户快速创建初始记忆档案
"""

from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.panel import Panel

from ..memory.storage.user_isolated import UserMemoryManager


console = Console()


@dataclass
class MemoryTemplate:
    """记忆模板"""
    name: str
    description: str
    filename: str
    template: str
    required_fields: list


# 预定义的记忆模板
TEMPLATES = {
    "identity": MemoryTemplate(
        name="身份档案",
        description="你的基本信息、价值观、人生目标",
        filename="identity/profile.md",
        template="""---
type: identity
created_at: {timestamp}
updated_at: {timestamp}
tags: [identity, core, profile]
---

# 👤 {display_name} 的身份档案

## 基本信息

- **姓名**: {name}
- **职业/身份**: {occupation}
- **当前阶段**: {life_stage}
- **所在城市**: {location}

## 核心价值观

{values}

## 人生目标

### 短期目标（1年内）
{short_term_goals}

### 长期目标（5年内）
{long_term_goals}

## 性格特点

{personality}

## 偏好与习惯

- **学习风格**: {learning_style}
- **工作节奏**: {work_style}
- **决策方式**: {decision_style}

## 重要关系

{relationships}

## 备注

{notes}

---
*此档案由 Huaqi 初始化创建，会随着对话自动更新*
""",
        required_fields=["name", "occupation", "life_stage"]
    ),
    
    "skills": MemoryTemplate(
        name="技能图谱",
        description="你正在学习或想要掌握的技能",
        filename="skills/learning_map.md",
        template="""---
type: skill
created_at: {timestamp}
updated_at: {timestamp}
tags: [skills, learning, growth]
---

# 🎯 技能学习图谱

## 当前正在学习

{current_skills}

## 计划学习

{planned_skills}

## 已掌握

{mastered_skills}

## 学习目标追踪

| 技能 | 开始时间 | 当前水平 | 目标水平 | 每周投入 |
|------|----------|----------|----------|----------|
{skill_table}

## 学习资源

{learning_resources}

---
*最后更新: {timestamp}*
""",
        required_fields=["current_skills"]
    ),
    
    "projects": MemoryTemplate(
        name="项目追踪",
        description="你正在进行的项目",
        filename="projects/active.md",
        template="""---
type: project
created_at: {timestamp}
updated_at: {timestamp}
tags: [projects, work, current]
---

# 🚀 进行中的项目

## 项目概览

{projects_overview}

## 详细项目

{projects_detail}

## 近期里程碑

{milestones}

---
*最后更新: {timestamp}*
""",
        required_fields=["projects_overview"]
    ),
    
    "daily_notes": MemoryTemplate(
        name="日常笔记模板",
        description="日常想法和记录的模板",
        filename="templates/daily_note.md",
        template="""---
type: note
date: {date}
tags: [daily, journal]
mood: {mood}
---

# 📓 {date} 笔记

## 今日关键词

{keywords}

## 想法与灵感

{thoughts}

## 待办事项

- [ ] {todo_1}
- [ ] {todo_2}

## 今日收获

{learnings}

---
""",
        required_fields=["date"]
    ),
}


class MemoryInitializer:
    """记忆初始化器"""
    
    def __init__(self, memory_manager: UserMemoryManager):
        self.memory_manager = memory_manager
        self.user_id = memory_manager.user_id
    
    def run_interactive(self):
        """交互式初始化向导"""
        console.print(Panel.fit(
            "🌸 欢迎来到 Huaqi 记忆初始化向导\n"
            "让我们一起创建你的初始记忆档案",
            title="记忆初始化",
            border_style="cyan"
        ))
        console.print()
        
        # 选择要创建的档案
        selected = self._select_templates()
        
        if not selected:
            console.print("[dim]已取消初始化[/dim]")
            return
        
        # 逐个创建
        for template_key in selected:
            template = TEMPLATES[template_key]
            console.print(f"\n[bold]创建: {template.name}[/bold]")
            console.print(f"[dim]{template.description}[/dim]\n")
            
            if template_key == "identity":
                self._create_identity()
            elif template_key == "skills":
                self._create_skills()
            elif template_key == "projects":
                self._create_projects()
            elif template_key == "daily_notes":
                self._create_daily_template()
        
        console.print("\n[green]✓ 初始化完成！[/green]")
        console.print("你可以随时通过对话来更新这些记忆。")
    
    def _select_templates(self) -> list:
        """选择要创建的模板"""
        console.print("[bold]请选择要创建的记忆档案:[/bold]\n")
        
        selected = []
        for key, template in TEMPLATES.items():
            if Confirm.ask(f"创建 {template.name}? ({template.description})", default=True):
                selected.append(key)
        
        return selected
    
    def _create_identity(self):
        """创建身份档案"""
        timestamp = datetime.now().isoformat()
        
        # 收集信息
        data = {
            "timestamp": timestamp,
            "display_name": Prompt.ask("你希望如何被称呼", default="朋友"),
            "name": Prompt.ask("你的姓名"),
            "occupation": Prompt.ask("你的职业/身份"),
            "life_stage": Prompt.ask("当前人生阶段", default="探索期"),
            "location": Prompt.ask("所在城市", default="未知"),
            "values": self._multi_line_input("你的核心价值观（每行一个）"),
            "short_term_goals": self._multi_line_input("短期目标（1年内，每行一个）"),
            "long_term_goals": self._multi_line_input("长期目标（5年内，每行一个）"),
            "personality": self._multi_line_input("描述一下你的性格特点"),
            "learning_style": Prompt.ask("你的学习风格", default="自主探索"),
            "work_style": Prompt.ask("你的工作节奏", default="灵活安排"),
            "decision_style": Prompt.ask("你的决策方式", default="先收集信息再凭直觉"),
            "relationships": self._multi_line_input("重要关系（家人、朋友、导师等）"),
            "notes": self._multi_line_input("其他备注", default="无"),
        }
        
        # 格式化并保存
        content = TEMPLATES["identity"].template.format(**data)
        self._save_memory(TEMPLATES["identity"].filename, content)
        
        console.print(f"[green]✓ 身份档案已创建[/green]")
    
    def _create_skills(self):
        """创建技能图谱"""
        timestamp = datetime.now().isoformat()
        
        console.print("\n[yellow]让我们记录你的技能学习情况[/yellow]\n")
        
        # 当前学习
        current = []
        console.print("[bold]当前正在学习的技能:[/bold] (输入空行结束)")
        while True:
            skill = Prompt.ask("技能名称", default="")
            if not skill:
                break
            level = Prompt.ask(f"{skill} 的当前水平", choices=["入门", "进阶", "熟练"], default="入门")
            current.append(f"- **{skill}**: {level}")
        
        # 计划学习
        planned = []
        console.print("\n[bold]计划学习的技能:[/bold] (输入空行结束)")
        while True:
            skill = Prompt.ask("技能名称", default="")
            if not skill:
                break
            planned.append(f"- {skill}")
        
        # 已掌握
        mastered = []
        console.print("\n[bold]已掌握的技能:[/bold] (输入空行结束)")
        while True:
            skill = Prompt.ask("技能名称", default="")
            if not skill:
                break
            mastered.append(f"- {skill}")
        
        data = {
            "timestamp": timestamp,
            "current_skills": "\n".join(current) if current else "- 暂无",
            "planned_skills": "\n".join(planned) if planned else "- 暂无",
            "mastered_skills": "\n".join(mastered) if mastered else "- 暂无",
            "skill_table": "| - | - | - | - | - |",  # 简化版
            "learning_resources": "- 待添加",
        }
        
        content = TEMPLATES["skills"].template.format(**data)
        self._save_memory(TEMPLATES["skills"].filename, content)
        
        console.print(f"[green]✓ 技能图谱已创建[/green]")
    
    def _create_projects(self):
        """创建项目追踪"""
        timestamp = datetime.now().isoformat()
        
        projects = []
        console.print("\n[bold]正在进行的项目:[/bold] (输入空行结束)\n")
        
        while True:
            name = Prompt.ask("项目名称", default="")
            if not name:
                break
            
            desc = Prompt.ask("项目描述", default="")
            status = Prompt.ask("项目状态", choices=["规划中", "进行中", "即将完成", "维护中"], default="进行中")
            priority = Prompt.ask("优先级", choices=["高", "中", "低"], default="中")
            
            projects.append({
                "name": name,
                "desc": desc,
                "status": status,
                "priority": priority,
            })
        
        # 格式化
        overview = "\n".join([f"- **{p['name']}** ({p['status']}) - {p['priority']}优先级" for p in projects])
        detail = "\n\n".join([f"### {p['name']}\n- 状态: {p['status']}\n- 优先级: {p['priority']}\n- 描述: {p['desc']}" for p in projects])
        
        data = {
            "timestamp": timestamp,
            "projects_overview": overview if overview else "- 暂无进行中的项目",
            "projects_detail": detail if detail else "暂无详细项目信息",
            "milestones": "- 待规划",
        }
        
        content = TEMPLATES["projects"].template.format(**data)
        self._save_memory(TEMPLATES["projects"].filename, content)
        
        console.print(f"[green]✓ 项目追踪已创建[/green]")
    
    def _create_daily_template(self):
        """创建日常笔记模板"""
        today = datetime.now().strftime("%Y-%m-%d")
        
        data = {
            "date": today,
            "mood": "😊",
            "keywords": "- ",
            "thoughts": "记录今天的想法...",
            "todo_1": "待办事项 1",
            "todo_2": "待办事项 2",
            "learnings": "今天学到了什么？",
        }
        
        content = TEMPLATES["daily_notes"].template.format(**data)
        self._save_memory(TEMPLATES["daily_notes"].filename, content)
        
        console.print(f"[green]✓ 日常笔记模板已创建[/green]")
    
    def _multi_line_input(self, prompt: str, default: str = "") -> str:
        """多行输入"""
        console.print(f"\n[bold]{prompt}[/bold] (输入空行结束):")
        lines = []
        while True:
            line = Prompt.ask("", default="")
            if not line:
                break
            lines.append(f"- {line}")
        
        return "\n".join(lines) if lines else default
    
    def _save_memory(self, relative_path: str, content: str):
        """保存记忆文件"""
        filepath = self.memory_manager.user_memory_dir / relative_path
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        return filepath
    
    def quick_init(self, **kwargs):
        """快速初始化（编程方式）"""
        timestamp = datetime.now().isoformat()
        
        # 创建最小化的身份档案
        identity_data = {
            "timestamp": timestamp,
            "display_name": kwargs.get("name", "朋友"),
            "name": kwargs.get("name", "未知"),
            "occupation": kwargs.get("occupation", "未知"),
            "life_stage": kwargs.get("life_stage", "探索期"),
            "location": kwargs.get("location", "未知"),
            "values": "- 成长\n- 创造",
            "short_term_goals": "- 探索新领域",
            "long_term_goals": "- 实现个人价值",
            "personality": "- 好奇心强\n- 喜欢学习",
            "learning_style": "自主探索",
            "work_style": "灵活安排",
            "decision_style": "理性分析",
            "relationships": "- 家人\n- 朋友",
            "notes": "通过快速初始化创建",
        }
        
        content = TEMPLATES["identity"].template.format(**identity_data)
        self._save_memory(TEMPLATES["identity"].filename, content)
        
        return True


def init_memory_command(memory_manager: UserMemoryManager, quick: bool = False, **kwargs):
    """初始化记忆命令入口"""
    initializer = MemoryInitializer(memory_manager)
    
    if quick:
        initializer.quick_init(**kwargs)
        console.print("[green]✓ 快速初始化完成[/green]")
    else:
        initializer.run_interactive()
