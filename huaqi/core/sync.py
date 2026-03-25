"""Git 同步系统

支持记忆数据的 Git 同步
"""

from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import subprocess
import json

from rich.console import Console

console = Console()


@dataclass
class SyncStatus:
    """同步状态"""
    ahead: int  # 本地超前提交数
    behind: int  # 本地落后提交数
    modified: List[str]  # 修改的文件
    untracked: List[str]  # 未跟踪的文件
    has_remote: bool  # 是否有远程仓库
    last_sync: Optional[str]  # 上次同步时间


class GitSyncManager:
    """Git 同步管理器"""
    
    def __init__(self, repo_dir: Path, remote_url: Optional[str] = None):
        self.repo_dir = Path(repo_dir)
        self.remote_url = remote_url
        self.git_dir = self.repo_dir / ".git"
    
    def init_repo(self) -> bool:
        """初始化 Git 仓库"""
        try:
            if self.git_dir.exists():
                console.print("[dim]Git 仓库已存在[/dim]")
                return True
            
            self._run_git_command(["init"])
            console.print("[green]✓ Git 仓库初始化成功[/green]")
            
            # 配置 .gitignore
            self._setup_gitignore()
            
            # 初始提交
            self._run_git_command(["add", "."])
            self._run_git_command([
                "commit", "-m", 
                "Initial commit\n\n- Initialize Huaqi memory repository\n- Add .gitignore"
            ])
            
            return True
            
        except Exception as e:
            console.print(f"[red]Git 初始化失败: {e}[/red]")
            return False
    
    def _setup_gitignore(self):
        """设置 .gitignore"""
        gitignore_path = self.repo_dir / ".gitignore"
        
        gitignore_content = """# Huaqi Git Sync

# Vector database (large binary files)
vectors/
*.db
*.sqlite
*.sqlite3

# Temporary files
*.tmp
*.temp
*.log

# System files
.DS_Store
Thumbs.db

# Optional: ignore large media files
# *.mp4
# *.mp3
# *.wav
"""
        
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write(gitignore_content)
        
        console.print("[dim]✓ 已配置 .gitignore[/dim]")
    
    def add_remote(self, url: str, name: str = "origin") -> bool:
        """添加远程仓库"""
        try:
            # 检查是否已有远程仓库
            result = self._run_git_command(
                ["remote", "get-url", name],
                check=False,
                capture_output=True
            )
            
            if result.returncode == 0:
                # 更新现有远程
                self._run_git_command(["remote", "set-url", name, url])
            else:
                # 添加新远程
                self._run_git_command(["remote", "add", name, url])
            
            self.remote_url = url
            console.print(f"[green]✓ 远程仓库已配置: {name} -> {url}[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]添加远程仓库失败: {e}[/red]")
            return False
    
    def get_status(self) -> SyncStatus:
        """获取同步状态"""
        try:
            # 检查是否有远程
            has_remote = False
            try:
                result = self._run_git_command(
                    ["remote", "-v"],
                    capture_output=True
                )
                has_remote = bool(result.stdout.strip())
            except:
                pass
            
            # 获取修改的文件
            result = self._run_git_command(
                ["status", "--porcelain"],
                capture_output=True
            )
            
            modified = []
            untracked = []
            
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                status = line[:2]
                filename = line[3:]
                
                if status.startswith("?"):
                    untracked.append(filename)
                else:
                    modified.append(filename)
            
            # 获取 ahead/behind
            ahead, behind = 0, 0
            if has_remote:
                try:
                    # 先 fetch
                    self._run_git_command(["fetch", "origin"], check=False)
                    
                    result = self._run_git_command(
                        ["rev-list", "--left-right", "--count", "HEAD...origin/main"],
                        capture_output=True
                    )
                    
                    if result.stdout:
                        ahead_behind = result.stdout.strip().split()
                        if len(ahead_behind) == 2:
                            ahead, behind = int(ahead_behind[0]), int(ahead_behind[1])
                except:
                    pass
            
            # 获取上次同步时间
            last_sync = None
            try:
                result = self._run_git_command(
                    ["log", "-1", "--format=%cd", "--date=iso"],
                    capture_output=True
                )
                if result.stdout:
                    last_sync = result.stdout.strip()
            except:
                pass
            
            return SyncStatus(
                ahead=ahead,
                behind=behind,
                modified=modified,
                untracked=untracked,
                has_remote=has_remote,
                last_sync=last_sync
            )
            
        except Exception as e:
            console.print(f"[red]获取状态失败: {e}[/red]")
            return SyncStatus(0, 0, [], [], False, None)
    
    def commit_changes(self, message: Optional[str] = None) -> bool:
        """提交本地更改"""
        try:
            # 检查是否有更改
            result = self._run_git_command(
                ["status", "--porcelain"],
                capture_output=True
            )
            
            if not result.stdout.strip():
                console.print("[dim]没有需要提交的更改[/dim]")
                return True
            
            # 添加所有更改
            self._run_git_command(["add", "-A"])
            
            # 生成提交信息
            if message is None:
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
                message = f"Auto sync - {timestamp}\n\n- Update memories\n- Sync changes"
            
            # 提交
            self._run_git_command(["commit", "-m", message])
            
            console.print("[green]✓ 本地更改已提交[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]提交失败: {e}[/red]")
            return False
    
    def push(self, force: bool = False) -> bool:
        """推送到远程"""
        try:
            # 先提交本地更改
            self.commit_changes()
            
            # 推送
            cmd = ["push", "origin", "main"]
            if force:
                cmd.append("--force")
            
            self._run_git_command(cmd)
            
            console.print("[green]✓ 已成功推送到远程[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]推送失败: {e}[/red]")
            console.print("[dim]提示: 如果远程有更新，请先执行 pull[/dim]")
            return False
    
    def pull(self, rebase: bool = True) -> bool:
        """从远程拉取"""
        try:
            cmd = ["pull", "origin", "main"]
            if rebase:
                cmd.append("--rebase")
            
            self._run_git_command(cmd)
            
            console.print("[green]✓ 已成功从远程拉取[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]拉取失败: {e}[/red]")
            console.print("[dim]提示: 如果存在冲突，需要手动解决[/dim]")
            return False
    
    def sync(self) -> bool:
        """完整同步（pull + push）"""
        try:
            # 先拉取
            if not self.pull():
                return False
            
            # 再推送
            return self.push()
            
        except Exception as e:
            console.print(f"[red]同步失败: {e}[/red]")
            return False
    
    def log(self, n: int = 10) -> List[Dict[str, str]]:
        """获取提交历史"""
        try:
            result = self._run_git_command(
                ["log", f"-{n}", "--pretty=format:%H|%ci|%s"],
                capture_output=True
            )
            
            commits = []
            for line in result.stdout.strip().split("\n"):
                if "|" in line:
                    parts = line.split("|", 2)
                    commits.append({
                        "hash": parts[0][:8],
                        "date": parts[1],
                        "message": parts[2] if len(parts) > 2 else "",
                    })
            
            return commits
            
        except Exception as e:
            console.print(f"[red]获取历史失败: {e}[/red]")
            return []
    
    def _run_git_command(
        self,
        args: List[str],
        check: bool = True,
        capture_output: bool = False
    ) -> subprocess.CompletedProcess:
        """运行 Git 命令"""
        cmd = ["git", "-C", str(self.repo_dir)] + args
        
        result = subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=True
        )
        
        return result


