import datetime
import os
from typing import Optional

import typer

from huaqi_src.layers.data.world.pipeline import WorldPipeline

world_app = typer.Typer(help="世界新闻采集")


def _build_enricher():
    """从环境变量构建 WorldNewsEnricher（如果 LLM 可用）。"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from huaqi_src.layers.capabilities.llm.manager import LLMManager, LLMConfig
        from huaqi_src.layers.capabilities.world_news_enricher import WorldNewsEnricher

        llm = LLMManager()
        llm.add_config(LLMConfig(
            provider="openai",
            model=os.environ.get("HUAQI_ENRICH_MODEL", "gpt-4o-mini"),
            api_key=api_key,
            temperature=0.3,
            max_tokens=8000,
            timeout=120,
        ))
        llm.set_active("openai")
        return WorldNewsEnricher(llm)
    except Exception as e:
        typer.echo(f"[World] 增强器初始化失败: {e}")
        return None


@world_app.command("fetch")
def fetch_cmd(
    date: Optional[str] = typer.Option(None, "--date", help="采集日期 YYYY-MM-DD，默认今天"),
    no_enrich: bool = typer.Option(False, "--no-enrich", help="跳过 LLM 翻译/扩展"),
):
    target_date: Optional[datetime.date] = None
    if date:
        try:
            target_date = datetime.date.fromisoformat(date)
        except ValueError:
            typer.echo(f"日期格式错误: {date}，请使用 YYYY-MM-DD")
            raise typer.Exit(1)

    pipeline = WorldPipeline()
    saved_path = pipeline.run(date=target_date)
    if saved_path is None:
        typer.echo("采集失败或未获取到任何文档")
        raise typer.Exit(1)

    if not no_enrich:
        enricher = _build_enricher()
        if enricher:
            typer.echo("[World] 正在翻译和扩展新闻内容...")
            if enricher.enrich_file(saved_path):
                typer.echo("[World] 内容增强完成")
            else:
                typer.echo("[World] 内容增强失败，保留原始内容")
        else:
            typer.echo("[World] 未配置 LLM，跳过内容增强")

    typer.echo("采集完成")
