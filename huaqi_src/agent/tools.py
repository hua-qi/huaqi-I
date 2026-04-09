from langchain_core.tools import tool
from huaqi_src.layers.data.diary import DiaryStore

_TOOL_REGISTRY: list = []

def register_tool(fn):
    _TOOL_REGISTRY.append(fn)
    return fn
from huaqi_src.config.paths import (
    get_memory_dir,
    get_work_docs_dir,
    get_cli_chats_dir,
    get_conversations_dir,
)
import datetime
from huaqi_src.layers.data.events.store import LocalDBStorage

@register_tool
@tool
def search_diary_tool(query: str) -> str:
    """搜索用户的历史日记内容。当用户询问过去发生的事情、特定的回忆或关键词（如kaleido）时使用。"""
    store = DiaryStore(get_memory_dir())
    results = store.search(query)
    
    if not results:
        return f"未找到包含 '{query}' 的相关日记。"
        
    formatted_results = [f"日期: {r.date}\n内容: {r.content}" for r in results[:3]]
    return "找到以下日记记录：\n\n" + "\n---\n".join(formatted_results)

@register_tool
@tool
def search_work_docs_tool(query: str) -> str:
    """搜索用户已导入的工作文档、笔记和项目文档。当用户询问与工作相关的内容时使用。"""
    try:
        work_docs_dir = get_work_docs_dir()
    except RuntimeError:
        return "未找到工作文档（数据目录未设置）。"

    if not work_docs_dir.exists():
        return f"未找到包含 '{query}' 的工作文档。"

    results = []
    query_lower = query.lower()
    for doc_file in sorted(work_docs_dir.iterdir()):
        if doc_file.suffix.lower() not in {".md", ".txt"}:
            continue
        try:
            content = doc_file.read_text(encoding="utf-8")
            if query_lower in content.lower():
                results.append(f"文件: {doc_file.name}\n内容摘要: {content[:300]}")
        except Exception:
            continue

    if not results:
        return f"未找到包含 '{query}' 的工作文档。"

    return "找到以下工作文档：\n\n" + "\n---\n".join(results[:3])