class UserGitSync:
    """用户隔离的 Git 同步"""
    
    def __init__(self, data_dir: Path, user_id: str):
        self.user_id = user_id
        self.user_data_dir = data_dir / "users_data" / user_id
        self.sync_manager = GitSyncManager(self.user_data_dir)
        
        # 配置文件路径
        self.config_file = self.user_data_dir / ".sync_config.json"
    
    def setup(self, remote_url: Optional[str] = None) -> bool:
        """设置同步"""
        # 初始化仓库
        if not self.sync_manager.init_repo():
            return False
        
        # 配置远程
        if remote_url:
            self.sync_manager.add_remote(remote_url)
            self._save_config({"remote_url": remote_url})
        else:
            # 尝试从配置加载
            config = self._load_config()
            if config.get("remote_url"):
                self.sync_manager.add_remote(config["remote_url"])
        
        return True
    
    def status(self) -> SyncStatus:
        """获取同步状态"""
        return self.sync_manager.get_status()
    
    def push(self) -> bool:
        """推送"""
        return self.sync_manager.push()
    
    def pull(self) -> bool:
        """拉取"""
        return self.sync_manager.pull()
    
    def sync(self) -> bool:
        """同步"""
        return self.sync_manager.sync()
    
    def auto_sync_enabled(self) -> bool:
        """检查是否启用自动同步"""
        config = self._load_config()
        return config.get("auto_sync", False)
    
    def enable_auto_sync(self, interval_minutes: int = 60):
        """启用自动同步"""
        config = self._load_config()
        config["auto_sync"] = True
        config["sync_interval_minutes"] = interval_minutes
        self._save_config(config)
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置"""
        if self.config_file.exists():
            with open(self.config_file, "r") as f:
                return json.load(f)
        return {}
    
    def _save_config(self, config: Dict[str, Any]):
        """保存配置"""
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)
