# CLI 报告查看与生成系统 (Report Viewer)

## 概述
统一的报告管理器（`ReportManager`）和报告 CLI 命令，用于高效查找和实时生成各类个人分析报告（包括晨间简报、日终复盘、周报和季报）。该功能使得用户无论在顶层 CLI 还是在聊天会话中，都能快速获取最新的总结与洞察。

## 设计思路
- **职责解耦**：将报告查找与生成的逻辑封装在 `ReportManager` 中，而具体的报告生成逻辑（调用 LLM 和收集数据）则由各报告类型自带的 Agent（如 `DailyReportAgent`, `WeeklyReportAgent`）处理。
- **懒生成策略**：默认情况下优先查找磁盘中已存在的报告文件以节省时间和 API 成本；仅在找不到对应报告且请求日期为“今天”或显式指定了 `--force` 强制生成时，才触发实时生成流程。
- **全场景覆盖**：支持顶层 CLI (`huaqi report ...`) 用于一次性快速查询，以及对话内部聊天指令 (`/report ...`) 用于会话期间无缝查阅。

## 实现细节

### ReportManager 核心逻辑
通过 `get_or_generate_report(report_type, date_str, force)` 提供统一的报告获取接口：
1. **日期解析**：支持 `today`，`yesterday` 以及 `YYYY-MM-DD` 格式的日期解析。
2. **路由映射**：通过 `report_type` (`morning`, `daily`, `weekly`, `quarterly`) 匹配对应的输出文件名、子目录及具体的 Agent 类。
3. **缓存与生成**：
   - 如果对应文件已存在且未开启 `--force`，直接读取文件内容并返回。
   - 如果文件不存在且不是今天，提示无法生成历史报告。
   - 触发对应 Agent 的 `.run()` 方法执行实时生成。

### 命令层级
- **顶层命令**：在 `cli/commands/report.py` 中定义 `huaqi report morning/daily/weekly`，通过 Typer 支持参数与选项（如 `--force`）。
- **聊天内命令**：在 `cli/chat.py` 的 `_handle_report_command` 中拦截 `/report` 指令，并调用 `ReportManager`。

## 接口与使用

### 顶层 CLI
```bash
# 查看今日晨报
huaqi report morning

# 查看昨日日结
huaqi report daily yesterday

# 强制重新生成本周周报
huaqi report weekly --force
```

### 聊天内指令
```
/report morning             # 查看晨间简报
/report daily               # 查看日终复盘
/report weekly              # 查看周报（支持别名 /report w）
/report quarterly           # 查看季报
/report insights            # 查看基于模式学习的个人洞察
```

## 相关文件
- `huaqi_src/layers/capabilities/reports/manager.py` - ReportManager 核心实现
- `huaqi_src/cli/commands/report.py` - 顶层 CLI 报告命令的路由绑定
- `huaqi_src/cli/chat.py` - `/report` 聊天命令解析逻辑
- `tests/layers/capabilities/reports/test_manager.py` - 核心逻辑单元测试
- `tests/cli/commands/test_report.py` - 顶层 CLI 单元测试
- `tests/cli/test_chat_report.py` - 聊天命令集成测试

---
**文档版本**: v1.0  
**最后更新**: 2026-04-03
