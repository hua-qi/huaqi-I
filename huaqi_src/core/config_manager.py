class ConfigManager:
    def __init__(self):
        self._enabled_modules = set()

    def is_enabled(self, module_name: str) -> bool:
        return module_name in self._enabled_modules

    def enable(self, module_name: str) -> None:
        self._enabled_modules.add(module_name)
