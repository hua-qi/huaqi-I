from langchain_core.tools import tool
from huaqi_src.core.diary_simple import DiaryStore
from huaqi_src.core.config_paths import get_memory_dir

@tool
def search_diary_tool(query: str) -> str:
    """搜索用户的历史日记内容。当用户询问过去发生的事情、特定的回忆或关键词（如kaleido）时使用。"""
    store = DiaryStore(get_memory_dir())
    results = store.search(query)
    
    if not results:
        return f"未找到包含 '{query}' 的相关日记。"
        
    formatted_results = [f"日期: {r.date}\n内容: {r.content}" for r in results[:3]]
    return "找到以下日记记录：\n\n" + "\n---\n".join(formatted_results)
