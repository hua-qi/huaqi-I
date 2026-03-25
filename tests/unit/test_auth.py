"""用户认证单元测试"""

import pytest
from pathlib import Path
from huaqi.core.auth import UserManager, UserProfile, UserSession


class TestUserManager:
    """测试用户管理器"""
    
    def test_create_user(self, temp_dir):
        """测试创建用户"""
        user_manager = UserManager(temp_dir)
        
        user = user_manager.create_user(
            email="test@example.com",
            username="testuser",
            provider="local",
            provider_id="test123"
        )
        
        assert isinstance(user, UserProfile)
        assert user.email == "test@example.com"
        assert user.username == "testuser"
        assert user.user_id is not None
        
        # 验证用户目录已创建
        user_dir = user_manager.get_user_dir(user.user_id)
        assert user_dir.exists()
    
    def test_get_user(self, temp_dir):
        """测试获取用户"""
        user_manager = UserManager(temp_dir)
        
        # 创建用户
        user = user_manager.create_user(
            email="test@example.com",
            username="testuser",
            provider="local",
            provider_id="test123"
        )
        
        # 获取用户
        retrieved_user = user_manager.get_user(user.user_id)
        assert retrieved_user is not None
        assert retrieved_user.email == user.email
    
    def test_get_nonexistent_user(self, temp_dir):
        """测试获取不存在的用户"""
        user_manager = UserManager(temp_dir)
        
        user = user_manager.get_user("nonexistent_id")
        assert user is None
    
    def test_create_duplicate_user(self, temp_dir):
        """测试创建重复用户"""
        user_manager = UserManager(temp_dir)
        
        # 创建第一个用户
        user_manager.create_user(
            email="test@example.com",
            username="testuser",
            provider="local",
            provider_id="test123"
        )
        
        # 尝试创建相同 provider_id 的用户
        with pytest.raises(ValueError):
            user_manager.create_user(
                email="test2@example.com",
                username="testuser2",
                provider="local",
                provider_id="test123"
            )
    
    def test_create_session(self, temp_dir):
        """测试创建会话"""
        user_manager = UserManager(temp_dir)
        
        # 创建用户
        user = user_manager.create_user(
            email="test@example.com",
            username="testuser",
            provider="local",
            provider_id="test123"
        )
        
        # 创建会话
        session = user_manager.create_session(user.user_id)
        
        assert isinstance(session, UserSession)
        assert session.user_id == user.user_id
        assert session.token is not None
        assert not session.is_expired
    
    def test_validate_session(self, temp_dir):
        """测试验证会话"""
        user_manager = UserManager(temp_dir)
        
        # 创建用户
        user = user_manager.create_user(
            email="test@example.com",
            username="testuser",
            provider="local",
            provider_id="test123"
        )
        
        # 创建会话
        session = user_manager.create_session(user.user_id)
        
        # 验证会话
        user_id = user_manager.validate_session(session.token)
        assert user_id == user.user_id
    
    def test_validate_invalid_session(self, temp_dir):
        """测试验证无效会话"""
        user_manager = UserManager(temp_dir)
        
        user_id = user_manager.validate_session("invalid_token")
        assert user_id is None
    
    def test_list_users(self, temp_dir):
        """测试列出所有用户"""
        user_manager = UserManager(temp_dir)
        
        # 创建多个用户
        user_manager.create_user(
            email="test1@example.com",
            username="user1",
            provider="local",
            provider_id="id1"
        )
        user_manager.create_user(
            email="test2@example.com",
            username="user2",
            provider="local",
            provider_id="id2"
        )
        
        # 列出用户
        users = user_manager.list_users()
        assert len(users) == 2


class TestUserSession:
    """测试用户会话"""
    
    def test_create_session(self):
        """测试创建会话"""
        session = UserSession.create("user_123")
        
        assert session.user_id == "user_123"
        assert session.session_id is not None
        assert session.token is not None
        assert not session.is_expired
    
    def test_session_expiration(self):
        """测试会话过期"""
        # 创建一个即将过期的会话（负持续时间）
        import datetime
        session = UserSession(
            session_id="test",
            user_id="user_123",
            created_at=datetime.datetime.now(),
            expires_at=datetime.datetime.now() - datetime.timedelta(hours=1),
            token="test_token"
        )
        
        assert session.is_expired
