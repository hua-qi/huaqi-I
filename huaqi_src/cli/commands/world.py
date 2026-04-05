import datetime
from typing import Optional

import typer

from huaqi_src.layers.data.world.pipeline import WorldPipeline

world_app = typer.Typer(help="世界新闻采集")


@world_app.command("fetch")
def fetch_cmd(
    date: Optional[str] = typer.Option(None, "--date", help="采集日期 YYYY-MM-DD，默认今天"),
):
    target_date: Optional[datetime.date] = None
    if date:
        try:
            target_date = datetime.date.fromisoformat(date)
        except ValueError:
            typer.echo(f"日期格式错误: {date}，请使用 YYYY-MM-DD")
            raise typer.Exit(1)

    pipeline = WorldPipeline()
    success = pipeline.run(date=target_date)
    if not success:
        typer.echo("采集失败或未获取到任何文档")
        raise typer.Exit(1)
    typer.echo("采集完成")
