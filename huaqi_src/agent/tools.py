from langchain_core.tools import tool
from huaqi_src.core.diary_simple import DiaryStore
from huaqi_src.core.config_paths import get_memory_dir
import datetime
from huaqi_src.core.db_storage import LocalDBStorage

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
def search_events_tool(query: str) -> str:
    """搜索用户的微信和CLI命令行等历史交互记录。当用户询问系统交互记录、自己说过什么、微信记录或者系统事件时使用。"""
    db = LocalDBStorage()
    results = db.search_events(query, limit=5)
    
    if not results:
        return f"未找到包含 '{query}' 的相关交互记录。"
        
    formatted_results = []
    for r in results:
        dt = datetime.datetime.fromtimestamp(r.timestamp).strftime('%Y-%m-%d %H:%M:%S')
        formatted_results.append(f"时间: {dt}\n来源: {r.source}\n用户: {r.actor}\n内容: {r.content}")
        
    return "找到以下历史交互记录：\n\n" + "\n---\n".join(formatted_results)
