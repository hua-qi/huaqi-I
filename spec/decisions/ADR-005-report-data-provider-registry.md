# ADR-005: 报告系统引入 DataProvider 注册表

**状态**: 已采纳
**日期**: 2026-03-31

## 背景

报告系统有 4 个报告类（晨报、日报、周报、季报），每个各自在 `_build_context()` 内硬编码数据读取逻辑。随着数据模块增多（people、learning、growth、events），每次新增数据来源都需要同时修改多个报告文件，违反开闭原则，且容易遗漏。

## 决策

引入 `DataProvider` 抽象基类 + 全局注册表（`_registry`）：

- 定义 `DataProvider` ABC，要求实现 `get_context(report_type, date_range) -> str | None`
- 全局 `_registry` 列表存放所有已注册的 Provider 实例
- `get_providers(report_type)` 按 `supported_reports` 过滤并按 `priority` 排序
- `context_builder.build_context()` 遍历所有匹配 Provider，拼接非 None 结果
- 报告类在 `__init__` 中调用 `_register_providers()`，注册带正确 `data_dir` 的 Provider 实例

## 备选方案

**方案 A：继续内嵌，拆分为私有方法**
在各报告类中将数据读取拆分为 `_get_world_context()`、`_get_diary_context()` 等私有方法。问题：仍然是 N 个文件各写一遍，新增模块仍需改 4 处。

**方案 B：集中式 ContextBuilder，硬编码所有数据源**
`ContextBuilder` 直接内嵌所有数据读取逻辑。问题：ContextBuilder 与所有数据模块强耦合，变成了另一个大泥球。

**方案 C（采纳）：注册表模式**
各数据模块各自实现并注册，ContextBuilder 只依赖抽象接口。新增数据模块只需新建 Provider 文件，不触碰任何现有报告代码。

## 结果

- 4 个报告类的 `_build_context()` 全部简化为一行 `build_context(report_type, date_range)` 调用
- `WeeklyReportAgent` 和 `QuarterlyReportAgent` 顺带新增了 `LearningProvider` 和 `GrowthProvider` 数据来源（原版遗漏）
- 新增数据模块接入报告系统，修改范围收缩为：1 个新文件 + 对应报告类的 `_register_providers()` 加一行
- 测试新增 19 个（16 Provider + 3 ContextBuilder），全量 135 个测试通过
