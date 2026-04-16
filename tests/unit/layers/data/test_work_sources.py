import datetime
from pathlib import Path
from huaqi_src.layers.data.collectors.work_sources.codeflicker import CodeflickerSource


def test_fetch_documents_returns_file_contents(tmp_path):
    chats_dir = tmp_path / "memory" / "cli_chats"
    chats_dir.mkdir(parents=True)
    (chats_dir / "session1.md").write_text("内容A")
    (chats_dir / "session2.md").write_text("内容B")

    source = CodeflickerSource(cli_chats_dir=chats_dir)
    docs = source.fetch_documents()
    assert len(docs) == 2
    assert "内容A" in docs or "内容B" in docs


def test_fetch_documents_filters_by_since(tmp_path):
    chats_dir = tmp_path / "cli_chats"
    chats_dir.mkdir(parents=True)
    old_file = chats_dir / "old.md"
    new_file = chats_dir / "new.md"
    old_file.write_text("旧内容")
    new_file.write_text("新内容")

    import time; time.sleep(0.05)
    cutoff = datetime.datetime.now(tz=datetime.timezone.utc)
    time.sleep(0.05)
    new_file.touch()

    source = CodeflickerSource(cli_chats_dir=chats_dir)
    docs = source.fetch_documents(since=cutoff)
    assert docs == ["新内容"]


def test_fetch_documents_filters_by_since_aware(tmp_path):
    chats_dir = tmp_path / "cli_chats_aware"
    chats_dir.mkdir(parents=True)
    old_file = chats_dir / "old.md"
    new_file = chats_dir / "new.md"
    old_file.write_text("旧内容2")
    new_file.write_text("新内容2")

    import time; time.sleep(0.05)
    cutoff = datetime.datetime.now(tz=datetime.timezone.utc)
    time.sleep(0.05)
    new_file.touch()

    source = CodeflickerSource(cli_chats_dir=chats_dir)
    docs = source.fetch_documents(since=cutoff)
    assert docs == ["新内容2"]


def test_huaqi_docs_source_reads_md_files(tmp_path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "designs").mkdir(parents=True)
    (docs_dir / "designs" / "design1.md").write_text("设计文档内容")

    from huaqi_src.layers.data.collectors.work_sources.huaqi_docs import HuaqiDocsSource
    source = HuaqiDocsSource(docs_dir=docs_dir)
    docs = source.fetch_documents()
    assert "设计文档内容" in docs


def test_kuaishou_docs_source_returns_list():
    from huaqi_src.layers.data.collectors.work_sources.kuaishou_docs import KuaishouDocsSource
    source = KuaishouDocsSource()
    docs = source.fetch_documents()
    assert isinstance(docs, list)



def test_huaqi_docs_source_reads_md_files(tmp_path):
    docs_dir = tmp_path / "docs"
    (docs_dir / "designs").mkdir(parents=True)
    (docs_dir / "designs" / "design1.md").write_text("设计文档内容")

    from huaqi_src.layers.data.collectors.work_sources.huaqi_docs import HuaqiDocsSource
    source = HuaqiDocsSource(docs_dir=docs_dir)
    docs = source.fetch_documents()
    assert "设计文档内容" in docs


def test_kuaishou_docs_source_returns_list():
    from huaqi_src.layers.data.collectors.work_sources.kuaishou_docs import KuaishouDocsSource
    source = KuaishouDocsSource()
    docs = source.fetch_documents()
    assert isinstance(docs, list)
