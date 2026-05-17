"""huaqi_src.prompts — 提示词管理模块。

从数据目录 prompts/ 加载场景提示词，支持热更新和模板变量注入。
"""

from huaqi_src.prompts.loader import PromptLoader, get_prompt_loader

__all__ = ["PromptLoader", "get_prompt_loader"]
