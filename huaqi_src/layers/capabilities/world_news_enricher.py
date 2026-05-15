"""世界新闻内容增强器

使用 LLM 将英文新闻翻译为中文并扩展摘要内容，
结合用户 TELOS 画像生成个性化重点关注建议。
"""

import re
from pathlib import Path


_ENRICH_PROMPT = """你是一位专业的新闻编辑。请处理以下世界新闻内容：

{raw_content}

{user_context}

## 输出结构

按以下结构输出 Markdown：

# 世界感知摘要 YYYY-MM-DD

## 重点关注建议

按以下领域分类，列出今日最值得**该用户**关注的新闻及关注理由（每类 1-3 条）：
- **AI/科技**：涉及 AI 技术突破、科技公司重大动态、开发者工具变化
- **宏观经济与政策**：涉及政策变化、市场趋势、国际关系、监管动态
- **行业动态**：涉及具体行业的重要变化

格式示例：
### AI/科技
- **新闻关键词**：关注理由（一句话说明为什么**这个用户**需要关注，而非泛泛的新闻重要性）

**重要**：如果上面提供了用户画像信息，请基于用户的具体背景（职业、兴趣、目标、挑战）来判断哪些新闻值得关注，关注理由必须与用户的具体情况关联。如果没有用户画像，则基于新闻本身的重要性给出通用建议。

---

## 新闻详情

### 来源：{{来源名称}}

#### {{{{英文原标题}}}}
**中文标题**：{{中文翻译标题}}

**链接**：{{原文 URL}}

{{中文摘要，2-3 段，补充关键背景信息}}

---

## 内容要求

1. **中英对照**：每条新闻保留英文原标题（用 #### 标记），紧接着给出中文标题翻译
2. **链接必含**：每条新闻必须包含原文链接（**链接**：URL）
3. **摘要扩展**：每条新闻扩展为 2-3 段中文内容，补充关键背景信息（如相关事件、行业影响、历史背景），但不要编造事实
4. **中文源处理**：原本就是中文的新闻（如 36氪、虎嗅、少数派）保留原文内容并适当扩展细节，不强行翻译
5. **英文源处理**：英文新闻（如 BBC、CNN、路透社）翻译为流畅中文，保留英文原标题
6. **个性化建议**：重点关注建议需基于用户画像（如已提供），关注理由要说明「为什么跟你有关」
7. **只输出 Markdown**：不要加任何额外说明、前言或结语"""


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

        user_section = _build_user_context_section(user_context)
        prompt = _ENRICH_PROMPT.format(
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
