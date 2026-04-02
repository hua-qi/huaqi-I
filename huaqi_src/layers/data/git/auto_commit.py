"""Git 自动提交和推送模块

每次数据变更时自动触发 git 提交和推送
支持自定义远程仓库地址
"""

import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, List
from dataclasses import dataclass
import yaml


@dataclass
class GitRemoteConfig:
    """Git 远程仓库配置"""
    name: str = "origin"
    url: str = ""
    branch: str = "main"
    auto_push: bool = True


@dataclass
class CommitResult:
    """提交结果"""
    committed: bool = False
    pushed: bool = False
    has_remote: bool = False
    error: str = ""


class GitAutoCommit:
    """Git 自动提交和推送管理器
    
    自动跟踪数据目录变更、提交并推送到远程
    """
    
    def __init__(self, repo_dir: Path, config_path: Optional[Path] = None):
        self.repo_dir = repo_dir
        self.config_path = config_path or (repo_dir / ".huaqi-git.yaml")
        self._git_available = self._check_git()
        self._repo_initialized = False
        self._remote_config: Optional[GitRemoteConfig] = None
        
        if self._git_available:
            self._repo_initialized = self._check_repo()
            self._load_config()
    
    def _check_git(self) -> bool:
        """检查 git 是否可用"""
        try:
            subprocess.run(
                ["git", "--version"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def _check_repo(self) -> bool:
        """检查是否是 git 仓库"""
        git_dir = self.repo_dir / ".git"
        return git_dir.exists()
    
    def _load_config(self):
        """加载 git 配置"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f) or {}
                    if "remote" in data:
                        self._remote_config = GitRemoteConfig(**data["remote"])
            except Exception:
                pass
    
    def _save_config(self):
        """保存 git 配置"""
        if self._remote_config:
            data = {"remote": self._remote_config.__dict__}
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, allow_unicode=True)
    
    def init_repo(self) -> bool:
        """初始化 git 仓库"""
        if not self._git_available:
            print("[Git] Git 不可用")
            return False

        if self._repo_initialized:
            return True

        self._migrate_memory_subrepo()

        try:
            subprocess.run(
                ["git", "init"],
                cwd=self.repo_dir,
                capture_output=True,
                check=True
            )

            self._ensure_git_config()

            gitignore = self.repo_dir / ".gitignore"
            if not gitignore.exists():
                gitignore.write_text("""# Huaqi Git Ignore
*.tmp
*.log
.DS_Store
Thumbs.db
.idea/
.vscode/
*.swp
*.swo
*~
vector_db/
models/
""")
            else:
                content = gitignore.read_text(encoding="utf-8")
                additions = []
                for entry in ("vector_db/", "models/"):
                    if entry not in content:
                        additions.append(entry)
                if additions:
                    gitignore.write_text(content.rstrip() + "\n" + "\n".join(additions) + "\n", encoding="utf-8")

            self._repo_initialized = True
            return True

        except subprocess.CalledProcessError as e:
            print(f"[Git] 初始化失败: {e}")
            return False

    def _migrate_memory_subrepo(self):
        """检测并迁移 memory/ 子仓库"""
        import shutil
        memory_git = self.repo_dir / "memory" / ".git"
        if memory_git.exists():
            shutil.rmtree(memory_git)
            print("[Git] 已迁移旧 memory/.git，统一由数据目录管理")
    
    def _ensure_git_config(self):
        """确保 git 用户配置存在"""
        try:
            # 检查 user.name
            result = subprocess.run(
                ["git", "config", "user.name"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True
            )
            if not result.stdout.strip():
                subprocess.run(
                    ["git", "config", "user.name", "Huaqi User"],
                    cwd=self.repo_dir,
                    capture_output=True,
                    check=True
                )
            
            # 检查 user.email
            result = subprocess.run(
                ["git", "config", "user.email"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True
            )
            if not result.stdout.strip():
                subprocess.run(
                    ["git", "config", "user.email", "huaqi@example.com"],
                    cwd=self.repo_dir,
                    capture_output=True,
                    check=True
                )
        except subprocess.CalledProcessError:
            pass
    
    def set_remote(self, url: str, name: str = "origin", branch: str = "main", auto_push: bool = True):
        """设置远程仓库
        
        Args:
            url: 远程仓库 URL (如 https://github.com/username/repo.git)
            name: 远程名称，默认 origin
            branch: 分支名，默认 main
            auto_push: 是否自动推送
        """
        if not self._git_available:
            print("[Git] Git 不可用")
            return False
        
        if not self._repo_initialized:
            if not self.init_repo():
                return False
        
        try:
            # 检查是否已存在该远程
            result = subprocess.run(
                ["git", "remote", "get-url", name],
                cwd=self.repo_dir,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                # 远程已存在，更新 URL
                subprocess.run(
                    ["git", "remote", "set-url", name, url],
                    cwd=self.repo_dir,
                    capture_output=True,
                    check=True
                )
                print(f"[Git] 已更新远程仓库 {name}: {url}")
            else:
                # 添加新远程
                subprocess.run(
                    ["git", "remote", "add", name, url],
                    cwd=self.repo_dir,
                    capture_output=True,
                    check=True
                )
                print(f"[Git] 已添加远程仓库 {name}: {url}")
            
            # 保存配置
            self._remote_config = GitRemoteConfig(
                name=name,
                url=url,
                branch=branch,
                auto_push=auto_push
            )
            self._save_config()
            
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"[Git] 设置远程仓库失败: {e}")
            return False
    
    def get_remote_url(self) -> Optional[str]:
        """获取远程仓库 URL"""
        if self._remote_config:
            return self._remote_config.url
        
        if not self._repo_initialized:
            return None
        
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except subprocess.CalledProcessError:
            pass
        
        return None
    
    def commit(self, message: Optional[str] = None, files: Optional[List[str]] = None) -> CommitResult:
        """执行 git 提交"""
        if not self._git_available:
            return CommitResult()

        if not self._repo_initialized:
            if not self.init_repo():
                return CommitResult()

        try:
            self._ensure_git_config()

            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )

            if not status_result.stdout.strip():
                return CommitResult()

            if files:
                for file in files:
                    subprocess.run(
                        ["git", "add", file],
                        cwd=self.repo_dir,
                        capture_output=True,
                        check=True
                    )
            else:
                subprocess.run(
                    ["git", "add", "."],
                    cwd=self.repo_dir,
                    capture_output=True,
                    check=True
                )

            if message is None:
                message = f"Auto commit at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_dir,
                capture_output=True,
                check=True
            )

            if self._remote_config and self._remote_config.auto_push:
                return self.push()

            has_remote = bool(self.get_remote_url())
            return CommitResult(committed=True, pushed=False, has_remote=has_remote)

        except subprocess.CalledProcessError as e:
            return CommitResult(error=str(e))
    
    def push(self, remote: Optional[str] = None, branch: Optional[str] = None) -> CommitResult:
        """推送到远程"""
        if not self._git_available or not self._repo_initialized:
            return CommitResult(committed=True, pushed=False, has_remote=False)

        remote = remote or (self._remote_config.name if self._remote_config else "origin")
        branch = branch or (self._remote_config.branch if self._remote_config else "main")

        result = subprocess.run(
            ["git", "remote", "get-url", remote],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            return CommitResult(committed=True, pushed=False, has_remote=False)

        try:
            subprocess.run(
                ["git", "pull", "--rebase", remote, branch],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
            )
            push_result = subprocess.run(
                ["git", "push", "-u", remote, branch],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            return CommitResult(committed=True, pushed=True, has_remote=True)
        except subprocess.CalledProcessError as e:
            stderr = e.stderr.strip() if e.stderr else str(e)
            return CommitResult(committed=True, pushed=False, has_remote=True, error=f"repo={self.repo_dir} | {stderr}")
    
    def pull(self, remote: Optional[str] = None, branch: Optional[str] = None) -> bool:
        """从远程拉取"""
        if not self._git_available or not self._repo_initialized:
            return False
        
        remote = remote or (self._remote_config.name if self._remote_config else "origin")
        branch = branch or (self._remote_config.branch if self._remote_config else "main")
        
        try:
            subprocess.run(
                ["git", "pull", remote, branch],
                cwd=self.repo_dir,
                capture_output=True,
                check=True
            )
            print(f"[Git] 📥 已从 {remote}/{branch} 拉取")
            return True
            
        except subprocess.CalledProcessError as e:
            print(f"[Git] 拉取失败: {e}")
            return False
    
    # ===== 快捷提交方法 =====
    
    def commit_personality_change(self, change_type: str = "update") -> CommitResult:
        """提交个性变更"""
        return self.commit(
            message=f"[Personality] {change_type}",
            files=["personality.yaml"]
        )

    def commit_hook_change(self, hook_name: str, action: str = "update") -> CommitResult:
        """提交 Hook 变更"""
        return self.commit(
            message=f"[Hook] {action}: {hook_name}",
            files=["hooks.yaml"]
        )

    def commit_skill_change(self, skill_name: str, action: str = "update") -> CommitResult:
        """提交技能变更"""
        return self.commit(
            message=f"[Skill] {action}: {skill_name}",
            files=["growth.yaml"]
        )

    def commit_goal_change(self, goal_title: str, action: str = "update") -> CommitResult:
        """提交目标变更"""
        return self.commit(
            message=f"[Goal] {action}: {goal_title}",
            files=["growth.yaml"]
        )

    def commit_config_change(self) -> CommitResult:
        """提交配置变更"""
        return self.commit(
            message=f"[Config] update",
            files=["config.yaml"]
        )
    
    def commit_memory_change(self, memory_type: str = "general") -> CommitResult:
        """提交记忆变更"""
        return self.commit(
            message=f"[Memory] {memory_type} at {datetime.now().strftime('%H:%M')}"
        )
    
    def get_status(self) -> dict:
        """获取 git 状态"""
        if not self._git_available:
            return {"available": False, "initialized": False}
        
        if not self._repo_initialized:
            return {"available": True, "initialized": False}
        
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            
            return {
                "available": True,
                "initialized": True,
                "modified": len([l for l in lines if l.startswith(" M") or l.startswith("M ")]),
                "added": len([l for l in lines if l.startswith("A ")]),
                "untracked": len([l for l in lines if l.startswith("??")]),
                "has_changes": len(lines) > 0,
                "remote_url": self.get_remote_url(),
                "auto_push": self._remote_config.auto_push if self._remote_config else False
            }
        except subprocess.CalledProcessError:
            return {"available": True, "initialized": False, "error": True}


# 全局 git 提交管理器
_git_committer: Optional[GitAutoCommit] = None


def get_git_committer(memory_dir: Path) -> GitAutoCommit:
    """获取或创建 git 提交管理器"""
    global _git_committer
    if _git_committer is None or _git_committer.repo_dir != memory_dir:
        _git_committer = GitAutoCommit(memory_dir)
    return _git_committer
