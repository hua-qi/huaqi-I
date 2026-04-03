from unittest.mock import patch
from huaqi_src.cli.chat import _handle_report_command

@patch('huaqi_src.cli.chat.console.print')
@patch('huaqi_src.layers.capabilities.reports.manager.ReportManager')
def test_handle_report_morning(mock_manager_class, mock_print):
    mock_manager = mock_manager_class.return_value
    mock_manager.get_or_generate_report.return_value = "Mock Morning Content"
    
    _handle_report_command(["/report", "morning", "today"])
    
    mock_manager.get_or_generate_report.assert_called_with("morning", "today")
    mock_print.assert_any_call("\nMock Morning Content\n")
