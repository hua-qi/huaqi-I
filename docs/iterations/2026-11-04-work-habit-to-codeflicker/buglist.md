# work-habit-to-codeflicker 迭代 Bug 清单

**所属迭代**: 2026-11-04-work-habit-to-codeflicker

---

## Round 1 - 2026-11-04

| ID | 描述 | 复现命令 | 优先级 | 状态 |
|----|------|---------|--------|------|
| B-001 | `CodeflickerSource` / `HuaqiDocsSource` 的 `fetch_documents()` 中 `datetime.fromtimestamp()` 返回 naive datetime，当调用方传入 aware datetime（如 `cli_chat_watcher` 解析的 `+00:00` 时间戳）时，比较会抛 `TypeError: can't compare offset-naive and offset-aware datetimes` | `pytest tests/unit/layers/data/test_work_sources.py` | P1 | fixed |
| B-002 | `DistillationPipeline.process()` 中 `new_dimension_hint` 处理使用裸 `except Exception`，会静默吞掉 `DimensionNotFoundError` 以外的所有异常（如磁盘满、权限错误），导致维度创建失败无感知 | `pytest tests/unit/layers/data/test_raw_signal_pipeline.py` | P1 | fixed |
| B-003 | `CLIChatWatcher._process_codeflicker_session()` 中 `t.join()` 无超时，若 `WorkSignalIngester.ingest()` 因网络或磁盘问题挂起，会永久阻塞调用线程 | 手动测试：令 `ingest()` 永不返回 | P1 | fixed |
| B-004 | `TelosManager.on_work_style_updated` 类型注解为 `Optional[callable]`，`callable` 是内置函数而非类型，应为 `Optional[Callable[[], None]]` | `mypy huaqi_src/layers/growth/telos/manager.py` | P2 | fixed |
