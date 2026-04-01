import pytest
from unittest.mock import MagicMock, patch


def _make_mock_llm(return_text: str):
    mock_msg = MagicMock()
    mock_msg.content = return_text
    mock_llm = MagicMock()
    mock_llm.invoke.return_value = mock_msg
    return mock_llm


def test_generate_outline_returns_lessons(tmp_path):
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm(
        "第1章：所有权（Ownership）\n第2章：借用（Borrowing）\n第3章：生命周期（Lifetimes）"
    )
    gen = CourseGenerator(llm=mock_llm)
    lessons = gen.generate_outline("Rust")

    assert len(lessons) >= 2
    assert any("所有权" in t for t in lessons)


def test_generate_outline_handles_numbered_list(tmp_path):
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm(
        "1. 基础语法\n2. 函数与闭包\n3. 错误处理\n4. 并发编程"
    )
    gen = CourseGenerator(llm=mock_llm)
    lessons = gen.generate_outline("Go")
    assert len(lessons) == 4
    assert lessons[0] == "基础语法"


def test_generate_lesson_returns_str(tmp_path):
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("所有权是 Rust 内存管理的核心...")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_lesson("Rust", "所有权")
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_quiz_returns_str(tmp_path):
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("以下哪段代码会报编译错误？\nA. let x = 5;\nB. let x = &5;")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_quiz("Rust", "所有权")
    assert isinstance(result, str)


def test_generate_feedback_returns_str(tmp_path):
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("回答正确！Rust 的所有权规则确保...")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_feedback("Rust", "所有权", "以下代码...", "选项 A")
    assert isinstance(result, str)


def test_generate_outline_with_types_returns_tuples():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm(
        "Python 环境安装\n变量与数据类型\n列表推导式练习\n文件读写实战项目"
    )
    gen = CourseGenerator(llm=mock_llm)
    results = gen.generate_outline_with_types("Python")

    assert len(results) == 4
    for title, lesson_type in results:
        assert isinstance(title, str)
        assert lesson_type in ("quiz", "coding", "project")


def test_generate_outline_with_types_detects_project():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("实战项目：构建 Web 服务")
    gen = CourseGenerator(llm=mock_llm)
    results = gen.generate_outline_with_types("Go")

    assert results[0][1] == "project"


def test_generate_outline_with_types_detects_coding():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("代码练习：字符串处理")
    gen = CourseGenerator(llm=mock_llm)
    results = gen.generate_outline_with_types("Python")

    assert results[0][1] == "coding"


def test_generate_feedback_appends_pass_marker():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("回答正确！Rust 的所有权规则确保了内存安全。")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_feedback("Rust", "所有权", "以下代码...", "选项 A", passed=True)
    assert result.endswith("[PASS]")


def test_generate_feedback_appends_fail_marker():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("回答有误，注意借用规则...")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_feedback("Rust", "所有权", "以下代码...", "选项 B", passed=False)
    assert result.endswith("[FAIL]")


def test_generate_feedback_default_no_marker():
    from huaqi_src.learning.course_generator import CourseGenerator

    mock_llm = _make_mock_llm("回答正确！")
    gen = CourseGenerator(llm=mock_llm)
    result = gen.generate_feedback("Rust", "所有权", "以下代码...", "选项 A")
    assert isinstance(result, str)
