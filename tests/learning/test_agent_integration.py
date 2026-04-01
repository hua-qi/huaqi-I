def test_learning_tools_importable():
    from huaqi_src.learning.learning_tools import (
        get_learning_progress_tool,
        get_course_outline_tool,
        start_lesson_tool,
    )
    for t in [get_learning_progress_tool, get_course_outline_tool, start_lesson_tool]:
        assert hasattr(t, "invoke")
        assert hasattr(t, "name")


def test_tools_registered_in_chat_graph():
    from huaqi_src.agent.graph.chat import build_chat_graph
    from huaqi_src.learning.learning_tools import (
        get_learning_progress_tool,
        get_course_outline_tool,
        start_lesson_tool,
    )
    graph = build_chat_graph()
    tool_names = {n for n in graph.nodes}
    assert "tools" in tool_names


def test_learning_tool_names_in_chat_tools():
    from huaqi_src.agent import tools as t
    assert hasattr(t, "get_learning_progress_tool")
    assert hasattr(t, "get_course_outline_tool")
    assert hasattr(t, "start_lesson_tool")


def test_mark_lesson_complete_tool_registered():
    from huaqi_src.agent.tools import mark_lesson_complete_tool
    assert hasattr(mark_lesson_complete_tool, "invoke")
    assert mark_lesson_complete_tool.name == "mark_lesson_complete_tool"


def test_mark_lesson_complete_tool_in_chat_graph():
    from huaqi_src.agent.graph.chat import build_chat_graph
    graph = build_chat_graph()
    tool_names = list(graph.nodes["tools"].runnable.tools_by_name.keys())
    assert "mark_lesson_complete_tool" in tool_names
