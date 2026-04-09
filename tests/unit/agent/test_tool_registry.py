def test_tool_registry_is_not_empty():
    from huaqi_src.agent.tools import _TOOL_REGISTRY
    assert len(_TOOL_REGISTRY) > 0

def test_tool_registry_contains_google_search():
    from huaqi_src.agent.tools import _TOOL_REGISTRY
    names = [t.name for t in _TOOL_REGISTRY]
    assert "google_search_tool" in names

def test_tool_registry_contains_all_existing_tools():
    from huaqi_src.agent.tools import _TOOL_REGISTRY
    names = [t.name for t in _TOOL_REGISTRY]
    expected = [
        "search_diary_tool",
        "search_work_docs_tool",
        "search_events_tool",
        "search_worldnews_tool",
        "search_person_tool",
        "search_cli_chats_tool",
        "get_relationship_map_tool",
        "search_huaqi_chats_tool",
        "get_learning_progress_tool",
        "get_course_outline_tool",
        "start_lesson_tool",
        "mark_lesson_complete_tool",
        "write_file_tool",
        "read_file_tool",
        "list_scheduled_jobs_tool",
        "add_scheduled_job_tool",
        "remove_scheduled_job_tool",
        "update_scheduled_job_tool",
        "enable_scheduled_job_tool",
        "disable_scheduled_job_tool",
    ]
    for name in expected:
        assert name in names, f"{name} not in registry"
