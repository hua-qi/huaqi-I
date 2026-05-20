"""世界新闻内容增强器

按 RSS 源分组处理：每个源独立调用 LLM，
选出 2 篇最相关 + 1 篇最不相关，生成中文摘要。
"""

import re
import sys
from pathlib import Path


# ═══ 按源处理 prompt ═══

_SOURCE_PROMPT = """你是一位专业新闻编辑和私人助理。以下是来自 **{source_name}** 的 {article_count} 篇文章。

{user_context}

## 文章列表

{article_list}

## 任务

从以上 {article_count} 篇文章中选出：
- **2 篇与用户最相关的**（用户应该重点关注）
- **1 篇与用户最不相关的**（拓宽视野，了解用户关注圈外的事情）

对每篇文章写中文摘要（2-3 段，200-400 字）。
英文源必须翻译为中文（可保留英文原标题供参考）。

严格按以下格式输出（标题级别必须用 H3，即 ###），不要加任何额外说明：

### 最相关：{{{{中文标题}}}}
**原文链接**：{{url}}
**为什么选这篇**：{{一句话，结合用户画像说明为什么这篇值得关注}}
{{中文摘要}}

### 最相关：{{{{中文标题}}}}
...

### 视野拓展：{{{{中文标题}}}}
**原文链接**：{{url}}
**为什么也值得了解**：{{一句话，说明这篇虽然与用户关注领域不同但仍值得了解}}
{{中文摘要}}"""


def _load_source_prompt(source_name: str, articles: list[str], user_section: str) -> str:
    """构造单个源的 prompt。"""
    article_count = len(articles)
    article_list_parts = []
    for i, article in enumerate(articles, 1):
        article_list_parts.append(f"### 文章 {i}\n{article}")
    article_list = "\n\n".join(article_list_parts)

    try:
        from huaqi_src.prompts.loader import get_prompt_loader
        loader = get_prompt_loader()
        system, user = loader.load(
            "layers.capabilities.world_news_enricher_source",
            source_name=source_name, article_count=str(article_count),
            article_list=article_list, user_context=user_section,
        )
        result = (system or "") + ("\n" + user if user else "")
        return result or _SOURCE_PROMPT.format(
            source_name=source_name, article_count=article_count,
            article_list=article_list, user_context=user_section,
        )
    except Exception:
        return _SOURCE_PROMPT.format(
            source_name=source_name, article_count=article_count,
            article_list=article_list, user_context=user_section,
        )


# ═══ 聚合 prompt（仅生成领域概览 + 综合推荐） ═══

_AGGREGATE_PROMPT = """你是一位专业新闻编辑。以下是今日从各新闻源精选的文章摘要。

{all_sources_content}

{user_context}

## 任务

请严格按以下格式输出，标题必须用 H2（##）：

## 领域概览
简述今日各领域新闻的整体态势（AI/科技、宏观经济与政策、行业动态各一两句）。

## 综合推荐
结合用户画像，从今日所有文章中选出**最值得用户关注的 3 篇**，格式：
1. **文章标题**（源名称）：一句话推荐理由
2. **文章标题**（源名称）：一句话推荐理由
3. **文章标题**（源名称）：一句话推荐理由

只输出以上两段，不要加 H1 标题或额外说明。"""


def _load_aggregate_prompt(all_sources: str, user_section: str) -> str:
    """构造最终聚合 prompt。"""
    prompt_text = _AGGREGATE_PROMPT.replace("{all_sources_content}", all_sources)
    prompt_text = prompt_text.replace("{user_context}", user_section)
    return prompt_text


# ═══ 辅助函数 ═══

def _build_user_context_section(telos_snapshot: str | None) -> str:
    """将 TELOS snapshot 转为 prompt 可用的简短用户画像段落。"""
    if not telos_snapshot or not telos_snapshot.strip():
        return ""
    lines = []
    for line in telos_snapshot.split("\n"):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("---") or stripped.startswith("dimension:") or \
           stripped.startswith("layer:") or stripped.startswith("confidence:") or \
           stripped.startswith("update_count:") or stripped.startswith("is_active:"):
            continue
        lines.append(stripped)
    summary = " ".join(lines)
    if len(summary) > 1500:
        summary = summary[:1500].rsplit("。", 1)[0] + "。"
    return summary


