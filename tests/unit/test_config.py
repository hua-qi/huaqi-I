"""配置管理单元测试"""

import pytest
from pathlib import Path
from huaqi.core.config import ConfigManager, UserConfig, LLMProviderConfig


class TestConfigManager:
    """测试配置管理器"""
    
    def test_init_config_manager(self, temp_dir, mock_user_id):
        """测试初始化配置管理器"""
        config_manager = ConfigManager(temp_dir, mock_user_id)
        
        assert config_manager.current_user_id == mock_user_id
        assert config_manager.user_data_dir.exists()
    
    def test_load_and_save_config(self, temp_dir, mock_user_id):
        """测试加载和保存配置"""
        config_manager = ConfigManager(temp_dir, mock_user_id)
        
        # 加载默认配置
        config = config_manager.load_config()
        assert isinstance(config, UserConfig)
        assert config.user_id == mock_user_id
        
        # 修改配置
        config.llm_default_provider = "test_provider"
        config_manager.save_config(config)
        
        # 重新加载
        reloaded_config = config_manager.load_config()
        assert reloaded_config.llm_default_provider == "test_provider"
    
    def test_get_and_set_config(self, temp_dir, mock_user_id):
        """测试获取和设置配置项"""
        config_manager = ConfigManager(temp_dir, mock_user_id)
        
        # 设置配置
        config_manager.set("llm_default_provider", "openai")
        config_manager.set("memory.max_session_memory", 200)
        
        # 获取配置
        assert config_manager.get("llm_default_provider") == "openai"
        assert config_manager.get("memory.max_session_memory") == 200
        
        # 获取不存在的配置
        assert config_manager.get("nonexistent.key", "default") == "default"
    
    def test_add_llm_provider(self, temp_dir, mock_user_id):
        """测试添加 LLM 提供商"""
        config_manager = ConfigManager(temp_dir, mock_user_id)
        
        provider = LLMProviderConfig(
            name="test_provider",
            model="test-model",
            api_key="test-key"
        )
        
        config_manager.add_llm_provider(provider)
        
        # 验证
        providers = config_manager.list_llm_providers()
        assert "test_provider" in providers
    
    def test_get_user_data_dir(self, temp_dir, mock_user_id):
        """测试获取用户数据目录"""
        config_manager = ConfigManager(temp_dir, mock_user_id)
        
        user_dir = config_manager.get_user_data_dir()
        assert user_dir.exists()
        assert mock_user_id in str(user_dir)
    
    def test_switch_user(self, temp_dir, mock_user_id):
        """测试切换用户"""
        config_manager = ConfigManager(temp_dir, mock_user_id)
        
        # 切换到新用户
        new_user = "new_user_67890"
        config_manager.switch_user(new_user)
        
        assert config_manager.current_user_id == new_user
        assert config_manager.get_user_data_dir().exists()
