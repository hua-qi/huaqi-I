# 全局 Bug 清单

> 仅收录影响关键链路的 bug，每次迭代验收时必须逐条回归验证。

## 活跃 Bug

| ID | 描述 | 优先级 | 状态 | 发现迭代 | 修复迭代 |
|----|------|--------|------|---------| --------|

## 回归记录

| ID | 迭代 | 验证结果 | 备注 |
|----|------|---------|------|
| B-001 | 2026-11-04-work-habit-to-codeflicker | ✅ fixed | `datetime.fromtimestamp(tz=utc)` + `astimezone` 统一 aware 比较 |
| B-002 | 2026-11-04-work-habit-to-codeflicker | ✅ fixed | 裸 `except Exception` 改为精确捕获 `DimensionNotFoundError` |
| B-003 | 2026-11-04-work-habit-to-codeflicker | ✅ fixed | `t.join(timeout=30)`，线程设为 daemon |

## 已关闭 Bug

| ID | 描述 | 关闭原因 | 关闭迭代 |
|----|------|---------| --------|
| B-001 | `CodeflickerSource` / `HuaqiDocsSource.fetch_documents()` naive vs aware datetime 比较崩溃 | 已修复验证通过 | 2026-11-04-work-habit-to-codeflicker |
| B-002 | `DistillationPipeline.process()` 的 `new_dimension_hint` 块使用裸 `except Exception`，静默吞掉非预期异常 | 已修复验证通过 | 2026-11-04-work-habit-to-codeflicker |
| B-003 | `CLIChatWatcher._process_codeflicker_session()` 线程 `join()` 无超时，`ingest()` 挂起会永久阻塞 | 已修复验证通过 | 2026-11-04-work-habit-to-codeflicker |
