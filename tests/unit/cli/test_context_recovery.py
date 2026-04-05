from unittest.mock import MagicMock, patch
import huaqi_src.cli.context as ctx_module


def test_ensure_initialized_triggers_startup_recovery(tmp_path):
    ctx_module._config = None
    ctx_module._personality = None
    ctx_module._hooks = None
    ctx_module._growth = None
    ctx_module._diary = None
    ctx_module._memory_store = None
    ctx_module._git = None
    ctx_module.DATA_DIR = None
    ctx_module.MEMORY_DIR = None

    with patch("huaqi_src.cli.context.require_data_dir", return_value=tmp_path), \
         patch("huaqi_src.cli.context.get_memory_dir", return_value=tmp_path / "memory"), \
         patch("huaqi_src.cli.context.init_config_manager"), \
         patch("huaqi_src.cli.context.PersonalityEngine"), \
         patch("huaqi_src.cli.context.GitAutoCommit"), \
         patch("huaqi_src.cli.context.HookManager"), \
         patch("huaqi_src.cli.context.GrowthTracker"), \
         patch("huaqi_src.cli.context.DiaryStore"), \
         patch("huaqi_src.cli.context.MarkdownMemoryStore"), \
         patch("huaqi_src.cli.context.StartupJobRecovery") as MockRecovery:

        ctx_module.ensure_initialized()

        MockRecovery.assert_called_once()
        MockRecovery.return_value.run.assert_called_once()
