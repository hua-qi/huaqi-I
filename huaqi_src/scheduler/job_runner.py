import datetime
from pathlib import Path
from typing import Optional


_JOB_FILENAME_MAP = {
    "morning_brief": lambda dt: f"{dt.strftime('%Y-%m-%d')}-morning.md",
    "daily_report": lambda dt: f"{dt.strftime('%Y-%m-%d')}-evening.md",
    "weekly_report": lambda dt: f"{dt.strftime('%Y-W%W')}.md",
    "quarterly_report": lambda dt: f"{dt.strftime('%Y')}-Q{(dt.month - 1) // 3 + 1}.md",
    "learning_daily_push": lambda dt: f"{dt.strftime('%Y-%m-%d')}-learning.md",
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
    filename = get_job_output_filename(job_id, scheduled_at) if output_dir else None
    full_path = str(Path(output_dir).expanduser() / filename) if output_dir and filename else None

    try:
        content = _call_llm_for_job(job_id, prompt)
        if full_path and content:
            path = Path(full_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            print(f"[Scheduler] 任务结果已写入: {full_path}")
        elif full_path:
            print(f"[Scheduler] LLM 未返回有效内容，跳过写入: {full_path}")
    except Exception as e:
        print(f"[Scheduler] 任务 {job_id} 执行失败: {e}")
        if raise_on_error:
            raise


_LEARNING_PUSH_SYSTEM_PROMPT = """你是 huaqi，用户的学习同伴。请根据用户当前的学习进度，从进行中的课程中选取一个知识点，出1-2道复习题。格式要求：

1. 简要说明所选课程和知识点
2. 出1-2道题目（选择题或简答题均可）
3. 给出答案解析
4. 最后附上一句鼓励的话

语气温暖有洞察力，内容要具体，不要泛泛而谈。"""


def _build_learning_context() -> str:
    """为学习推送构建学习进度上下文。"""
    try:
        from huaqi_src.config.paths import get_data_dir
        from huaqi_src.layers.capabilities.learning.progress_store import LearningProgressStore

        data_dir = get_data_dir()
        if data_dir is None:
            return "暂无学习数据。"

        store = LearningProgressStore(base_dir=data_dir / "learning")
        courses = store.list_courses()
        if not courses:
            return "暂无进行中的课程。"

        lines = ["## 当前学习进度"]
        for course in courses:
            completed = sum(1 for l in course.lessons if l.status == "completed")
            total = course.total_lessons
            in_progress = [l for l in course.lessons if l.status == "in_progress"]
            current = in_progress[0] if in_progress else None
            lines.append(f"\n### {course.skill_name}（{completed}/{total} 章完成）")
            if current:
                lines.append(f"当前章节：{current.title}")
            recent = [l for l in course.lessons if l.status == "completed"][-3:]
            if recent:
                lines.append("最近完成：" + "、".join(l.title for l in recent))

        return "\n".join(lines)
    except Exception as e:
        return f"学习数据加载失败: {e}"


def _call_llm_for_job(job_id: str, prompt: str) -> str:
    """直接调用 LLM 执行定时任务，不走 ChatAgent。"""
    from langchain_core.messages import SystemMessage, HumanMessage
    from huaqi_src.cli.context import build_llm_manager

    llm_mgr = build_llm_manager(temperature=0.7, max_tokens=800)
    if llm_mgr is None:
        return "（LLM 未配置）"

    if not llm_mgr._active_provider:
        return "（未配置任何 LLM 提供商）"
    cfg = llm_mgr._active_provider.config

    from langchain_openai import ChatOpenAI
    llm = ChatOpenAI(
        model=cfg.model,
        api_key=cfg.api_key,
        base_url=cfg.api_base or None,
        temperature=0.7,
        max_tokens=800,
    )

    if job_id == "learning_daily_push":
        system_prompt = _LEARNING_PUSH_SYSTEM_PROMPT
        context = _build_learning_context()
        user_message = f"{prompt}\n\n{context}"
    else:
        system_prompt = f"你是 huaqi，用户的 AI 同伴。请执行以下定时任务：「{job_id}」。"
        user_message = prompt

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_message),
    ])
    return response.content
