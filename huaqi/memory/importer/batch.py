"""批量导入管理器"""

from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from datetime import datetime
import shutil
import yaml

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from .factory import ImporterFactory
from .base import ImportResult
from ..storage.user_isolated import UserMemoryManager


console = Console()


@dataclass
class BatchImportResult:
    """批量导入结果"""
    total_files: int
    successful: int
    failed: int
    skipped: int
    results: List[ImportResult]
    duration_seconds: float
    
    @property
    def success_rate(self) -> float:
        if self.total_files == 0:
            return 0.0
        return self.successful / self.total_files * 100


class BatchImporter:
    """批量导入管理器
    
    支持:
    - 批量导入文件
    - 智能分类
    - 冲突处理
    - 增量导入
    - 导入预览
    - 多用户隔离
    """
    
    def __init__(
        self,
        memory_manager: UserMemoryManager,
        llm_client=None,
        dry_run: bool = False
    ):
        self.memory_manager = memory_manager
        self.llm_client = llm_client
        self.dry_run = dry_run
        self._conflict_strategy = "skip"  # skip / overwrite / rename / ask
    
    def import_directory(
        self,
        source_dir: Path,
        pattern: str = "**/*",
        exclude_patterns: List[str] = None,
        progress_callback: Optional[Callable] = None
    ) -> BatchImportResult:
        """批量导入目录
        
        Args:
            source_dir: 源目录
            pattern: 文件匹配模式
            exclude_patterns: 排除模式列表
            progress_callback: 进度回调函数
            
        Returns:
            BatchImportResult: 批量导入结果
        """
        import time
        start_time = time.time()
        
        # 1. 收集文件
        files = self._collect_files(source_dir, pattern, exclude_patterns or [])
        
        if not files:
            console.print("[yellow]未找到可导入的文件[/yellow]")
            return BatchImportResult(
                total_files=0,
                successful=0,
                failed=0,
                skipped=0,
                results=[],
                duration_seconds=0
            )
        
        console.print(f"\n[bold]发现 {len(files)} 个文件待导入[/bold]\n")
        
        # 2. 批量导入
        results = []
        successful = 0
        failed = 0
        skipped = 0
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task(
                f"导入中...",
                total=len(files)
            )
            
            for file_path in files:
                progress.update(task, description=f"导入: {file_path.name}")
                
                result = self._import_single_file(file_path)
                results.append(result)
                
                if result.success:
                    successful += 1
                    # 如果不是 dry_run，实际保存到记忆库
                    if not self.dry_run:
                        self._save_to_memory(result)
                else:
                    if "已存在" in (result.error_message or ""):
                        skipped += 1
                    else:
                        failed += 1
                
                progress.advance(task)
                
                if progress_callback:
                    progress_callback(result)
        
        duration = time.time() - start_time
        
        # 3. 显示结果
        self._display_results(results, duration)
        
        return BatchImportResult(
            total_files=len(files),
            successful=successful,
            failed=failed,
            skipped=skipped,
            results=results,
            duration_seconds=duration
        )
    
    def import_single(
        self,
        file_path: Path,
        memory_type: Optional[str] = None,
        tags: List[str] = None
    ) -> ImportResult:
        """导入单个文件
        
        Args:
            file_path: 文件路径
            memory_type: 强制指定记忆类型
            tags: 额外标签
            
        Returns:
            ImportResult: 导入结果
        """
        # 1. 获取导入器
        importer = ImporterFactory.get_importer(file_path, self.llm_client)
        
        if not importer:
            return ImportResult(
                success=False,
                file_path=file_path,
                memory_type="unknown",
                title=file_path.stem,
                content="",
                metadata={},
                tags=[],
                error_message=f"不支持的文件格式: {file_path.suffix}"
            )
        
        # 2. 导入文件
        result = importer.import_file(file_path, auto_classify=True)
        
        # 3. 应用强制参数
        if memory_type:
            result.memory_type = memory_type
        if tags:
            result.tags = list(set(result.tags + tags))
        
        # 4. 保存
        if result.success and not self.dry_run:
            self._save_to_memory(result)
        
        return result
    
    def preview_import(
        self,
        source_dir: Path,
        pattern: str = "**/*"
    ) -> List[Dict[str, Any]]:
        """预览导入结果（不实际导入）
        
        Args:
            source_dir: 源目录
            pattern: 文件匹配模式
            
        Returns:
            预览信息列表
        """
        files = self._collect_files(source_dir, pattern, [])
        
        preview = []
        for file_path in files:
            importer = ImporterFactory.get_importer(file_path, self.llm_client)
            
            if importer:
                # 只提取文本和分类，不保存
                content = importer.extract_text(file_path)
                classification = importer._default_classification(file_path)
                
                preview.append({
                    "file": str(file_path.relative_to(source_dir)),
                    "size": file_path.stat().st_size,
                    "type": classification["type"],
                    "will_import": True
                })
            else:
                preview.append({
                    "file": str(file_path.relative_to(source_dir)),
                    "size": file_path.stat().st_size,
                    "type": "unknown",
                    "will_import": False,
                    "reason": "不支持的格式"
                })
        
        return preview
    
    def _collect_files(
        self,
        source_dir: Path,
        pattern: str,
        exclude_patterns: List[str]
    ) -> List[Path]:
        """收集待导入的文件"""
        files = []
        
        for file_path in source_dir.glob(pattern):
            if not file_path.is_file():
                continue
            
            # 检查排除模式
            should_exclude = False
            for exclude in exclude_patterns:
                if exclude in str(file_path):
                    should_exclude = True
                    break
            
            if not should_exclude:
                files.append(file_path)
        
        return sorted(files)
    
    def _import_single_file(self, file_path: Path) -> ImportResult:
        """导入单个文件"""
        return self.import_single(file_path)
    
    def _save_to_memory(self, result: ImportResult):
        """保存导入结果到记忆库（Markdown 格式）"""
        if not result.success:
            return
        
        # 生成唯一文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        base_name = result.file_path.stem
        filename = f"{base_name}_{timestamp}.md"
        
        # 获取存储路径
        memory_path = self.memory_manager.get_memory_path(result.memory_type, filename)
        
        # 处理冲突
        counter = 1
        while memory_path.exists():
            filename = f"{base_name}_{timestamp}_{counter}.md"
            memory_path = self.memory_manager.get_memory_path(result.memory_type, filename)
            counter += 1
        
        # 构建 Markdown 内容
        content = self._build_memory_content(result)
        
        # 保存文件
        memory_path.parent.mkdir(parents=True, exist_ok=True)
        with open(memory_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        # 5. TODO: 生成向量索引
        # self._create_vector_index(result, memory_path)
    
    def _build_memory_content(self, result: ImportResult) -> str:
        """构建记忆文件内容"""
        lines = [
            f"# {result.title}",
            "",
            f"**类型**: {result.memory_type}",
            f"**来源**: {result.file_path}",
            f"**导入时间**: {datetime.now().isoformat()}",
            f"**标签**: {', '.join(result.tags) if result.tags else '无'}",
            "",
            "---",
            "",
            "## 内容",
            "",
            result.content,
            "",
            "---",
            "",
            "## 元数据",
            "",
            "```yaml",
            yaml.dump(result.metadata, allow_unicode=True, default_flow_style=False),
            "```",
        ]
        
        if result.extracted_insights:
            lines.extend([
                "",
                "## 提取的洞察",
                "",
            ])
            for insight in result.extracted_insights:
                lines.append(f"- {insight}")
        
        return "\n".join(lines)
    
    def _display_results(self, results: List[ImportResult], duration: float):
        """显示导入结果"""
        console.print(f"\n[bold]导入完成[/bold] (耗时 {duration:.2f} 秒)\n")
        
        # 按类型统计
        type_stats: Dict[str, int] = {}
        for result in results:
            if result.success:
                type_stats[result.memory_type] = type_stats.get(result.memory_type, 0) + 1
        
        if type_stats:
            console.print("[bold]按类型分布:[/bold]")
            for mem_type, count in sorted(type_stats.items()):
                console.print(f"  {mem_type}: {count} 个文件")
        
        # 显示失败项
        failed = [r for r in results if not r.success]
        if failed:
            console.print(f"\n[bold red]失败项 ({len(failed)} 个):[/bold red]")
            for result in failed[:5]:  # 只显示前5个
                console.print(f"  - {result.file_path.name}: {result.error_message}")
            if len(failed) > 5:
                console.print(f"  ... 还有 {len(failed) - 5} 个")


class ImportWizard:
    """导入向导
    
    交互式引导用户完成导入
    """
    
    def __init__(self, batch_importer: BatchImporter):
        self.importer = batch_importer
    
    def run(self):
        """运行导入向导"""
        console.print("\n[bold cyan]🌸 Huaqi 记忆导入向导[/bold cyan]\n")
        
        # 1. 选择源目录
        source = self._ask_source()
        if not source:
            return
        
        # 2. 预览
        if self._ask_yes_no("是否先预览导入结果？"):
            preview = self.importer.preview_import(Path(source))
            self._show_preview(preview)
        
        # 3. 配置选项
        options = self._configure_options()
        
        # 4. 执行导入
        if self._ask_yes_no("确认开始导入？"):
            result = self.importer.import_directory(
                Path(source),
                exclude_patterns=options.get("exclude", [])
            )
            self._show_summary(result)
    
    def _ask_source(self) -> Optional[str]:
        """询问源目录"""
        from rich.prompt import Prompt
        
        source = Prompt.ask(
            "请输入要导入的目录路径",
            default=str(Path.home() / "Documents")
        )
        
        if not Path(source).exists():
            console.print(f"[red]路径不存在: {source}[/red]")
            return None
        
        return source
    
    def _ask_yes_no(self, question: str) -> bool:
        """询问是/否"""
        from rich.prompt import Confirm
        return Confirm.ask(question, default=True)
    
    def _show_preview(self, preview: List[Dict[str, Any]]):
        """显示预览"""
        console.print(f"\n[bold]预览: 共 {len(preview)} 个文件[/bold]\n")
        
        from rich.table import Table
        table = Table(show_header=True, header_style="bold")
        table.add_column("文件")
        table.add_column("类型")
        table.add_column("大小", justify="right")
        table.add_column("状态")
        
        for item in preview[:20]:  # 只显示前20个
            status = "✓ 将导入" if item["will_import"] else "✗ 跳过"
            status_style = "green" if item["will_import"] else "red"
            table.add_row(
                item["file"],
                item["type"],
                f"{item['size'] / 1024:.1f} KB",
                f"[{status_style}]{status}[/{status_style}]"
            )
        
        if len(preview) > 20:
            table.add_row("...", "", "", f"还有 {len(preview) - 20} 个文件")
        
        console.print(table)
        console.print()
    
    def _configure_options(self) -> Dict[str, Any]:
        """配置导入选项"""
        options = {}
        
        # 排除模式
        if self._ask_yes_no("是否排除某些文件？"):
            from rich.prompt import Prompt
            exclude = Prompt.ask(
                "请输入排除模式（用逗号分隔）",
                default="node_modules,.git,__pycache__"
            )
            options["exclude"] = [e.strip() for e in exclude.split(",")]
        
        return options
    
    def _show_summary(self, result: BatchImportResult):
        """显示导入摘要"""
        console.print(f"\n[bold green]导入完成![/bold green]\n")
        console.print(f"总计: {result.total_files} 个文件")
        console.print(f"成功: {result.successful} 个")
        console.print(f"跳过: {result.skipped} 个")
        console.print(f"失败: {result.failed} 个")
        console.print(f"成功率: {result.success_rate:.1f}%")
        console.print(f"耗时: {result.duration_seconds:.2f} 秒")