@register_tool
@tool
def search_events_tool(query: str) -> str:
    """搜索用户的CLI命令行等历史交互记录。当用户询问系统交互记录、自己说过什么或者系统事件时使用。"""
    db = LocalDBStorage()
    results = db.search_events(query, limit=5)
    
    if not results:
        return f"未找到包含 '{query}' 的相关交互记录。"
        
    formatted_results = []
    for r in results:
        dt = datetime.datetime.fromtimestamp(r.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        formatted_results.append(f"时间: {dt}\n来源: {r.source}\n用户: {r.actor}\n内容: {r.content}")
        
    return "找到以下历史交互记录：\n\n" + "\n---\n".join(formatted_results)

@register_tool
@tool
def search_worldnews_tool(query: str) -> str:
    """搜索最近的世界新闻和热点事件摘要。当用户询问最新世界动态、新闻或时事时使用。"""
    from huaqi_src.layers.data.world.storage import WorldNewsStorage

    try:
        storage = WorldNewsStorage()
        results = storage.search(query, days=7)
    except RuntimeError:
        return f"未找到关于 '{query}' 的世界新闻（数据目录未设置）。"

    if not results:
        return f"本地未找到关于 '{query}' 的近期世界新闻。请立即调用 google_search_tool 在互联网上搜索。"

    return "找到以下相关世界新闻：\n\n" + "\n---\n".join(results[:3])


@register_tool
@tool
def search_person_tool(name: str) -> str:
    """查询某人的画像和互动历史。当用户询问某个人的信息、与某人的关系、某人的性格特点时使用。"""
    from huaqi_src.layers.growth.telos.dimensions.people.graph import PeopleGraph
    try:
        graph = PeopleGraph()
    except RuntimeError:
        return f"未找到 '{name}' 的相关信息（数据目录未设置）。"

    person = graph.get_person(name)
    if person is None:
        results = graph.search(name)
        if not results:
            return f"未找到 '{name}' 的相关信息。"
        person = results[0]

    lines = [
        f"姓名: {person.name}",
        f"关系类型: {person.relation_type}",
        f"情感倾向: {person.emotional_impact}（huaqi 的观察）",
        f"近30天互动次数: {person.interaction_frequency}",
    ]
    if person.alias:
        lines.append(f"别名: {', '.join(person.alias)}")
    if person.profile:
        lines.append(f"画像: {person.profile}")
    if person.notes:
        lines.append(f"备注: {person.notes}")

    return "\n".join(lines)



@register_tool
@tool
def search_cli_chats_tool(query: str) -> str:
    """搜索用户与其他 CLI Agent（如 codeflicker、Claude）的对话记录。
    支持按日期查询，例如「今天」「昨天」「4月8日」「2026-04-08」。
    当用户询问曾经的编程问题、讨论过的技术方案、某天做了什么时使用。
    """
    import re as _re
    try:
        cli_chats_dir = get_cli_chats_dir()
    except RuntimeError:
        return f"未找到包含 '{query}' 的 CLI 对话记录（数据目录未设置）。"

    if not cli_chats_dir.exists():
        return f"未找到包含 '{query}' 的 CLI 对话记录。"

    codeflicker_dir = cli_chats_dir / "codeflicker"

    target_date = _parse_date_from_query(query)

    results = []
    query_lower = query.lower()

    if codeflicker_dir.exists():
        if target_date:
            year, month, day = target_date[:4], target_date[5:7], target_date[8:10]
            day_dir = codeflicker_dir / year / month / day
            day_dirs = [day_dir] if day_dir.exists() else []
        else:
            day_dirs = sorted(
                (d for y in codeflicker_dir.iterdir() if y.is_dir()
                 for m in y.iterdir() if m.is_dir()
                 for d in m.iterdir() if d.is_dir()),
                reverse=True
            )[:7]

        for date_dir in day_dirs:
            if not date_dir.is_dir():
                continue
            date_label = f"{date_dir.parent.parent.name}-{date_dir.parent.name}-{date_dir.name}"
            for md_file in sorted(date_dir.glob("*.md"), reverse=True):
                try:
                    content = md_file.read_text(encoding="utf-8")
                    if target_date or query_lower in content.lower():
                        session_id = md_file.stem
                        lines = content.splitlines()
                        branch = next((l.split("git_branch:")[-1].strip() for l in lines if "git_branch:" in l), "")
                        preview = "\n".join(
                            l for l in lines if l.startswith("[") and "[user]:" in l
                        )[:200]
                        results.append(
                            f"日期: {date_label} | session: {session_id}"
                            + (f" | 分支: {branch}" if branch else "")
                            + f"\n{preview}"
                        )
                except Exception:
                    continue

    for md_file in sorted(cli_chats_dir.rglob("*.md"), reverse=True):
        if "codeflicker" in str(md_file):
            continue
        try:
            content = md_file.read_text(encoding="utf-8")
            if query_lower in content.lower():
                results.append(f"文件: {md_file.parent.name}/{md_file.name}\n摘要: {content[:300]}")
        except Exception:
            continue
        if len(results) >= 10:
            break

    if not results:
        if target_date:
            return f"未找到 {target_date} 的 codeflicker 对话记录。"
        return f"未找到包含 '{query}' 的 CLI 对话记录。"
    return "找到以下 CLI 对话记录：\n\n" + "\n---\n".join(results[:5])


def _parse_date_from_query(query: str) -> str:
    """从 query 中识别日期，返回 YYYY-MM-DD 或空字符串"""
    import re
    import datetime as _dt

    today = _dt.date.today()
    q = query.lower()

    if "今天" in q or "today" in q:
        return today.strftime("%Y-%m-%d")
    if "昨天" in q or "yesterday" in q:
        return (today - _dt.timedelta(days=1)).strftime("%Y-%m-%d")
    if "前天" in q:
        return (today - _dt.timedelta(days=2)).strftime("%Y-%m-%d")

    m = re.search(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", query)
    if m:
        raw = m.group(1).replace("/", "-")
        try:
            return _dt.date.fromisoformat(raw).strftime("%Y-%m-%d")
        except ValueError:
            pass

    m = re.search(r"(\d{1,2})月(\d{1,2})日?", query)
    if m:
        month, day = int(m.group(1)), int(m.group(2))
        year = today.year
        try:
            return _dt.date(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass

    return ""


@register_tool
@tool
def get_relationship_map_tool() -> str:
    """获取用户的关系网络全图，按亲密度排序列出所有关系人。当用户询问「我认识哪些人」「我的社交圈」时使用。"""
    from huaqi_src.layers.growth.telos.dimensions.people.graph import PeopleGraph
    try:
        graph = PeopleGraph()
    except RuntimeError:
        return "暂无关系人数据（数据目录未设置）。"

    people = graph.list_people()
    if not people:
        return "暂无关系人数据。"

    people.sort(key=lambda p: p.interaction_frequency, reverse=True)
    lines = ["你的关系网络：", ""]
    for p in people:
        line = f"- {p.name}（{p.relation_type}）"
        if p.interaction_frequency > 0:
            line += f"，近30天互动 {p.interaction_frequency} 次"
        if p.emotional_impact != "中性":
            line += f"，{p.emotional_impact}影响"
        lines.append(line)

    return "\n".join(lines)


@register_tool
@tool
def search_huaqi_chats_tool(query: str) -> str:
    """搜索用户与 Huaqi 的历史对话记录。
    当用户询问「我之前说过什么」「你还记得...吗」「上次我们聊了什么」
    「今天我有没有提到...」等涉及过往 huaqi 对话的问题时使用。
    支持自然语言查询，也支持「今天」「昨天」「上周」等时间描述。
    """
    from pathlib import Path
    from huaqi_src.config.paths import get_data_dir
    from huaqi_src.layers.data.memory.storage.markdown_store import MarkdownMemoryStore

    data_dir = get_data_dir()
    if data_dir is None:
        return f"未找到与 Huaqi 的历史对话（数据目录未设置）。"

    conversations_dir = get_conversations_dir()
    if not conversations_dir.exists():
        return f"未找到包含 '{query}' 的 Huaqi 对话记录。"

    store = MarkdownMemoryStore(conversations_dir)

    vector_results = []
    try:
        from huaqi_src.layers.data.memory.vector import get_hybrid_search
        search = get_hybrid_search(use_vector=True, use_bm25=True)
        hits = search.search(query, top_k=3, doc_type="conversation")
        for h in hits:
            content = h.get("content", "")
            date = h.get("metadata", {}).get("date", "")
            if content:
                vector_results.append(f"[{date}]\n{content[:300]}")
    except Exception:
        pass

    markdown_results = []
    try:
        hits = store.search_conversations(query)
        for h in hits[:5]:
            date = h.get("created_at", "")[:10]
            context = h.get("context", "")
            if context:
                markdown_results.append(f"[{date}]\n{context[:300]}")
    except Exception:
        pass

    seen = set()
    all_results = []
    for r in vector_results + markdown_results:
        key = r[:80]
        if key not in seen:
            seen.add(key)
            all_results.append(r)

    if not all_results:
        return f"未找到包含 '{query}' 的 Huaqi 对话记录。"

    return "找到以下与 Huaqi 的历史对话：\n\n" + "\n---\n".join(all_results[:5])

from huaqi_src.layers.capabilities.learning.learning_tools import (
    get_learning_progress_tool,
    get_course_outline_tool,
    start_lesson_tool,
    mark_lesson_complete_tool,
)

for _t in (get_learning_progress_tool, get_course_outline_tool, start_lesson_tool, mark_lesson_complete_tool):
    _TOOL_REGISTRY.append(_t)


@register_tool
@tool
def write_file_tool(file_path: str, content: str) -> str:
    """将内容写入指定文件路径。当需要保存报告、笔记或任务结果到文件时使用。支持绝对路径和 ~ 展开。"""
    from pathlib import Path
    try:
        path = Path(file_path).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f"已写入文件: {path}"
    except Exception as e:
        return f"写入失败: {e}"


@register_tool
@tool
def read_file_tool(file_path: str) -> str:
    """读取指定文件路径的内容。当需要查看本地文件、报告或笔记时使用。支持绝对路径和 ~ 展开。"""
    from pathlib import Path
    try:
        path = Path(file_path).expanduser()
        if not path.exists():
            return f"文件不存在: {path}"
        content = path.read_text(encoding="utf-8")
        if len(content) > 10000:
            return content[:10000] + f"\n\n[内容已截断，共 {len(content)} 字符]"
        return content
    except Exception as e:
        return f"读取失败: {e}"


def _sync_scheduler_after_tool(store) -> str:
    try:
        from huaqi_src.scheduler.manager import get_scheduler_manager
        from huaqi_src.scheduler.jobs import register_jobs
        scheduler = get_scheduler_manager()
        if scheduler.is_running():
            register_jobs(scheduler, store)
    except Exception:
        pass
    return ""


@register_tool
@tool
def list_scheduled_jobs_tool() -> str:
    """列出所有定时任务及其配置。当用户询问有哪些定时任务时使用。"""
    from huaqi_src.scheduler.scheduled_job_store import ScheduledJobStore
    from huaqi_src.config.paths import get_data_dir
    data_dir = get_data_dir()
    if data_dir is None:
        return "数据目录未设置。"
    store = ScheduledJobStore(data_dir)
    jobs = store.load_jobs()
    if not jobs:
        return "当前没有定时任务。"
    lines = ["当前定时任务列表：\n"]
    for job in jobs:
        status = "启用" if job.enabled else "禁用"
        lines.append(f"- [{status}] {job.display_name}（{job.id}）")
        lines.append(f"  Cron: {job.cron}")
        lines.append(f"  Prompt: {job.prompt[:60]}{'...' if len(job.prompt) > 60 else ''}")
        if job.output_dir:
            lines.append(f"  输出目录: {job.output_dir}")
    return "\n".join(lines)


@register_tool
@tool
def add_scheduled_job_tool(
    job_id: str,
    display_name: str,
    cron: str,
    prompt: str,
    output_dir: str = "",
) -> str:
    """新增一个定时任务。当用户想要创建新的定时任务时使用。
    job_id 为唯一标识（英文字母和下划线），cron 为标准 5 段 cron 表达式，output_dir 可为空。"""
    from huaqi_src.scheduler.scheduled_job_store import ScheduledJobStore, ScheduledJob
    from huaqi_src.config.paths import get_data_dir
    data_dir = get_data_dir()
    if data_dir is None:
        return "数据目录未设置。"
    store = ScheduledJobStore(data_dir)
    try:
        job = ScheduledJob(
            id=job_id,
            display_name=display_name,
            cron=cron,
            enabled=True,
            prompt=prompt,
            output_dir=output_dir or None,
        )
        store.add_job(job)
        _sync_scheduler_after_tool(store)
        return f"已创建定时任务：{display_name}（{job_id}），Cron: {cron}"
    except ValueError as e:
        return str(e)


@register_tool
@tool
def remove_scheduled_job_tool(job_id: str) -> str:
    """删除一个定时任务。当用户想要移除某个定时任务时使用。"""
    from huaqi_src.scheduler.scheduled_job_store import ScheduledJobStore
    from huaqi_src.config.paths import get_data_dir
    data_dir = get_data_dir()
    if data_dir is None:
        return "数据目录未设置。"
    store = ScheduledJobStore(data_dir)
    try:
        store.remove_job(job_id)
        _sync_scheduler_after_tool(store)
        return f"已删除定时任务: {job_id}"
    except ValueError as e:
        return str(e)


@register_tool
@tool
def update_scheduled_job_tool(
    job_id: str,
    display_name: str = "",
    cron: str = "",
    prompt: str = "",
    output_dir: str = "",
    clear_output_dir: bool = False,
) -> str:
    """更新一个定时任务的配置。当用户想修改任务名称、执行时间或 prompt 时使用。只传需要修改的字段。
    若要清除输出目录，设置 clear_output_dir=True。"""
    from huaqi_src.scheduler.scheduled_job_store import ScheduledJobStore
    from huaqi_src.config.paths import get_data_dir
    data_dir = get_data_dir()
    if data_dir is None:
        return "数据目录未设置。"
    store = ScheduledJobStore(data_dir)
    job = store.get_job(job_id)
    if job is None:
        return f"任务不存在: {job_id}"
    updates = {}
    if display_name:
        updates["display_name"] = display_name
    if cron:
        updates["cron"] = cron
    if prompt:
        updates["prompt"] = prompt
    if clear_output_dir:
        updates["output_dir"] = None
    elif output_dir:
        updates["output_dir"] = output_dir
    if not updates:
        return "未提供任何需要更新的字段。"
    try:
        updated_job = job.model_copy(update=updates)
        store.update_job(updated_job)
        _sync_scheduler_after_tool(store)
        return f"已更新定时任务: {job_id}"
    except ValueError as e:
        return str(e)


@register_tool
@tool
def enable_scheduled_job_tool(job_id: str) -> str:
    """启用一个定时任务。当用户想要开启某个已禁用的定时任务时使用。"""
    from huaqi_src.scheduler.scheduled_job_store import ScheduledJobStore
    from huaqi_src.config.paths import get_data_dir
    data_dir = get_data_dir()
    if data_dir is None:
        return "数据目录未设置。"
    store = ScheduledJobStore(data_dir)
    job = store.get_job(job_id)
    if job is None:
        return f"任务不存在: {job_id}"
    updated_job = job.model_copy(update={"enabled": True})
    store.update_job(updated_job)
    _sync_scheduler_after_tool(store)
    return f"已启用定时任务: {job_id}"


@register_tool
@tool
def disable_scheduled_job_tool(job_id: str) -> str:
    """禁用一个定时任务。当用户想要暂停某个定时任务时使用。"""
    from huaqi_src.scheduler.scheduled_job_store import ScheduledJobStore
    from huaqi_src.config.paths import get_data_dir
    data_dir = get_data_dir()
    if data_dir is None:
        return "数据目录未设置。"
    store = ScheduledJobStore(data_dir)
    job = store.get_job(job_id)
    if job is None:
        return f"任务不存在: {job_id}"
    updated_job = job.model_copy(update={"enabled": False})
    store.update_job(updated_job)
    _sync_scheduler_after_tool(store)
    return f"已禁用定时任务: {job_id}"


@register_tool
@tool
def google_search_tool(query: str) -> str:
    """在互联网上搜索最新信息、新闻、热点事件。
    当用户询问近期新闻、实时动态、或本地数据库无法回答的时事问题时使用。
    """
    import time

    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS

    last_err = None
    for attempt in range(3):
        try:
            if attempt > 0:
                time.sleep(3 * attempt)
            with DDGS(timeout=20) as ddgs:
                results = list(ddgs.text(query, max_results=5))
            if not results:
                return f"未找到关于 '{query}' 的相关信息"
            lines = []
            for r in results:
                title = r.get("title", "")
                body = r.get("body", "")
                href = r.get("href", "")
                lines.append(f"【{title}】\n{body}\n{href}")
            return "\n\n".join(lines)
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if "ratelimit" in msg or "rate limit" in msg or "202" in msg or "0x304" in msg or "unsupported protocol" in msg:
                continue
            if "timeout" in msg or "timed out" in msg:
                continue
            break

    msg = str(last_err).lower()
    if "timeout" in msg or "timed out" in msg:
        return "网络搜索暂时不可用，请稍后重试"
    if "ratelimit" in msg or "rate limit" in msg or "202" in msg or "0x304" in msg or "unsupported protocol" in msg:
        return "搜索频率过高，请稍后再试"
    return f"搜索失败: {str(last_err)[:80]}"
