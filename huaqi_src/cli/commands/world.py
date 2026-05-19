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


def _load_user_context() -> str | None:
    """从 TELOS 加载用户画像摘要，用于个性化新闻建议。"""
    try:
        from huaqi_src.config.paths import require_data_dir
        from huaqi_src.layers.growth.telos.manager import TelosManager

        data_dir = require_data_dir()
        telos_dir = data_dir / "telos"
        if not telos_dir.exists():
            return None
        manager = TelosManager(telos_dir=telos_dir, git_commit=False)
        active = manager.list_active()
        if not active:
            return None
        # 提取全部维度
        labels = {
            "beliefs": "核心信念", "models": "心理模型", "narratives": "自我叙事",
            "goals": "当前目标", "challenges": "当前挑战", "strategies": "应对策略",
            "learned": "最近所学", "shadows": "盲点/短板",
        }
        parts = []
        for dim in active:
            if dim.content.strip():
                label = labels.get(dim.name, dim.name)
                parts.append(f"{label}：{dim.content.strip()}")
        return "\n".join(parts) if parts else None
    except Exception:
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
        if enricher is None:
            typer.echo("[World] 未配置 LLM（缺少 OPENAI_API_KEY 或初始化失败），跳过内容增强", err=True)
        else:
            typer.echo("[World] 正在翻译和扩展新闻内容...")
            user_context = _load_user_context()
            if enricher.enrich_file(saved_path, user_context=user_context):
                typer.echo("[World] 内容增强完成")
            else:
                typer.echo("[World] 错误：内容增强失败，请检查 API Key 和网络连接", err=True)
                raise typer.Exit(1)

    typer.echo("采集完成")


@world_app.command("enrich")
def enrich_cmd(
    date: str = typer.Option(..., "--date", help="要增强的日期 YYYY-MM-DD"),
):
    """对指定日期的世界新闻文件单独执行 LLM 增强（不重新采集）。"""
    from pathlib import Path
    from huaqi_src.config.paths import require_data_dir

    try:
        target_date = datetime.date.fromisoformat(date)
    except ValueError:
        typer.echo(f"日期格式错误: {date}，请使用 YYYY-MM-DD", err=True)
        raise typer.Exit(1)

    data_dir = require_data_dir()
    file_path = Path(data_dir) / "world" / f"{target_date.isoformat()}.md"
    if not file_path.exists():
        typer.echo(f"文件不存在: {file_path}", err=True)
        raise typer.Exit(1)

    enricher = _build_enricher()
    if enricher is None:
        typer.echo("无法初始化 LLM 增强器（请确认 OPENAI_API_KEY 已设置）", err=True)
        raise typer.Exit(1)

    typer.echo(f"[World] 正在增强 {file_path} ...")
    user_context = _load_user_context()
    if enricher.enrich_file(file_path, user_context=user_context):
        typer.echo("[World] 内容增强完成")
    else:
        typer.echo("[World] 内容增强失败", err=True)
        raise typer.Exit(1)
