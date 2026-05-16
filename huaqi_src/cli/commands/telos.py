"""TELOS 成长引擎 CLI 命令。"""
import typer

telos_app = typer.Typer(name="telos", help="TELOS 成长引擎管理")


@telos_app.command("distill")
def distill_command(
    limit: int = typer.Option(10, "--limit", "-l", help="每次最多处理的信号数"),
):
    """运行信号蒸馏——捞取未处理信号，提炼 TELOS 维度认知。"""
    from huaqi_src.cli.context import ensure_initialized
    from huaqi_src.layers.capabilities.telos_distiller import run_distillation

    ensure_initialized()

    print(f"开始蒸馏（上限 {limit} 条）...")
    result = run_distillation(limit=limit)
    print(f"完成：处理 {result['processed']} 条，失败 {result['errors']} 条")
