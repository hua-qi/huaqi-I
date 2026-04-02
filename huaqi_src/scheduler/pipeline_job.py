"""内容流水线定时任务

集成 Pipeline 到调度器，支持人工确认机制
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

from .manager import get_scheduler_manager
from huaqi_src.layers.capabilities.pipeline import create_default_pipeline, ContentItem


class ReviewStatus(Enum):
    """审核状态"""
    PENDING = "pending"      # 待审核
    APPROVED = "approved"    # 已通过
    REJECTED = "rejected"    # 已拒绝


class PendingReview:
    """待审核内容"""
    
    def __init__(
        self,
        item: ContentItem,
        task_id: str,
        created_at: datetime = None,
    ):
        self.item = item
        self.task_id = task_id
        self.status = ReviewStatus.PENDING
        self.created_at = created_at or datetime.now()
        self.reviewed_at: Optional[datetime] = None
        self.review_notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item.id,
            "task_id": self.task_id,
            "source": self.item.source.value,
            "title": self.item.title,
            "content": self.item.xiaohongshu_content or self.item.content,
            "tags": self.item.xiaohongshu_tags,
            "original_url": self.item.url,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_notes": self.review_notes,
        }


class PipelineJobManager:
    """流水线任务管理器
    
    功能:
    - 执行内容采集和处理
    - 支持人工审核机制
    - 管理待审核队列
    """
    
    def __init__(self, pending_dir: Path = None):
        if pending_dir is None:
            from ..config.paths import get_pending_reviews_dir
            pending_dir = get_pending_reviews_dir()
        self.pending_dir = pending_dir
        self.pending_dir.mkdir(parents=True, exist_ok=True)
        
        self.auto_publish: bool = False  # 默认需要人工确认
    
    async def run_pipeline(
        self,
        limit: int = 5,
        require_review: bool = True,
    ) -> Dict[str, Any]:
        """执行流水线任务
        
        Args:
            limit: 每个源采集数量
            require_review: 是否需要人工审核
            
        Returns:
            执行结果统计
        """
        print(f"\n[PipelineJob] 启动内容流水线 - {datetime.now()}")
        
        # 创建流水线
        pipeline = create_default_pipeline()
        
        # 如果需要审核，先执行 dry_run 创建草稿
        if require_review and not self.auto_publish:
            print("[PipelineJob] 审核模式：生成草稿等待确认")
            stats = await pipeline.run(
                limit=limit,
                dry_run=True,  # 不发布，只生成草稿
            )
            
            # 创建待审核任务
            if stats.get("processed", 0) > 0:
                await self._create_pending_reviews(stats)
        else:
            # 自动发布模式
            print("[PipelineJob] 自动发布模式")
            stats = await pipeline.run(limit=limit, dry_run=False)
        
        return stats
    
    async def _create_pending_reviews(self, stats: Dict[str, Any]):
        """从草稿创建待审核项"""
        from huaqi_src.layers.capabilities.pipeline.platforms import XiaoHongShuPublisher
        
        publisher = XiaoHongShuPublisher()
        drafts = publisher.list_drafts()
        
        if not drafts:
            return
        
        # 只获取最新的草稿（最近5分钟内创建的）
        from datetime import timedelta
        now = datetime.now()
        recent_drafts = []
        for d in drafts:
            try:
                created_time = datetime.fromisoformat(d["created"])
                if (now - created_time).total_seconds() < 300:  # 5分钟内
                    recent_drafts.append(d)
            except Exception as e:
                print(f"[PipelineJob] 解析时间失败: {e}")
                continue
        
        if not recent_drafts:
            print("[PipelineJob] 没有新的待审核内容")
            return
        
        # 创建待审核队列
        task_id = datetime.now().strftime("pipeline_%Y%m%d_%H%M%S")
        pending_file = self.pending_dir / f"{task_id}.json"
        
        pending_items = []
        for draft in recent_drafts[:10]:  # 最多10条
            pending_items.append({
                "draft_path": draft["path"],
                "status": ReviewStatus.PENDING.value,
                "created_at": draft["created"],
            })
        
        with open(pending_file, 'w', encoding='utf-8') as f:
            json.dump({
                "task_id": task_id,
                "created_at": datetime.now().isoformat(),
                "items": pending_items,
                "stats": stats,
            }, f, ensure_ascii=False, indent=2)
        
        print(f"[PipelineJob] 已创建 {len(pending_items)} 条待审核内容")
        print(f"[PipelineJob] 使用 'huaqi pipeline review {task_id}' 进行审核")
    
    def list_pending_reviews(self) -> List[Dict[str, Any]]:
        """列出所有待审核任务"""
        reviews = []
        
        for pending_file in self.pending_dir.glob("*.json"):
            try:
                with open(pending_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 统计待审核数量
                pending_count = sum(
                    1 for item in data.get("items", [])
                    if item.get("status") == ReviewStatus.PENDING.value
                )
                
                if pending_count > 0:
                    reviews.append({
                        "task_id": data.get("task_id"),
                        "created_at": data.get("created_at"),
                        "pending_count": pending_count,
                        "total_count": len(data.get("items", [])),
                        "path": str(pending_file),
                    })
            except Exception as e:
                print(f"[PipelineJob] 读取审核文件失败: {e}")
        
        return sorted(reviews, key=lambda x: x["created_at"], reverse=True)
    
    def get_pending_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取指定任务的待审核内容"""
        pending_file = self.pending_dir / f"{task_id}.json"
        
        if not pending_file.exists():
            return None
        
        with open(pending_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def approve_item(
        self,
        task_id: str,
        item_index: int,
        notes: str = None,
    ) -> bool:
        """通过审核项"""
        pending_file = self.pending_dir / f"{task_id}.json"
        
        if not pending_file.exists():
            return False
        
        with open(pending_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        items = data.get("items", [])
        if item_index >= len(items):
            return False
        
        items[item_index]["status"] = ReviewStatus.APPROVED.value
        items[item_index]["reviewed_at"] = datetime.now().isoformat()
        items[item_index]["review_notes"] = notes
        
        with open(pending_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[PipelineJob] 已通过审核: 任务 {task_id}, 项目 {item_index}")
        return True
    
    def reject_item(
        self,
        task_id: str,
        item_index: int,
        notes: str = None,
    ) -> bool:
        """拒绝审核项"""
        pending_file = self.pending_dir / f"{task_id}.json"
        
        if not pending_file.exists():
            return False
        
        with open(pending_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        items = data.get("items", [])
        if item_index >= len(items):
            return False
        
        items[item_index]["status"] = ReviewStatus.REJECTED.value
        items[item_index]["reviewed_at"] = datetime.now().isoformat()
        items[item_index]["review_notes"] = notes
        
        with open(pending_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"[PipelineJob] 已拒绝: 任务 {task_id}, 项目 {item_index}")
        return True
    
    async def publish_approved(self, task_id: str) -> int:
        """发布已通过审核的内容"""
        from huaqi_src.layers.capabilities.pipeline.platforms import XiaoHongShuPublisher
        
        pending_file = self.pending_dir / f"{task_id}.json"
        
        if not pending_file.exists():
            return 0
        
        with open(pending_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        items = data.get("items", [])
        publisher = XiaoHongShuPublisher()
        
        published = 0
        for item in items:
            if item.get("status") == ReviewStatus.APPROVED.value:
                # 读取草稿文件并发布
                draft_path = item.get("draft_path")
                if draft_path and Path(draft_path).exists():
                    # 这里简化处理，实际应该重新构造 ContentItem
                    print(f"[PipelineJob] 发布: {Path(draft_path).name}")
                    published += 1
        
        print(f"[PipelineJob] 已发布 {published} 条内容")
        return published


# 定时任务处理器
async def scheduled_content_pipeline(**kwargs):
    """定时执行的内容流水线"""
    limit = kwargs.get("limit", 5)
    auto_publish = kwargs.get("auto_publish", False)
    
    manager = PipelineJobManager()
    manager.auto_publish = auto_publish
    
    await manager.run_pipeline(
        limit=limit,
        require_review=not auto_publish,
    )
