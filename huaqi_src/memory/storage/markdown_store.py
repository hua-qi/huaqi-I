"""Markdown 格式记忆存储

所有记忆以人类可读的 Markdown 格式存储
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import re


class MarkdownMemoryStore:
    """Markdown 记忆存储
    
    存储格式：
    - 会话：按日期组织的 Markdown 文件
    - 元数据：YAML frontmatter
    - 内容：Markdown 正文
    """
    
    def __init__(self, base_dir: Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def save_conversation(
        self,
        session_id: str,
        timestamp: datetime,
        turns: List[Dict[str, Any]],
        metadata: Optional[Dict] = None
    ) -> Path:
        """保存会话为 Markdown 文件
        
        Args:
            session_id: 会话ID
            timestamp: 会话时间
            turns: 对话轮次列表
            metadata: 额外元数据
            
        Returns:
            Path: 保存的文件路径
        """
        # 按日期组织目录
        date_dir = self.base_dir / timestamp.strftime("%Y/%m")
        date_dir.mkdir(parents=True, exist_ok=True)
        
        # 文件名：时间戳_会话ID.md
        filename = f"{timestamp.strftime('%Y%m%d_%H%M%S')}_{session_id}.md"
        filepath = date_dir / filename
        
        # 构建 Markdown 内容
        content = self._build_conversation_markdown(
            session_id=session_id,
            timestamp=timestamp,
            turns=turns,
            metadata=metadata
        )
        
        # 写入文件
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        
        return filepath
    
    def _build_conversation_markdown(
        self,
        session_id: str,
        timestamp: datetime,
        turns: List[Dict[str, Any]],
        metadata: Optional[Dict] = None
    ) -> str:
        """构建会话 Markdown 内容"""
        lines = []
        
        # YAML Frontmatter
        lines.append("---")
        lines.append(f"session_id: {session_id}")
        lines.append(f"created_at: {timestamp.isoformat()}")
        lines.append(f"turns: {len(turns)}")
        
        if metadata:
            for key, value in metadata.items():
                if isinstance(value, (str, int, float, bool)):
                    lines.append(f"{key}: {value}")
        
        lines.append("---")
        lines.append("")
        
        # 标题
        lines.append(f"# 对话记录 - {timestamp.strftime('%Y年%m月%d日 %H:%M')}")
        lines.append("")
        
        # 对话内容
        for i, turn in enumerate(turns, 1):
            user_msg = turn.get("user_message", "")
            assistant_msg = turn.get("assistant_response", "")
            turn_metadata = turn.get("metadata", {})
            
            # 用户消息
            lines.append(f"## 回合 {i}")
            lines.append("")
            lines.append("**👤 用户**")
            lines.append("")
            lines.append(user_msg)
            lines.append("")
            
            # 助手回复
            lines.append("**🤖 Huaqi**")
            lines.append("")
            lines.append(assistant_msg)
            lines.append("")
            
            # 元数据（可选）
            if turn_metadata:
                lines.append("<details>")
                lines.append("<summary>元数据</summary>")
                lines.append("")
                lines.append("```yaml")
                for key, value in turn_metadata.items():
                    lines.append(f"{key}: {value}")
                lines.append("```")
                lines.append("")
                lines.append("</details>")
                lines.append("")
            
            lines.append("---")
            lines.append("")
        
        return "\n".join(lines)
    
    def load_conversation(self, filepath: Path) -> Optional[Dict[str, Any]]:
        """加载 Markdown 会话文件
        
        Args:
            filepath: Markdown 文件路径
            
        Returns:
            Dict: 会话数据
        """
        if not filepath.exists():
            return None
        
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 解析 frontmatter
        frontmatter, body = self._parse_frontmatter(content)
        
        # 解析对话轮次
        turns = self._parse_turns(body)
        
        return {
            "session_id": frontmatter.get("session_id", ""),
            "created_at": frontmatter.get("created_at", ""),
            "turns": turns,
            "metadata": {k: v for k, v in frontmatter.items() 
                        if k not in ["session_id", "created_at", "turns"]},
        }
    
    def _parse_frontmatter(self, content: str) -> tuple[Dict, str]:
        """解析 YAML frontmatter"""
        if not content.startswith("---"):
            return {}, content
        
        parts = content.split("---", 2)
        if len(parts) < 3:
            return {}, content
        
        frontmatter_text = parts[1].strip()
        body = parts[2].strip()
        
        # 简单解析 YAML
        frontmatter = {}
        for line in frontmatter_text.split("\n"):
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                
                # 尝试转换类型
                if value.isdigit():
                    value = int(value)
                elif value.lower() in ("true", "false"):
                    value = value.lower() == "true"
                
                frontmatter[key] = value
        
        return frontmatter, body
    
    def _parse_turns(self, body: str) -> List[Dict[str, Any]]:
        """解析对话轮次"""
        turns = []
        
        # 按 "## 回合" 分割
        sections = re.split(r'\n## 回合 \d+\n', body)
        
        for section in sections[1:]:  # 跳过标题部分
            turn = {"user_message": "", "assistant_response": "", "metadata": {}}
            
            # 分割用户和助手部分
            if "**👤 用户**" in section and "**🤖 Huaqi**" in section:
                parts = section.split("**🤖 Huaqi**")
                
                # 提取用户消息
                user_part = parts[0].split("**👤 用户**")[1].strip()
                turn["user_message"] = self._clean_message(user_part)
                
                # 提取助手回复
                assistant_part = parts[1].split("---")[0].strip()
                turn["assistant_response"] = self._clean_message(assistant_part)
            
            turns.append(turn)
        
        return turns
    
    def _clean_message(self, text: str) -> str:
        """清理消息文本"""
        # 移除 <details> 标签
        text = re.sub(r'<details>.*?</details>', '', text, flags=re.DOTALL)
        # 移除空白行
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(lines)
    
    def list_conversations(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """列出所有会话
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            limit: 最大数量
            
        Returns:
            List: 会话信息列表
        """
        conversations = []
        
        # 遍历所有 Markdown 文件
        for filepath in self.base_dir.rglob("*.md"):
            try:
                # 从文件名解析时间
                stat = filepath.stat()
                file_time = datetime.fromtimestamp(stat.st_mtime)
                
                # 日期过滤
                if start_date and file_time < start_date:
                    continue
                if end_date and file_time > end_date:
                    continue
                
                # 解析 frontmatter
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                frontmatter, _ = self._parse_frontmatter(content)
                
                conversations.append({
                    "filepath": str(filepath.relative_to(self.base_dir)),
                    "session_id": frontmatter.get("session_id", ""),
                    "created_at": frontmatter.get("created_at", ""),
                    "turns": frontmatter.get("turns", 0),
                    "modified": file_time.isoformat(),
                })
                
                if len(conversations) >= limit:
                    break
                    
            except Exception:
                continue
        
        # 按时间倒序
        conversations.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        
        return conversations
    
    def search_conversations(self, query: str) -> List[Dict[str, Any]]:
        """搜索会话内容
        
        Args:
            query: 搜索关键词
            
        Returns:
            List: 匹配的会话列表
        """
        results = []
        query_lower = query.lower()
        
        for filepath in self.base_dir.rglob("*.md"):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                if query_lower in content.lower():
                    frontmatter, _ = self._parse_frontmatter(content)
                    
                    # 提取匹配的片段
                    lines = content.split('\n')
                    context = []
                    for i, line in enumerate(lines):
                        if query_lower in line.lower():
                            # 提取前后 2 行作为上下文
                            start = max(0, i - 2)
                            end = min(len(lines), i + 3)
                            context.extend(lines[start:end])
                            context.append("...")
                    
                    results.append({
                        "filepath": str(filepath.relative_to(self.base_dir)),
                        "session_id": frontmatter.get("session_id", ""),
                        "created_at": frontmatter.get("created_at", ""),
                        "context": '\n'.join(context[:10]),  # 限制上下文长度
                    })
                    
            except Exception:
                continue
        
        return results
    
    def delete_conversation(self, filepath: Path) -> bool:
        """删除会话文件
        
        Args:
            filepath: 文件路径（相对或绝对）
            
        Returns:
            bool: 是否成功
        """
        if not filepath.is_absolute():
            filepath = self.base_dir / filepath
        
        if filepath.exists():
            filepath.unlink()
            return True
        return False
    
    def export_conversation(self, filepath: Path, format: str = "json") -> str:
        """导出会话为其他格式
        
        Args:
            filepath: Markdown 文件路径
            format: 导出格式 (json/html/txt)
            
        Returns:
            str: 导出内容
        """
        conv = self.load_conversation(filepath)
        if not conv:
            return ""
        
        if format == "json":
            return json.dumps(conv, ensure_ascii=False, indent=2)
        
        elif format == "html":
            # 简单 HTML 转换
            html = ["<html><body>"]
            html.append(f"<h1>对话记录</h1>")
            html.append(f"<p>时间: {conv.get('created_at', '')}</p>")
            
            for i, turn in enumerate(conv.get("turns", []), 1):
                html.append(f"<h2>回合 {i}</h2>")
                html.append(f"<p><strong>用户:</strong> {turn.get('user_message', '')}</p>")
                html.append(f"<p><strong>Huaqi:</strong> {turn.get('assistant_response', '')}</p>")
            
            html.append("</body></html>")
            return "\n".join(html)
        
        elif format == "txt":
            # 纯文本格式
            lines = [f"对话记录 - {conv.get('created_at', '')}", "=" * 40, ""]
            
            for i, turn in enumerate(conv.get("turns", []), 1):
                lines.append(f"回合 {i}")
                lines.append("-" * 40)
                lines.append(f"用户: {turn.get('user_message', '')}")
                lines.append("")
                lines.append(f"Huaqi: {turn.get('assistant_response', '')}")
                lines.append("")
            
            return "\n".join(lines)
        
        return ""
