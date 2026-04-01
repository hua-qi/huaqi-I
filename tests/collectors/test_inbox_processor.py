import pytest
from pathlib import Path
from huaqi_src.collectors.inbox_processor import InboxProcessor

def test_process_markdown_file(tmp_path):
    inbox_dir = tmp_path / "inbox" / "work_docs"
    inbox_dir.mkdir(parents=True)
    archive_dir = tmp_path / "memory" / "work_docs"
    
    md_file = inbox_dir / "note.md"
    md_file.write_text("# 项目A设计\n今天完成了核心模块的设计。", encoding="utf-8")
    
    processor = InboxProcessor(data_dir=tmp_path)
    docs = processor.sync()
    
    assert len(docs) == 1
    assert docs[0].doc_type == "work_doc"
    assert "项目A设计" in docs[0].content
    assert docs[0].source.startswith("file:")

def test_processed_file_is_archived(tmp_path):
    inbox_dir = tmp_path / "inbox" / "work_docs"
    inbox_dir.mkdir(parents=True)
    
    md_file = inbox_dir / "report.md"
    md_file.write_text("季度报告内容", encoding="utf-8")
    
    processor = InboxProcessor(data_dir=tmp_path)
    processor.sync()
    
    assert not md_file.exists()
    archive_dir = tmp_path / "memory" / "work_docs"
    archived_files = list(archive_dir.glob("*.md"))
    assert len(archived_files) == 1

def test_txt_file_is_also_supported(tmp_path):
    inbox_dir = tmp_path / "inbox" / "work_docs"
    inbox_dir.mkdir(parents=True)
    
    txt_file = inbox_dir / "notes.txt"
    txt_file.write_text("纯文本笔记", encoding="utf-8")
    
    processor = InboxProcessor(data_dir=tmp_path)
    docs = processor.sync()
    
    assert len(docs) == 1
    assert "纯文本笔记" in docs[0].content

def test_sync_with_empty_inbox_returns_empty_list(tmp_path):
    inbox_dir = tmp_path / "inbox" / "work_docs"
    inbox_dir.mkdir(parents=True)
    
    processor = InboxProcessor(data_dir=tmp_path)
    docs = processor.sync()
    
    assert docs == []
