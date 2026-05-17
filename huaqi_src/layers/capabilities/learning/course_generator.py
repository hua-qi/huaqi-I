import re
from typing import Any, List, Optional


_LEARNING_FALLBACKS = {
    "outline": (
        "你是一位专业的技术讲师。请为「{skill}」生成一个由浅入深的学习大纲，包含 6-10 个章节。\n"
        "\n"
        "要求：\n"
        "- 每行只输出一个章节标题，不加编号前缀（如\"第1章：\"）\n"
        "- 从最基础的概念开始，逐步深入\n"
        "- 每个章节标题简洁（不超过 20 字）\n"
        "\n"
        "直接输出章节列表，每行一个标题："
    ),
    "lesson": (
        "你是一位专业的技术讲师，正在讲解「{skill}」课程的「{chapter}」章节。\n"
        "\n"
        "请用清晰、简洁的语言讲解本章核心概念，包含：\n"
        "1. 核心概念解释\n"
        "2. 关键原理（可包含示例代码，如果是编程语言）\n"
        "3. 一句话总结\n"
        "\n"
        "要求：中文回答，总字数不超过 300 字。"
    ),
    "quiz": (
        "你是一位专业的技术讲师，刚讲完「{skill}」的「{chapter}」章节。\n"
        "\n"
        "请出一道考题来检验学习效果：\n"
        "- 如果是编程语言，优先出代码理解题（给出代码，问输出/报错原因）\n"
        "- 否则出简答题\n"
        "- 题目简洁，学员应在 2 分钟内能回答\n"
        "\n"
        "直接输出题目，不要解释："
    ),
    "feedback": (
        "你是一位专业技术讲师，正在批改关于「{skill}」「{chapter}」章节的作业。\n"
        "\n"
        "题目：{quiz}\n"
        "学员回答：{answer}\n"
        "\n"
        "请给出简短评价（100-150 字）：\n"
        "- 先肯定正确的部分\n"
        "- 指出错误或补充遗漏的重点\n"
        "- 鼓励继续学习\n"
        "\n"
        "用温暖、鼓励的语气："
    ),
}


def _load_learning_prompt(prompt_type: str, **kwargs) -> str:
    try:
        from huaqi_src.prompts.loader import get_prompt_loader
        loader = get_prompt_loader()
        scene_id = f"layers.capabilities.learning.{prompt_type}"
        system, user = loader.load(scene_id, **kwargs)
        return user or system or ""
    except Exception:
        return _LEARNING_FALLBACKS.get(prompt_type, "").format(**kwargs)


class CourseGenerator:
    def __init__(self, llm: Optional[Any] = None):
        self._llm = llm

    def _get_llm(self):
        if self._llm is not None:
            return self._llm
        from huaqi_src.cli.context import build_llm_manager, ensure_initialized
        from langchain_openai import ChatOpenAI

        ensure_initialized()
        llm_mgr = build_llm_manager(temperature=0.7, max_tokens=600)
        if llm_mgr is None:
            raise RuntimeError("未配置任何 LLM 提供商")
        if not llm_mgr._active_provider:
            raise RuntimeError("未配置任何 LLM 提供商")
        cfg = llm_mgr._active_provider.config
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.api_base or None,
            temperature=0.7,
            max_tokens=600,
        )

    def generate_outline(self, skill: str) -> List[str]:
        llm = self._get_llm()
        prompt = _load_learning_prompt("outline", skill=skill)
        response = llm.invoke(prompt)
        raw = response.content.strip()
        lines = [l.strip() for l in raw.splitlines() if l.strip()]
        cleaned = []
        for line in lines:
            line = re.sub(r"^[\d]+[.。、\)）]\s*", "", line)
            line = re.sub(r"^第\d+章[：:]\s*", "", line)
            if line:
                cleaned.append(line)
        return cleaned

    def generate_lesson(self, skill: str, chapter: str) -> str:
        llm = self._get_llm()
        prompt = _load_learning_prompt("lesson", skill=skill, chapter=chapter)
        response = llm.invoke(prompt)
        return response.content.strip()

    def generate_quiz(self, skill: str, chapter: str) -> str:
        llm = self._get_llm()
        prompt = _load_learning_prompt("quiz", skill=skill, chapter=chapter)
        response = llm.invoke(prompt)
        return response.content.strip()

    def generate_feedback(self, skill: str, chapter: str, quiz: str, answer: str, passed: bool = None) -> str:
        llm = self._get_llm()
        prompt = _load_learning_prompt("feedback", skill=skill, chapter=chapter, quiz=quiz, answer=answer)
        response = llm.invoke(prompt)
        text = response.content.strip()
        if passed is True:
            return text + "\n\n[PASS]"
        if passed is False:
            return text + "\n\n[FAIL]"
        return text

    _PROJECT_KEYWORDS = ("实战", "项目", "project", "实操", "部署", "安装", "环境配置", "搭建")
    _CODING_KEYWORDS = ("练习", "coding", "代码", "编写", "实现", "写一个", "刷题")

    def _infer_lesson_type(self, title: str) -> str:
        title_lower = title.lower()
        for kw in self._PROJECT_KEYWORDS:
            if kw in title_lower:
                return "project"
        for kw in self._CODING_KEYWORDS:
            if kw in title_lower:
                return "coding"
        return "quiz"

    def generate_outline_with_types(self, skill: str) -> List[tuple]:
        titles = self.generate_outline(skill)
        return [(title, self._infer_lesson_type(title)) for title in titles]
