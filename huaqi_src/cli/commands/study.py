from typing import Optional

import typer
from rich.table import Table

from huaqi_src.cli.context import console

study_app = typer.Typer(name="study", help="学习助手 - 系统性学习技术", invoke_without_command=True)


def _get_store():
    from huaqi_src.core.config_paths import get_learning_dir
    from huaqi_src.learning.progress_store import LearningProgressStore

    try:
        return LearningProgressStore(get_learning_dir())
    except RuntimeError:
        console.print("[red]错误：数据目录未设置。请先运行 `huaqi config set data_dir <路径>`[/red]")
        raise typer.Exit(1)


@study_app.callback(invoke_without_command=True)
def study_main(
    ctx: typer.Context,
    skill: Optional[str] = typer.Argument(None, help="要学习的技术名称，如 rust、python"),
    list_courses: bool = typer.Option(False, "--list", "-l", help="列出所有课程进度"),
    reset: bool = typer.Option(False, "--reset", help="重置该课程进度"),
):
    """学习助手 - 生成大纲、讲解章节、出题考察"""
    if list_courses:
        _cmd_list()
        return

    if skill is None:
        console.print(ctx.get_help())
        return

    if reset:
        _cmd_reset(skill)
        return

    _cmd_start(skill)


def _cmd_list():
    store = _get_store()
    courses = store.list_courses()
    if not courses:
        console.print("[dim]暂无学习课程。使用 `huaqi study <技术名>` 开始学习。[/dim]")
        return

    table = Table(title="学习课程进度")
    table.add_column("技术", style="cyan")
    table.add_column("当前章节")
    table.add_column("进度")
    table.add_column("状态")

    for course in courses:
        completed = sum(1 for l in course.lessons if l.status == "completed")
        progress = f"{completed}/{course.total_lessons}"
        current_title = next(
            (l.title for l in course.lessons if l.index == course.current_lesson), "—"
        )
        status = "✅ 已完成" if completed == course.total_lessons else "▶️ 学习中"
        table.add_row(course.skill_name, f"第{course.current_lesson}章 {current_title}", progress, status)

    console.print(table)


def _cmd_reset(skill: str):
    from huaqi_src.learning.progress_store import slugify
    import shutil

    store = _get_store()
    slug = slugify(skill)
    course_dir = store.courses_dir / slug
    if not course_dir.exists():
        console.print(f"[yellow]未找到课程「{skill}」，无需重置。[/yellow]")
        return

    shutil.rmtree(course_dir)
    console.print(f"[green]✅ 已重置「{skill}」课程进度。[/green]")


def _cmd_start(skill: str):
    from huaqi_src.learning.learning_tools import start_lesson_tool

    console.print(f"\n[bold cyan]📚 启动学习：{skill}[/bold cyan]\n")

    try:
        result = start_lesson_tool.invoke({"skill": skill})
        console.print(result)
    except Exception as e:
        console.print(f"[red]启动学习失败：{e}[/red]")
        raise typer.Exit(1)
