# 定时任务迁移至 GitHub Actions

> **Spec:** `docs/specs/2026-05-14-reports-github-actions.md`
> **Plan:** `docs/plans/2026-05-14-reports-github-actions.md`
> **日期:** 2026-05-14

## 概述

将 6 个定时任务从本地 APScheduler 迁移至 GitHub Actions cron 调度，解决 macOS 上没有常驻 daemon 导致报告无法如期执行的问题。

## 设计决策

### 调度平台：GitHub Actions

- 数据目录已是 git 仓库，天然集成
- 免费额度充足（6 个任务 ~60 分钟/月，远低于 2000 分钟限制）
- 不依赖本机开机状态
- 失败自动通知（Server酱 + GitHub 原生）

### 执行路径

- **4 个报告任务**（晨间/日报/周报/季报）：走 `huaqi report <type>` 专用 ReportAgent 路径
- **2 个功能任务**（学习推送/世界新闻）：走 `huaqi scheduler run <id>` 通用路径
- 保留 APScheduler 代码作为本地调试备选

### 通知：Server酱

- 成功时推送报告摘要
- 失败时推送告警 + GitHub Actions 运行链接
- 通过 `SERVERCHAN_KEY` Secret 配置

## 部署方式

1. 将 `scripts/github-actions/` 下所有文件复制到数据仓库的 `.github/workflows/`
2. 在数据仓库配置 GitHub Secrets（`OPENAI_API_KEY`、`SERVERCHAN_KEY`）
3. 手动触发一次 workflow 验证

## 后续新增定时任务

遵循 GitHub Actions 模式：
1. 在 `scripts/github-actions/` 创建 `<task-name>.yml`
2. 参考已有 workflow 模板填写 cron、命令、输出路径
3. 复制到数据仓库 `.github/workflows/`

## 文件清单

```
scripts/github-actions/
├── morning-brief.yml      # 晨间简报 08:00
├── daily-report.yml       # 日终复盘 23:00
├── weekly-report.yml      # 周报 周日 21:00
├── quarterly-report.yml   # 季报 季度末 22:00（含日期判断）
├── learning-push.yml      # 学习推送 21:00
├── world-fetch.yml        # 世界新闻采集 07:00
├── notify.sh              # Server酱 通知脚本
└── SECRETS.md             # Secrets 配置说明
```

## 测试覆盖

- 单元测试：`tests/unit/test_github_actions_workflows.py`（7 用例）
- 单元测试：`tests/unit/test_headless_report_commands.py`（5 用例）
- 冒烟测试：`tests/smoke_test.py::TestGitHubActionsWorkflows`（7 用例）
