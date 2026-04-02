from langchain_core.tools import tool
from huaqi_src.layers.data.diary import DiaryStore
from huaqi_src.config.paths import (
    get_memory_dir,
    get_work_docs_dir,
    get_cli_chats_dir,
    get_conversations_dir,
)
import datetime
from huaqi_src.layers.data.events.store import LocalDBStorage

@tool
def search_diary_tool(query: str) -> str:
    """搜索用户的历史日记内容。当用户询问过去发生的事情、特定的回忆或关键词（如kaleido）时使用。"""
    store = DiaryStore(get_memory_dir())
    results = store.search(query)
    
    if not results:
        return f"未找到包含 '{query}' 的相关日记。"
        
    formatted_results = [f"日期: {r.date}\n内容: {r.content}" for r in results[:3]]
    return "找到以下日记记录：\n\n" + "\n---\n".join(formatted_results)

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
        return f"未找到关于 '{query}' 的近期世界新闻。"

    return "找到以下相关世界新闻：\n\n" + "\n---\n".join(results[:3])


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



@tool
def search_cli_chats_tool(query: str) -> str:
    """搜索用户与其他 CLI Agent（如 codeflicker、Claude）的对话记录。当用户询问曾经的编程问题、讨论过的技术方案时使用。"""
    try:
        cli_chats_dir = get_cli_chats_dir()
    except RuntimeError:
        return f"未找到包含 '{query}' 的 CLI 对话记录（数据目录未设置）。"

    if not cli_chats_dir.exists():
        return f"未找到包含 '{query}' 的 CLI 对话记录。"

    results = []
    query_lower = query.lower()
    for md_file in sorted(cli_chats_dir.rglob("*.md"), reverse=True)[:30]:
        try:
            content = md_file.read_text(encoding="utf-8")
            if query_lower in content.lower():
                results.append(f"文件: {md_file.parent.name}/{md_file.name}\n摘要: {content[:300]}")
        except Exception:
            continue

    if not results:
        return f"未找到包含 '{query}' 的 CLI 对话记录。"
    return "找到以下 CLI 对话记录：\n\n" + "\n---\n".join(results[:3])


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
