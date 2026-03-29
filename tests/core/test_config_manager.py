from huaqi_src.core.config_manager import ConfigManager

def test_modules_disabled_by_default():
    config = ConfigManager()
    assert config.is_enabled("wechat") is False
    assert config.is_enabled("network_proxy") is False

def test_enable_module():
    config = ConfigManager()
    config.enable("wechat")
    assert config.is_enabled("wechat") is True
