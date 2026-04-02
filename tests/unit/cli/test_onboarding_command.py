from pathlib import Path
from huaqi_src.cli.commands.onboarding import is_first_run


def test_is_first_run_true_when_no_telos(tmp_path):
    assert is_first_run(telos_dir=tmp_path / "telos") is True


def test_is_first_run_false_when_telos_exists(tmp_path):
    telos_dir = tmp_path / "telos"
    telos_dir.mkdir()
    (telos_dir / "beliefs.md").touch()
    assert is_first_run(telos_dir=telos_dir) is False
