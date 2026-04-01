import pytest
from typer.testing import CliRunner
from unittest.mock import patch
from huaqi_src.cli.commands.people import people_app

runner = CliRunner()


def test_people_list_empty(tmp_path):
    with patch("huaqi_src.cli.commands.people.PeopleGraph") as MockGraph:
        mock_instance = MockGraph.return_value
        mock_instance.list_people.return_value = []
        result = runner.invoke(people_app, ["list"])
    assert result.exit_code == 0
    assert "暂无" in result.output


def test_people_add(tmp_path):
    with patch("huaqi_src.cli.commands.people.PeopleGraph") as MockGraph:
        mock_instance = MockGraph.return_value
        mock_instance.get_person.return_value = None
        result = runner.invoke(people_app, ["add", "张三", "--relation", "同事"])
    assert result.exit_code == 0
    mock_instance.add_person.assert_called_once()


def test_people_show_not_found(tmp_path):
    with patch("huaqi_src.cli.commands.people.PeopleGraph") as MockGraph:
        mock_instance = MockGraph.return_value
        mock_instance.get_person.return_value = None
        result = runner.invoke(people_app, ["show", "不存在的人"])
    assert result.exit_code == 0
    assert "未找到" in result.output


def test_people_note(tmp_path):
    with patch("huaqi_src.cli.commands.people.PeopleGraph") as MockGraph:
        mock_instance = MockGraph.return_value
        mock_instance.update_person.return_value = True
        result = runner.invoke(people_app, ["note", "张三", "喜欢喝咖啡"])
    assert result.exit_code == 0
    mock_instance.update_person.assert_called_once_with("张三", notes="喜欢喝咖啡")
