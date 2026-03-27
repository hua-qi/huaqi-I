"""小红书发布器

支持两种模式:
1. 真实发布: 通过小红书 API 或模拟浏览器发布 (需登录)
2. 草稿模式: 生成内容到本地，手动复制发布
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .base import BasePublisher
from ..models import ContentItem, ContentStatus


class XiaoHongShuPublisher(BasePublisher):
    """小红书内容发布器"""
    
    platform_name = "xiaohongshu"
    
    def __init__(self, config: dict = None):
        super().__init__(config)
        self.draft_dir = Path(self.config.get("draft_dir", "~/.huaqi/drafts/xiaohongshu"))
        self.draft_dir = self.draft_dir.expanduser()
        self.draft_dir.mkdir(parents=True, exist_ok=True)
        
        # 真实发布配置 (可选)
        self.api_token = self.config.get("api_token") or os.getenv("XIAOHONGSHU_TOKEN")
        self.enable_auto_publish = self.config.get("auto_publish", False) and bool(self.api_token)
    
    async def publish(self, item: ContentItem) -> bool:
        """发布内容到小红书
        
        当前实现: 保存为草稿文件
        未来: 支持 API 自动发布
        """
        try:
            if self.enable_auto_publish:
                return await self._auto_publish(item)
            else:
                return await self._save_draft(item)
                
        except Exception as e:
            print(f"[XiaoHongShu] 发布失败: {e}")
            item.status = ContentStatus.FAILED
            return False
    
    async def _save_draft(self, item: ContentItem) -> bool:
        """保存为草稿文件"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{item.id[:8]}.md"
        filepath = self.draft_dir / filename
        
        # 构建草稿内容
        content = self._build_draft(item)
        
        # 保存文件
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        # 同时保存元数据
        meta_filepath = self.draft_dir / f"{filename}.json"
        metadata = {
            "item_id": item.id,
            "source": item.source.value,
            "original_url": item.url,
            "title": item.title,
            "tags": item.xiaohongshu_tags,
            "created_at": datetime.now().isoformat(),
            "status": "draft",
        }
        with open(meta_filepath, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        item.status = ContentStatus.PUBLISHED  # 标记为已处理
        print(f"[XiaoHongShu] 草稿已保存: {filepath}")
        return True
    
    async def _auto_publish(self, item: ContentItem) -> bool:
        """自动发布到小红书 (待实现)"""
        # TODO: 实现小红书 API 发布
        print("[XiaoHongShu] 自动发布功能待实现，保存为草稿")
        return await self._save_draft(item)
    
    def _build_draft(self, item: ContentItem) -> str:
        """构建草稿内容"""
        lines = [
            f"# {item.title}",
            "",
            "---",
            "",
            "## 小红书内容",
            "",
            item.xiaohongshu_content or item.content,
            "",
            "---",
            "",
            "## 元数据",
            "",
            f"- **来源**: {item.source.value}",
            f"- **原文链接**: {item.url or 'N/A'}",
            f"- **作者**: {item.author or 'N/A'}",
            "",
            "## 标签",
            "",
        ]
        
        for tag in item.xiaohongshu_tags:
            lines.append(f"- {tag}")
        
        lines.extend([
            "",
            "---",
            "",
            "## 操作说明",
            "",
            "1. 复制上方的【小红书内容】",
            "2. 打开小红书 APP",
            "3. 创建新笔记，粘贴内容",
            "4. 选择合适的图片",
            "5. 点击发布",
            "",
        ])
        
        return "\n".join(lines)
    
    async def health_check(self) -> bool:
        """检查发布器状态"""
        # 检查草稿目录是否可写
        try:
            test_file = self.draft_dir / ".health_check"
            test_file.write_text("ok")
            test_file.unlink()
            return True
        except:
            return False
    
    def list_drafts(self) -> list:
        """列出所有草稿"""
        drafts = []
        for f in self.draft_dir.glob("*.md"):
            if not f.name.endswith(".json.md"):
                drafts.append({
                    "filename": f.name,
                    "path": str(f),
                    "created": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
                })
        return sorted(drafts, key=lambda x: x["created"], reverse=True)
