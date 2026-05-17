"""huaqi prompts 命令：浏览和管理提示词文件。"""

import typer
from rich.table import Table

from huaqi_src.cli.context import console

prompts_app = typer.Typer(
    name="prompts",
    help="浏览和管理提示词文件",
    no_args_is_help=True,
)


@prompts_app.command("list")
def prompts_list():
    """列出所有提示词及其功能描述。"""
    from huaqi_src.prompts.loader import get_prompt_loader
    from huaqi_src.prompts.initializer import get_prompts_initializer

    try:
        loader = get_prompt_loader()
    except RuntimeError as e:
        console.print(f"[red]数据目录未初始化: {e}[/red]")
        return

    prompts_dir = loader.prompts_dir
    init = get_prompts_initializer(prompts_dir)
    init.ensure()

    scenes = init.get_all_scenes()
    if not scenes:
        console.print("[dim]暂无提示词文件[/dim]")
        return

    table = Table(title="提示词文件列表")
    table.add_column("文件", style="cyan")
    table.add_column("场景 ID", style="green")
    table.add_column("影响功能", style="yellow")

    for scene_id in sorted(scenes):
        file_path = prompts_dir / f"{scene_id.replace('.', '/')}.md"
        rel_path = file_path.relative_to(prompts_dir)
        description = _describe_scene(scene_id)
        table.add_row(str(rel_path), scene_id, description)

    console.print()
    console.print(table)
    console.print(f"\n[dim]提示词目录: {prompts_dir}[/dim]")
    console.print("[dim]编辑任意 .md 文件后无需重启，下次调用即刻生效。[/dim]")


_SCENE_DESCRIPTIONS: dict[str, str] = {
    "base": "角色基线，所有场景的 system prompt 开头",
    "agent.chat": "LangGraph Agent 对话系统提示词",
    "cli.chat": "传统 CLI 对话模式系统提示词",
    "scheduler.jobs.morning_brief": "晨间简报定时任务",
    "scheduler.jobs.daily_report": "日终复盘定时任务",
    "scheduler.jobs.weekly_report": "周报定时任务",
    "scheduler.jobs.quarterly_report": "季报定时任务",
    "scheduler.jobs.learning_daily_push": "每日学习推送定时任务",
    "scheduler.jobs.world_fetch": "世界新闻采集定时任务",
    "scheduler.job_runner": "定时任务执行器 system prompt",
    "scheduler.job_runner.learning": "学习推送执行器 system prompt",
    "layers.capabilities.reports.morning": "晨间简报生成",
    "layers.capabilities.reports.daily": "日终复盘生成",
    "layers.capabilities.reports.weekly": "周报生成",
    "layers.capabilities.reports.quarterly": "季报生成",
    "layers.capabilities.reports.growth": "成长报告生成",
    "layers.growth.telos.engine.step1": "TELOS 引擎：信号分析",
    "layers.growth.telos.engine.step3": "TELOS 引擎：更新决策",
    "layers.growth.telos.engine.step4": "TELOS 引擎：内容生成",
    "layers.growth.telos.engine.step5": "TELOS 引擎：成长事件判断",
    "layers.growth.telos.engine.review_stale": "TELOS 引擎：过时复审",
    "layers.growth.telos.engine.step345": "TELOS 引擎：组合更新",
    "layers.growth.telos.context.chat": "TELOS 上下文：对话模式",
    "layers.growth.telos.context.onboarding": "TELOS 上下文：引导模式",
    "layers.growth.telos.context.report": "TELOS 上下文：报告模式",
    "layers.growth.telos.context.distill": "TELOS 上下文：提炼模式",
    "layers.growth.telos.dimensions.people.extractor": "人物提取",
    "layers.growth.telos.dimensions.people.pipeline": "人物管道分析",
    "layers.capabilities.world_news_enricher": "世界新闻增强/翻译",
    "layers.capabilities.learning.outline": "课程大纲生成",
    "layers.capabilities.learning.lesson": "课程内容生成",
    "layers.capabilities.learning.quiz": "测验题目生成",
    "layers.capabilities.learning.feedback": "学习反馈评价",
    "layers.capabilities.onboarding.telos_generator": "冷启动 TELOS 生成",
    "layers.capabilities.personality.engine": "个性引擎系统提示词",
    "layers.capabilities.personality.updater": "人格画像更新分析",
    "layers.data.profile.narrative": "用户画像叙事生成",
    "layers.data.profile.extract": "用户信息提取",
    "layers.data.memory.relevance": "记忆相关性判断",
}


def _describe_scene(scene_id: str) -> str:
    if scene_id in _SCENE_DESCRIPTIONS:
        return _SCENE_DESCRIPTIONS[scene_id]
    parts = scene_id.split(".")
    if parts[0] == "scheduler" and "jobs" in parts:
        return "定时任务提示词"
    return "自定义提示词"
