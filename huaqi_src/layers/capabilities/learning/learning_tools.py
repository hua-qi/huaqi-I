from langchain_core.tools import tool

from .course_generator import CourseGenerator
from .progress_store import LearningProgressStore, slugify


def _get_store() -> LearningProgressStore:
    from huaqi_src.config.paths import get_learning_dir

    return LearningProgressStore(get_learning_dir())


@tool
def get_learning_progress_tool(skill: str) -> str:
    """查询某技术的学习进度。当用户询问「我学 XX 到哪了」「XX 学了多少」等学习进度时使用。"""
    try:
        store = _get_store()
    except RuntimeError as e:
        return f"无法获取学习进度：{e}"

    slug = slugify(skill)
    course = store.load_course(slug)
    if course is None:
        return f"尚未开始学习「{skill}」。可以说「开始学 {skill}」来生成课程大纲。"

    completed = sum(1 for l in course.lessons if l.status == "completed")
    lines = [
        f"📚 {course.skill_name} 学习进度",
        f"",
        f"当前章节：第 {course.current_lesson} 章（共 {course.total_lessons} 章）",
        f"已完成：{completed}/{course.total_lessons} 章",
        f"",
        f"章节列表：",
    ]
    for lesson in course.lessons:
        icon = {"completed": "✅", "in_progress": "▶️", "pending": "⬜"}.get(lesson.status, "⬜")
        lines.append(f"{icon} 第{lesson.index}章：{lesson.title}")

    return "\n".join(lines)


@tool
def get_course_outline_tool(skill: str) -> str:
    """获取某技术的课程大纲。当用户询问「XX 课程有哪些章节」「给我看 XX 学习计划」时使用。"""
    try:
        store = _get_store()
    except RuntimeError as e:
        return f"无法获取课程大纲：{e}"

    slug = slugify(skill)
    course = store.load_course(slug)
    if course is None:
        return f"未找到「{skill}」的课程大纲。可以说「开始学 {skill}」来自动生成。"

    lines = [f"📖 {course.skill_name} 课程大纲（共 {course.total_lessons} 章）", ""]
    for lesson in course.lessons:
        icon = {"completed": "✅", "in_progress": "▶️", "pending": "⬜"}.get(lesson.status, "⬜")
        lines.append(f"{icon} 第{lesson.index}章：{lesson.title}")

    return "\n".join(lines)


@tool
def start_lesson_tool(skill: str) -> str:
    """开始或继续学习某技术当前章节，返回讲解内容和考题。
    当用户说「继续学 XX」「开始今天的学习」「出道题考我」「学 XX」时使用。
    """
    try:
        store = _get_store()
    except RuntimeError as e:
        return f"无法启动学习：{e}"

    from .models import CourseOutline, LessonOutline

    slug = slugify(skill)
    course = store.load_course(slug)

    gen = CourseGenerator()

    if course is None:
        outline_with_types = gen.generate_outline_with_types(skill)
        if not outline_with_types:
            return f"生成「{skill}」课程大纲失败，请稍后重试。"
        lessons = [
            LessonOutline(index=i + 1, title=title, lesson_type=ltype)
            for i, (title, ltype) in enumerate(outline_with_types)
        ]
        course = CourseOutline(skill_name=skill, slug=slug, lessons=lessons)
        store.save_course(course)

    current = next(
        (l for l in course.lessons if l.index == course.current_lesson),
        course.lessons[0] if course.lessons else None,
    )
    if current is None:
        return f"「{skill}」课程已全部完成！🎉"

    if all(l.status == "completed" for l in course.lessons):
        return f"🎉 恭喜！「{skill}」课程已全部完成！共 {course.total_lessons} 章。"

    lesson_content = gen.generate_lesson(skill, current.title)
    quiz = gen.generate_quiz(skill, current.title)

    lines = [
        f"## 📚 {skill} · 第{current.index}章：{current.title}",
        "",
        lesson_content,
        "",
        "---",
        "",
        f"### 🧠 练习题",
        "",
        quiz,
        "",
        f"*（回答后我会给你反馈，说「完成本章」可标记此章完成）*",
    ]

    return "\n".join(lines)


@tool
def mark_lesson_complete_tool(skill: str) -> str:
    """标记当前章节为已完成，并自动推进到下一章。
    当满足以下任一条件时调用：
    1. 用户回答练习题且反馈包含 [PASS]
    2. 用户明确说「完成本章」「下一章」「继续」「我会了」等
    """
    try:
        store = _get_store()
    except RuntimeError as e:
        return f"无法标记完成：{e}"

    slug = slugify(skill)
    course = store.load_course(slug)
    if course is None:
        return f"未找到「{skill}」的课程。可以说「开始学 {skill}」先生成课程大纲。"

    current_index = course.current_lesson
    current = next((l for l in course.lessons if l.index == current_index), None)
    if current is None:
        return f"🎉 「{skill}」课程已全部完成！共 {course.total_lessons} 章。"

    store.mark_lesson_complete(slug, current_index)
    course = store.load_course(slug)

    next_lesson = next(
        (l for l in course.lessons if l.status in ("pending", "in_progress")),
        None,
    )

    if next_lesson is None:
        return (
            f"🎉 恭喜！「{skill}」课程已全部完成！共 {course.total_lessons} 章。\n"
            f"你已掌握了「{skill}」的全部内容！"
        )

    lines = [
        f"✅ 第{current_index}章《{current.title}》已完成！",
        f"",
        f"下一章：第{next_lesson.index}章《{next_lesson.title}》",
        f"说「继续学」开始下一章",
    ]
    return "\n".join(lines)
