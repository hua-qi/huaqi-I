class ConfigManager:
    def __init__(self):
        self._enabled_modules = set()
        self._load_from_app_config()

    def _load_from_app_config(self):
        try:
            # 尝试通过环境变量获取配置
            import os
            if os.getenv("HUAQI_ENABLE_NETWORK") == "1":
                self._enabled_modules.add("network_proxy")

            # 尝试从持久化配置读取
            from huaqi_src.core.config_paths import get_data_dir
            from huaqi_src.core.config_simple import ConfigManager as SimpleConfigManager
            
            data_dir = get_data_dir()
            if data_dir:
                cfg_manager = SimpleConfigManager(data_dir)
                app_cfg = cfg_manager.load_config()
                if app_cfg and hasattr(app_cfg, 'modules'):
                    for mod, enabled in app_cfg.modules.items():
                        if enabled:
                            self._enabled_modules.add(mod)
        except Exception:
            pass

    def is_enabled(self, module_name: str) -> bool:
        return module_name in self._enabled_modules

    def enable(self, module_name: str) -> None:
        self._enabled_modules.add(module_name)
