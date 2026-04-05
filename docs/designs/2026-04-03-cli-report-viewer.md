# CLI 报告查看与生成系统

**Date:** 2026-04-03

## Context
目前系统已经支持 `MorningBriefAgent`（晨间简报）和 `DailyReportAgent`（日终复盘）等在后台定时生成报告，并将其保存在数据目录中。然而，用户无法通过 CLI 方便地主动查看这些报告，尤其是当天的早报或日报。我们需要设计一套方案，支持通过 CLI 命令（包括顶级命令和对话内命令）查看早报、日报、周报、季报等报告内容。

## Discussion
在讨论中，我们明确了以下核心需求与交互方式：
1. **双交互入口**：既支持顶级子命令（如 `huaqi report daily`，适合快速查看），也支持在 `huaqi chat` 中的聊天内命令（如 `/report daily`，适合在对话时调出）。
2. **缺失时的处理**：如果用户请求的某天报告尚未生成（如今天的早报），系统应触发 Agent 实时生成并展示，而不是直接返回找不到。
3. **支持历史日期**：不仅支持查看当前周期的报告，还要支持查询历史记录（如 `yesterday`, `last-week` 或具体日期）。

针对架构实现，我们探讨了两种方案：
- **方案 A（统一报告管理器）**：新增一个专门的 `ReportManager` 统一处理参数解析、查找和实时生成逻辑，CLI 只负责调用展示。
- **方案 B（直接调用）**：在 CLI 层直接写查找和生成的逻辑。

经过评估，选择了高内聚低耦合的**方案 A**，以利于后续扩展其他报告和支持多端调用。

## Approach
采用 **统一报告管理器 (ReportManager)** 方案。核心思路是将报告的“定位”和“生成”职责下沉至管理器，CLI 仅作为调度和展示层：
- 提供基于自然语言和具体日期的报告检索。
- 采用显式的顶级 CLI 结构（如 `huaqi report morning`）。
- 聊天内的 `/report` 命令完全复用底层逻辑，并提供友好的加载提示。

## Architecture
具体的技术细节及组件划分如下：

1. **核心层：统一报告管理器 (ReportManager)**
   - **位置**：`huaqi_src/layers/capabilities/reports/manager.py`
   - **核心职责**：
     - 提供 `get_or_generate_report(report_type: str, date_str: str = "today") -> str` 接口。
     - 负责解析日期（将 `today`, `yesterday`, `this-week` 转换为准确的查询时间区间）。
     - 检查目标报告 Markdown 文件是否存在。
     - 若文件缺失，根据 `report_type` 映射并实例化对应的 Agent（如 `DailyReportAgent`）实时生成，完成后返回内容。

2. **展示层 A：顶级 CLI 命令**
   - **位置**：`huaqi_src/cli/commands/report.py` (挂载至 `cli/__init__.py`)
   - **命令结构**：提供明确的子命令如 `huaqi report morning [DATE]`, `huaqi report daily [DATE]`, `huaqi report weekly [DATE]` 等。
   - **拓展参数**：增加 `--force`（或 `-f`）选项，允许用户强制覆盖重新生成当前报告。

3. **展示层 B：对话内斜杠命令**
   - **位置**：修改 `huaqi_src/cli/chat.py` 中的 `_handle_report_command`。
   - **集成逻辑**：
     - 解析 `/report <type> [date]`。
     - 对接 `ReportManager.get_or_generate_report`。
     - 兼容处理系统现有的 `/report insights` 命令。
     - 在请求 Agent 实时生成时，利用 UI 组件展示正在生成的“加载提示”，避免阻塞体验。
