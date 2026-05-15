"""世界新闻内容增强器

使用 LLM 将英文新闻翻译为中文并扩展摘要内容。
"""

import re
from pathlib import Path


_ENRICH_PROMPT = """你是一位专业的新闻编辑。请处理以下世界新闻内容：

{raw_content}

要求：
1. 将所有英文标题和内容翻译为流畅的中文
2. 每篇新闻扩展为 2-3 段详细内容，补充关键背景信息
3. 原本就是中文的内容保留但同样扩展细节
4. 保留原文中的链接和来源标注
5. 整体格式保持不变（# 标题、## 来源、--- 分隔线）
6. 不要添加原文中不存在的信息或编造事实
7. 只输出处理后的 Markdown 内容，不要加任何额外说明"""


class WorldNewsEnricher:
    """使用 LLM 翻译和扩展世界新闻内容。"""

    def __init__(self, llm_manager):
        self._llm = llm_manager

    def enrich_file(self, file_path: Path) -> bool:
        """读取世界新闻文件，翻译并扩展内容，原地覆写。"""
        raw_content = file_path.read_text(encoding="utf-8")
        if not raw_content.strip():
            return False

        prompt = _ENRICH_PROMPT.format(raw_content=raw_content)

        try:
            response = self._llm.quick_chat(
                prompt,
                system="你是一位专业新闻编辑，擅长翻译和撰写中文新闻摘要。",
            )
        except Exception as e:
            print(f"[WorldNewsEnricher] LLM 调用失败: {e}")
            return False

        enriched = _extract_markdown(response)
        if not enriched:
            print("[WorldNewsEnricher] LLM 返回内容为空")
            return False

        file_path.write_text(enriched, encoding="utf-8")
        return True


def _extract_markdown(text: str) -> str:
    """从 LLM 回复中提取 Markdown 内容（去掉可能的代码块包裹和前言）。"""
    # 尝试提取 ```markdown 代码块
    md_match = re.search(r"```(?:markdown|md)?\s*\n(.*?)\n```", text, re.DOTALL)
    if md_match:
        return md_match.group(1).strip()

    # 尝试找到 # 标题开头
    heading_idx = text.find("\n# ")
    if heading_idx == -1:
        heading_idx = text.find("# ")
    if heading_idx > 0:
        return text[heading_idx:].strip()

    # 去掉可能的前导/尾随空白
    return text.strip()
