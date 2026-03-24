"""用户隔离的存储管理

确保每个用户的数据完全隔离
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
import shutil

from huaqi.core.config import ConfigManager


class UserContext:
    """用户上下文
    
    用于在操作期间临时切换用户
    """
    
    def __init__(self, config_manager: ConfigManager, user_id: str):
        self.config_manager = config_manager
        self.user_id = user_id
        self.previous_user_id: Optional[str] = None
    
    def __enter__(self):
        self.previous_user_id = self.config_manager.current_user_id
        if self.previous_user_id != self.user_id:
            self.config_manager.switch_user(self.user_id)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.previous_user_id and self.previous_user_id != self.user_id:
            self.config_manager.switch_user(self.previous_user_id)
        return False


class UserIsolatedStorage:
    """用户隔离存储基类
    
    所有涉及用户数据的存储类都应继承此类
    """
    
    def __init__(self, config_manager: ConfigManager, user_id: Optional[str] = None):
        self.config_manager = config_manager
        self._user_id = user_id or config_manager.current_user_id
        
        if self._user_id is None:
            raise ValueError("未指定用户ID，请先登录")
    
    @property
    def user_id(self) -> str:
        return self._user_id
    
    @property
    def user_data_dir(self) -> Path:
        """获取当前用户的数据目录"""
        return self.config_manager.get_user_data_dir(self._user_id)
    
    @property
    def user_memory_dir(self) -> Path:
        """获取当前用户的记忆目录"""
        return self.config_manager.get_user_memory_dir(self._user_id)
    
    @property
    def user_vector_dir(self) -> Path:
        """获取当前用户的向量目录"""
        return self.config_manager.get_user_vector_dir(self._user_id)
    
    def ensure_user_dirs(self):
        """确保用户目录存在"""
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self.user_memory_dir.mkdir(parents=True, exist_ok=True)
        self.user_vector_dir.mkdir(parents=True, exist_ok=True)
    
    def switch_user(self, user_id: str):
        """切换到其他用户"""
        self._user_id = user_id
        self.config_manager.switch_user(user_id)
        self.ensure_user_dirs()
    
    def with_user(self, user_id: str) -> UserContext:
        """创建临时用户上下文"""
        return UserContext(self.config_manager, user_id)
    
    def get_user_stats(self) -> Dict[str, Any]:
        """获取用户存储统计"""
        stats = {
            "user_id": self._user_id,
            "data_dir": str(self.user_data_dir),
            "total_size_bytes": 0,
            "file_count": 0,
            "memory_files": 0,
            "vector_files": 0,
        }
        
        if self.user_data_dir.exists():
            for path in self.user_data_dir.rglob("*"):
                if path.is_file():
                    stats["file_count"] += 1
                    stats["total_size_bytes"] += path.stat().st_size
                    
                    if "memory" in str(path):
                        stats["memory_files"] += 1
                    elif "vectors" in str(path):
                        stats["vector_files"] += 1
        
        # 转换为人类可读的大小
        stats["total_size_human"] = self._format_bytes(stats["total_size_bytes"])
        
        return stats
    
    def _format_bytes(self, size: int) -> str:
        """格式化字节大小"""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.2f} {unit}"
            size /= 1024
        return f"{size:.2f} TB"
    
    def export_user_data(self, output_path: Path) -> Path:
        """导出用户数据
        
        Args:
            output_path: 输出文件路径
            
        Returns:
            Path: 导出的文件路径
        """
        import tarfile
        
        # 确保输出目录存在
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 创建 tar.gz 压缩包
        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(self.user_data_dir, arcname=self._user_id)
        
        return output_path
    
    def import_user_data(self, import_path: Path, merge: bool = False):
        """导入用户数据
        
        Args:
            import_path: 导入文件路径
            merge: 是否合并（False 则覆盖）
        """
        import tarfile
        
        if not merge and self.user_data_dir.exists():
            # 备份现有数据
            backup_path = self.user_data_dir.parent / f"{self._user_id}_backup_{self._timestamp()}"
            shutil.move(self.user_data_dir, backup_path)
        
        # 解压数据
        with tarfile.open(import_path, "r:gz") as tar:
            tar.extractall(self.user_data_dir.parent)
    
    def _timestamp(self) -> str:
        """生成时间戳"""
        from datetime import datetime
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def clear_user_data(self, confirm: bool = False):
        """清空用户数据（危险操作！）
        
        Args:
            confirm: 必须设置为 True 才会执行
        """
        if not confirm:
            raise ValueError("清空数据需要 confirm=True")
        
        if self.user_data_dir.exists():
            shutil.rmtree(self.user_data_dir)
            self.ensure_user_dirs()


class UserMemoryManager(UserIsolatedStorage):
    """用户记忆管理器
    
    管理特定用户的所有记忆相关操作
    """
    
    def __init__(self, config_manager: ConfigManager, user_id: Optional[str] = None):
        super().__init__(config_manager, user_id)
        self.ensure_user_dirs()
    
    def get_memory_path(self, memory_type: str, filename: str) -> Path:
        """获取记忆文件路径
        
        Args:
            memory_type: identity / project / skill / insight / note
            filename: 文件名
            
        Returns:
            Path: 完整路径
        """
        type_dir = self.user_memory_dir / memory_type
        type_dir.mkdir(parents=True, exist_ok=True)
        return type_dir / filename
    
    def list_memories(self, memory_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出用户的所有记忆"""
        memories = []
        
        search_dir = self.user_memory_dir
        if memory_type:
            search_dir = search_dir / memory_type
        
        if not search_dir.exists():
            return memories
        
        for path in search_dir.rglob("*.md"):
            rel_path = path.relative_to(self.user_memory_dir)
            memories.append({
                "path": str(rel_path),
                "type": rel_path.parts[0] if rel_path.parts else "unknown",
                "filename": path.name,
                "size": path.stat().st_size,
                "modified": path.stat().st_mtime,
            })
        
        return memories
    
    def delete_memory(self, memory_path: str) -> bool:
        """删除记忆"""
        full_path = self.user_memory_dir / memory_path
        
        if full_path.exists() and full_path.is_file():
            full_path.unlink()
            return True
        return False
    
    def search_memories(self, query: str) -> List[Dict[str, Any]]:
        """搜索用户记忆（基础实现，实际应使用向量搜索）"""
        # TODO: 集成向量搜索
        results = []
        memories = self.list_memories()
        
        query_lower = query.lower()
        for memory in memories:
            if query_lower in memory["path"].lower():
                results.append(memory)
        
        return results