def _parse_sources(raw_content: str) -> dict[str, list[str]]:
    """按源分组文章，返回 {source_name: [article_md]}。

    原始文件格式：
        # 世界感知摘要 YYYY-MM-DD
        ## 36氪
        # article title
        content...
        **链接**：url
        ---
        ## BBC科技
        ...
    """
    sources: dict[str, list[str]] = {}
    parts = raw_content.split("\n## ")
    for part in parts[1:]:  # 跳过 H1 标题
        try:
            source_name, body = part.split("\n", 1)
        except ValueError:
            continue
        source_name = source_name.strip()
        articles = [a.strip() for a in body.split("\n---\n") if a.strip()]
        if source_name not in sources:
            sources[source_name] = []
        sources[source_name].extend(articles)
    return sources


def _extract_markdown(text: str) -> str:
    """从 LLM 回复中提取 Markdown 内容。"""
    md_match = re.search(r"```(?:markdown|md)?\s*\n(.*?)\n```", text, re.DOTALL)
    if md_match:
        return md_match.group(1).strip()
    heading_idx = text.find("\n# ")
    if heading_idx == -1:
        heading_idx = text.find("# ")
    if heading_idx > 0:
        return text[heading_idx:].strip()
    return text.strip()


# ═══ 主类 ═══

class WorldNewsEnricher:
    """使用 LLM 翻译和扩展世界新闻内容。

    按 RSS 源逐个处理：每个源的 3 篇文章一次 LLM 调用，
    选出 2 篇最相关 + 1 篇最不相关并生成中文摘要。
    """

    def __init__(self, llm_manager):
        self._llm = llm_manager

    def enrich_file(self, file_path: Path, user_context: str | None = None) -> bool:
        """读取世界新闻文件，按源处理，原地覆写。"""
        raw_content = file_path.read_text(encoding="utf-8")
        if not raw_content.strip():
            return False

        user_section = _build_user_context_section(user_context)

        sources = _parse_sources(raw_content)
        if not sources:
            print("[WorldNewsEnricher] 未解析到任何新闻源", file=sys.stderr)
            return False

        enriched_parts: list[str] = []
        for source_name in sorted(sources.keys()):
            articles = sources[source_name]
            result = self._enrich_one_source(source_name, articles, user_section)
            if result:
                enriched_parts.append(result)
            else:
                print(
                    f"[WorldNewsEnricher] 源 '{source_name}' 增强失败，跳过",
                    file=sys.stderr,
                )

        if not enriched_parts:
            print("[WorldNewsEnricher] 所有源增强均失败", file=sys.stderr)
            return False

        all_sources_text = "\n\n".join(enriched_parts)

        # 聚合 LLM：仅生成领域概览 + 综合推荐
        aggregate_prompt = _load_aggregate_prompt(all_sources_text, user_section)
        overview = ""
        try:
            response = self._llm.quick_chat(
                aggregate_prompt,
                system="你是一位专业新闻编辑，擅长整理和撰写中文新闻摘要。",
            )
            overview = _extract_markdown(response)
        except Exception as e:
            print(
                f"[WorldNewsEnricher] 聚合 LLM 调用失败: {e}",
                file=sys.stderr,
            )

        # 代码拼装最终文件（避免 LLM 重组导致标题重复或内容丢失）
        date_str = file_path.stem
        final = f"# 世界感知摘要 {date_str}\n\n"
        if overview:
            final += overview + "\n\n"
        final += all_sources_text + "\n"

        file_path.write_text(final, encoding="utf-8")
        return True

    def _enrich_one_source(
        self, source_name: str, articles: list[str], user_section: str,
    ) -> str | None:
        """对单个源调用 LLM，返回该源的摘要 Markdown。"""
        prompt = _load_source_prompt(source_name, articles, user_section)
        try:
            response = self._llm.quick_chat(
                prompt,
                system="你是一位专业新闻编辑，擅长翻译和撰写中文新闻摘要。",
            )
        except Exception as e:
            print(
                f"[WorldNewsEnricher] 源 '{source_name}' LLM 调用失败: {e}",
                file=sys.stderr,
            )
            return None

        result = _extract_markdown(response)
        if not result:
            print(
                f"[WorldNewsEnricher] 源 '{source_name}' 返回内容为空"
                f"（原始长度: {len(response)} 字符）",
                file=sys.stderr,
            )
            return None

        return f"## {source_name}\n\n{result}"
