from huaqi_src.cli.notifier import CLINotifier


def test_cli_notifier_send_message_outputs_text(capsys):
    notifier = CLINotifier(user_id="u1")
    notifier.send_message("你的 beliefs 维度刚刚更新了", user_id="u1")
    captured = capsys.readouterr()
    assert "beliefs" in captured.out


def test_cli_notifier_display_progress(capsys):
    notifier = CLINotifier(user_id="u1")
    notifier.display_progress("正在处理信号...")
    captured = capsys.readouterr()
    assert "处理" in captured.out
