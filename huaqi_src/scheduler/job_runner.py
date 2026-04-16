import datetime
from pathlib import Path
from typing import Optional


_JOB_FILENAME_MAP = {
    "morning_brief": lambda dt: f"{dt.strftime('%Y-%m-%d')}-morning.md",
    "daily_report": lambda dt: f"{dt.strftime('%Y-%m-%d')}-evening.md",
    "weekly_report": lambda dt: f"{dt.strftime('%Y-W%W')}.md",
    "quarterly_report": lambda dt: f"{dt.strftime('%Y')}-Q{(dt.month - 1) // 3 + 1}.md",
}


def get_job_output_filename(job_id: str, scheduled_at: Optional[datetime.datetime] = None) -> str:
    dt = scheduled_at or datetime.datetime.now()
    if job_id in _JOB_FILENAME_MAP:
        return _JOB_FILENAME_MAP[job_id](dt)
    return f"{job_id}_{dt.strftime('%Y%m%d_%H%M%S')}.md"


def _run_scheduled_job(
    job_id: str,
    prompt: str,
    output_dir: Optional[str],
    scheduled_at: Optional[datetime.datetime] = None,
    raise_on_error: bool = False,
):
    from huaqi_src.agent.chat_agent import ChatAgent
    full_prompt = prompt
    if output_dir:
        filename = get_job_output_filename(job_id, scheduled_at)
        full_path = str(Path(output_dir).expanduser() / filename)
        full_prompt = (
            f"[系统] 你正在执行定时任务「{job_id}」，请将最终结果用 write_file_tool 写入文件：{full_path}\n\n"
            + prompt
        )
    try:
        agent = ChatAgent()
        agent.run(full_prompt)
    except Exception as e:
        print(f"[Scheduler] 任务 {job_id} 执行失败: {e}")
        if raise_on_error:
            raise
