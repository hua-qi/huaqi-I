import uuid
import typer
from typing import Optional
from rich.console import Console
from rich.table import Table

from huaqi_src.people.graph import PeopleGraph
from huaqi_src.people.models import Person

people_app = typer.Typer(name="people", help="管理人物关系网络")
console = Console()


@people_app.command("list")
def list_people():
    """列出所有关系人（按亲密度排序）"""
    graph = PeopleGraph()
    people = graph.list_people()
    if not people:
        console.print("[dim]暂无关系人数据[/dim]")
        return
    people.sort(key=lambda p: p.interaction_frequency, reverse=True)
    table = Table(title="关系网络")
    table.add_column("姓名")
    table.add_column("关系")
    table.add_column("情感倾向")
    table.add_column("近30天互动")
    for p in people:
        table.add_row(p.name, p.relation_type, p.emotional_impact, str(p.interaction_frequency))
    console.print(table)


@people_app.command("show")
def show_person(name: str = typer.Argument(..., help="人物姓名")):
    """查看某人详细画像"""
    graph = PeopleGraph()
    person = graph.get_person(name)
    if person is None:
        console.print(f"[red]未找到 '{name}'[/red]")
        return
    console.print(f"\n[bold]{person.name}[/bold]")
    console.print(f"关系类型: {person.relation_type}")
    console.print(f"情感倾向: {person.emotional_impact}（huaqi 的观察）")
    console.print(f"近30天互动: {person.interaction_frequency} 次")
    if person.alias:
        console.print(f"别名: {', '.join(person.alias)}")
    if person.profile:
        console.print(f"\n[bold]画像:[/bold]\n{person.profile}")
    if person.notes:
        console.print(f"\n[bold]备注:[/bold]\n{person.notes}")


@people_app.command("add")
def add_person(
    name: str = typer.Argument(..., help="姓名"),
    relation: str = typer.Option("其他", "--relation", "-r", help="关系类型"),
):
    """手动添加关系人"""
    graph = PeopleGraph()
    if graph.get_person(name) is not None:
        console.print(f"[yellow]'{name}' 已存在，使用 'huaqi people note' 更新备注[/yellow]")
        return
    person = Person(
        person_id=f"{name}-{uuid.uuid4().hex[:8]}",
        name=name,
        relation_type=relation,
    )
    graph.add_person(person)
    console.print(f"[green]已添加 '{name}'（{relation}）[/green]")


@people_app.command("note")
def add_note(
    name: str = typer.Argument(..., help="人物姓名"),
    text: str = typer.Argument(..., help="备注内容"),
):
    """为某人添加备注"""
    graph = PeopleGraph()
    success = graph.update_person(name, notes=text)
    if not success:
        console.print(f"[red]未找到 '{name}'[/red]")
        return
    console.print(f"[green]已更新 '{name}' 的备注[/green]")


@people_app.command("delete")
def delete_person(
    name: str = typer.Argument(..., help="人物姓名"),
    yes: bool = typer.Option(False, "--yes", "-y", help="跳过确认"),
):
    """删除某人数据（隐私保护）"""
    if not yes:
        confirm = typer.confirm(f"确定删除 '{name}' 的所有数据？此操作不可撤销")
        if not confirm:
            return
    graph = PeopleGraph()
    success = graph.delete_person(name)
    if not success:
        console.print(f"[red]未找到 '{name}'[/red]")
        return
    console.print(f"[green]已删除 '{name}' 的所有数据[/green]")
