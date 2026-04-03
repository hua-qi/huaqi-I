import pytest
from unittest.mock import patch, MagicMock
from huaqi_src.layers.capabilities.reports.manager import ReportManager

def test_get_or_generate_report_not_found(tmp_path):
    manager = ReportManager(data_dir=tmp_path)
    result = manager.get_or_generate_report("morning", date_str="2000-01-01")
    assert "无法生成历史日期的报告" in result

@patch('huaqi_src.layers.capabilities.reports.manager.MorningBriefAgent')
def test_get_or_generate_report_today(mock_agent_class, tmp_path):
    mock_agent = MagicMock()
    mock_agent_class.return_value = mock_agent
    
    manager = ReportManager(data_dir=tmp_path)
    manager.get_or_generate_report("morning", date_str="today")
    mock_agent.run.assert_called_once()
