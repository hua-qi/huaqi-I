"""世界新闻内容增强器

使用 LLM 将英文新闻翻译为中文并扩展摘要内容，
结合用户 TELOS 画像生成个性化重点关注建议。
"""

import re
from pathlib import Path


_ENRICH_FALLBACK = """你是一位专业的新闻编辑，也是一位了解用户个人画像的私人助理。你的任务：先从以下三个领域对新闻进行粗筛分类，再根据用户 TELOS 画像从所有分类中选出**最值得该用户关注的 3 篇新闻**，进行深度中文摘要。

{raw_content}

{user_context}

## 工作流程

1. **按三个领域粗筛**：将以下所有新闻分为三类（无法归入三类的忽略）：
   - **AI/科技**：涉及 AI 技术突破、科技公司重大动态、开发者工具变化
   - **宏观经济与政策**：涉及政策变化、市场趋势、国际关系、监管动态
   - **行业动态**：涉及具体行业的重要变化
2. **结合画像评估**：在每个领域内，结合用户画像（如已提供）逐条评估与用户兴趣、职业、目标的相关性
3. **精选 3 篇**：从所有分类中选出与用户最相关的**恰好 3 篇**（可跨领域），宁缺毋滥
4. **深度摘要**：对选中的 3 篇逐一撰写中文摘要，并说明选择理由

## 输出结构

按以下结构输出 Markdown：

# 世界感知摘要 YYYY-MM-DD

## 领域粗筛结果

简述三个领域各筛选出几篇、与本用户关联度如何。

## 今日精选（3 篇）

对选中的 3 篇新闻，每条按以下格式输出：

### 精选 {{序号}}：{{{{中文标题}}}}

**来源**：{{来源名称}}
**领域**：{{AI/科技 | 宏观经济与政策 | 行业动态}}
**链接**：{{原文 URL}}
{{#if 英文源}}**英文原标题**：{{{{原标题}}}}{{/if}}

**为什么选这篇**：{{结合用户画像，一句话说明这篇文章为什么值得该用户关注}}

{{中文摘要，2-3 段，补充关键背景信息}}

---

## 内容要求

1. **精选 3 篇**：只输出 3 篇最相关的新闻，含详细摘要。其余新闻不输出详情
2. **领域覆盖**：粗筛时三个领域都要考虑，但精选的 3 篇可以来自同一领域（用户画像指向该领域时）
3. **选择理由**：每条新闻必须说明「为什么选这篇」，结合用户画像（如已提供），否则说明普适重要性
4. **统一中文输出**：所有内容必须是中文，英文新闻必须翻译（保留英文原标题供参考）
5. **摘要质量**：每条摘要 2-3 段（200-400 字），补充关键背景，不要照搬原文
6. **链接必含**：每条新闻必须包含原文链接
7. **只输出 Markdown**：不要加任何额外说明、前言或结语"""


def _load_enrich_prompt(raw_content: str, user_context: str) -> str:
    try:
        from huaqi_src.prompts.loader import get_prompt_loader
        loader = get_prompt_loader()
        system, user = loader.load(
            "layers.capabilities.world_news_enricher",
            raw_content=raw_content, user_context=user_context,
        )
        result = (system or "") + ("\n" + user if user else "")
        return result or ""
    except Exception:
        return _ENRICH_FALLBACK.format(
            raw_content=raw_content, user_context=user_context
        )


def _build_user_context_section(telos_snapshot: str | None) -> str:
    """将 TELOS snapshot 转为 prompt 可用的简短用户画像段落。"""
    if not telos_snapshot or not telos_snapshot.strip():
        return ""
    # 提取内容行，过滤掉 markdown frontmatter 噪音
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
    # 限制长度，避免 prompt 过长
    if len(summary) > 1500:
        summary = summary[:1500].rsplit("。", 1)[0] + "。"
    return summary


_MAX_RAW_CONTENT_CHARS = 25000


def _truncate_raw_content(raw_content: str, max_chars: int = _MAX_RAW_CONTENT_CHARS) -> str:
    """截断过长原始内容，按文章边界截断避免切断单条新闻。"""
    if len(raw_content) <= max_chars:
        return raw_content
    truncated = raw_content[:max_chars]
    last_sep = truncated.rfind("\n---")
    if last_sep > max_chars // 2:
        return truncated[:last_sep].strip()
    last_nl = truncated.rfind("\n\n")
    if last_nl > max_chars // 2:
        return truncated[:last_nl].strip()
    return truncated


class WorldNewsEnricher:
    """使用 LLM 翻译和扩展世界新闻内容。"""

    def __init__(self, llm_manager):
        self._llm = llm_manager

    def enrich_file(self, file_path: Path, user_context: str | None = None) -> bool:
        """读取世界新闻文件，翻译并扩展内容，原地覆写。

        Args:
            file_path: 世界新闻 markdown 文件路径
            user_context: 可选的用户画像文本（来自 TELOS），用于个性化重点关注建议
        """
        raw_content = file_path.read_text(encoding="utf-8")
        if not raw_content.strip():
            return False

        raw_content = _truncate_raw_content(raw_content)

        user_section = _build_user_context_section(user_context)
        prompt = _load_enrich_prompt(
            raw_content=raw_content, user_context=user_section
        )

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
    md_match = re.search(r"```(?:markdown|md)?\s*\n(.*?)\n```", text, re.DOTALL)
    if md_match:
        return md_match.group(1).strip()

    heading_idx = text.find("\n# ")
    if heading_idx == -1:
        heading_idx = text.find("# ")
    if heading_idx > 0:
        return text[heading_idx:].strip()

    return text.strip()
