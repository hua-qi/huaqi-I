import typer
import pty
import os
import sys
import re
import time
from typing import List
from huaqi_src.cli.context import ensure_initialized, console

proxy_app = typer.Typer(name="proxy", help="代理执行并采集外部 CLI 的交互记录")

def strip_ansi(text: str) -> str:
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

@proxy_app.command("run", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def proxy_run(ctx: typer.Context):
    """包装执行任意 CLI 命令，并拦截其输入输出存入事件数据库"""
    ensure_initialized()
    command = ctx.args
    if not command:
        console.print("[red]请提供要执行的命令，例如: huaqi proxy run codeflicker[/red]")
        raise typer.Exit(1)
        
    from huaqi_src.core.db_storage import LocalDBStorage
    from huaqi_src.core.event import Event
    
    db = LocalDBStorage()
    
    cmd_str = " ".join(command)
    console.print(f"[dim]🚀 正在代理执行: {cmd_str}[/dim]")
    
    output_buffer = []
    
    def read_interceptor(fd):
        try:
            data = os.read(fd, 1024)
        except OSError:
            return b""
        output_buffer.append(data)
        return data

    start_time = int(time.time())
    
    # 记录用户发起的命令
    db.insert_event(Event(
        timestamp=start_time,
        source="cli_proxy",
        actor="User",
        content=cmd_str,
        context_id=cmd_str
    ))
    
    try:
        # 使用 pty 衍生子进程并拦截
        pty.spawn(command, read_interceptor)
    except Exception as e:
        console.print(f"\n[red]执行出错: {e}[/red]")
        
    # 执行结束后，提取并清理输出
    full_output = b"".join(output_buffer).decode("utf-8", errors="ignore")
    clean_output = strip_ansi(full_output).strip()
    
    if clean_output:
        # 保存代理命令返回的内容
        db.insert_event(Event(
            timestamp=int(time.time()),
            source="cli_proxy",
            actor=command[0],
            content=clean_output,
            context_id=cmd_str
        ))
        
    console.print(f"\n[dim]✅ 交互已静默捕获并保存。[/dim]")

@proxy_app.callback(invoke_without_command=True)
def proxy_callback(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        ctx.get_help()
