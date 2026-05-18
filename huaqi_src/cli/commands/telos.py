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


@telos_app.command("backfill")
def backfill_command(
    user_id: str = typer.Option("default", "--user-id", "-u", help="用户 ID"),
):
    """从 checkpoints.db 回填 RawSignal——将历史对话转为信号。"""
    from pathlib import Path
    from huaqi_src.cli.context import ensure_initialized
    from huaqi_src.config.paths import require_data_dir
    from huaqi_src.config.adapters.storage import SQLiteStorageAdapter
    from huaqi_src.layers.data.raw_signal.store import RawSignalStore
    from huaqi_src.layers.data.raw_signal.backfill import backfill_from_checkpoints

    ensure_initialized()
    data_dir = require_data_dir()

    signal_store = RawSignalStore(
        adapter=SQLiteStorageAdapter(db_path=data_dir / "raw_signals.db")
    )
    result = backfill_from_checkpoints(
        checkpoints_db_path=data_dir / "checkpoints.db",
        signal_store=signal_store,
        user_id=user_id,
    )
    print(
        f"回填完成：新增 {result['backfilled']} 条，"
        f"跳过 {result['skipped']} 条（已存在），"
        f"失败 {result['errors']} 条"
    )