class UserSkillManager(UserIsolatedStorage):
    """用户技能管理器
    
    管理特定用户的技能配置和数据
    """
    
    def __init__(self, config_manager: ConfigManager, user_id: Optional[str] = None):
        super().__init__(config_manager, user_id)
        self.skills_dir = self.user_data_dir / "skills"
        self.skills_dir.mkdir(parents=True, exist_ok=True)
    
    def get_skill_config(self, skill_name: str) -> Dict[str, Any]:
        """获取技能配置"""
        config_path = self.skills_dir / f"{skill_name}.yaml"
        
        if config_path.exists():
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        return {}
    
    def save_skill_config(self, skill_name: str, config: Dict[str, Any]):
        """保存技能配置"""
        import yaml
        
        config_path = self.skills_dir / f"{skill_name}.yaml"
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True)
    
    def list_skills(self) -> List[str]:
        """列出用户已配置的技能"""
        skills = []
        for config_file in self.skills_dir.glob("*.yaml"):
            skills.append(config_file.stem)
        return skills
    
    def enable_skill(self, skill_name: str):
        """启用技能"""
        config = self.get_skill_config(skill_name)
        config["enabled"] = True
        self.save_skill_config(skill_name, config)
    
    def disable_skill(self, skill_name: str):
        """禁用技能"""
        config = self.get_skill_config(skill_name)
        config["enabled"] = False
        self.save_skill_config(skill_name, config)
    
    def is_skill_enabled(self, skill_name: str) -> bool:
        """检查技能是否启用"""
        config = self.get_skill_config(skill_name)
        return config.get("enabled", True)
