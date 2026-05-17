# Spec: 定时任务迁移至 GitHub Actions

> **生成 Spec 唯一入口为 `docs/specs/`。Spec 是功能的顶层设计，只描述 WHAT 和 WHY，不描述 HOW。**

## 1. 要解决的问题

定时报告依赖本机常驻进程（APScheduler daemon），需要用户手动启动、保持终端不关、无法在电脑关机时执行。macOS 上没有 systemd，daemon 稳定性差（已知 21 个 bug），导致报告经常不能如期生成。用户需要一种不依赖本机开机状态的、可靠的定时执行方案。

## 2. 功能范围

**包含：**
- 将全部 6 个定时任务迁移到 GitHub Actions cron 调度
- 任务执行完成后通过 Server酱 推送微信通知（含报告摘要）
- 任务执行失败时通过 Server酱 推送告警通知（含失败原因）
- 生成的报告文件自动 commit + push 回数据仓库
- 可通过 GitHub Actions 运行历史查看每次执行状态和日志
- 后续新增定时任务也遵循 GitHub Actions 模式（决策落地到架构文档）

**不包含：**
- 修改或删除现有 APScheduler 代码（保留向后兼容，用户仍可本地运行）
- 修改报告 Agent 的业务逻辑
- GitHub Actions 之外的云平台（VPS、GitLab CI 等）
- 数据目录的 git 仓库初始化（用户已有）

## 3. 技术选型

| 决策点 | 选择 | 原因 |
|--------|------|------|
| 调度平台 | GitHub Actions | 数据目录已是 git 仓库，天然集成；免费额度充足 |
| 通知渠道 | Server酱 | 微信推送，一个 webhook URL，最轻量 |
| 执行方式 | CLI 命令（`huaqi report` 等） | 走专用 ReportAgent 路径，不走有 bug 的 ChatAgent 通用路径 |

## 4. 验收标准

每条 AC 必须**可验证**——agent 能直接翻译为测试函数。

- [x] AC-1: 6 个 GitHub Actions workflow 文件存在且 schema 合法 → `test_all_workflows_exist`
- [x] AC-2: 每个 workflow 在无交互环境下可执行对应的 CLI 命令 → `test_headless_cli_commands`
- [x] AC-3: workflow 中 git commit + push 步骤正确引用生成的文件路径 → `test_workflow_output_paths`
- [x] AC-4: Server酱 通知步骤正确构造 webhook URL 和消息体 → `test_serverchan_notification_config`
- [x] AC-5: GitHub Secrets 清单文档完备，用户可按文档完成配置 → `test_secrets_documentation`
- [x] AC-6: 架构文档明确标注「新增定时任务使用 GitHub Actions」的决策 → `test_arch_doc_decision`
- [x] AC-7: 失败时 Server酱 推送告警通知，包含任务名和失败原因 → `test_failure_notification`
- [x] AC-8: GitHub Actions workflow 中 `workflow_dispatch` 支持手动触发，便于调试 → `test_manual_trigger`
- [x] AC-9: 季报 workflow 在非季度末日期自动跳过，仅季度最后一天实际执行 → `test_quarterly_conditional`
- [x] AC-10: 每个 workflow 在 push 前先 pull --rebase，处理并发冲突 → `test_git_pull_before_push`
- [x] AC-11: CI 日志中不打印 Secret 值（Server酱 key、API key）→ `test_no_secret_leakage`

## 5. 依赖

- **依赖**：`huaqi report` CLI 命令（晨间/日报/周报/季报）、`huaqi scheduler run` 命令（学习推送/世界新闻采集）
- **依赖**：用户数据目录已有 git remote（用户已确认）
- **被依赖**：后续新增定时任务遵循本 Spec 的 workflow 模式

## 6. 风险与假设

- **假设**：用户数据目录的 git remote 指向 GitHub 私有仓库
- **假设**：`huaqi report` 系列命令可在无 TTY 的 CI 环境中正常运行
- **假设**：GitHub Actions 的 cron 时区为 UTC，需要换算（北京时间 8:00 = UTC 0:00）
- **风险**：GitHub Actions cron 在私有仓库有 2000 分钟/月限制，6 个任务预计使用 ~60 分钟/月，远低于上限
- **风险**：GitHub Actions cron 不保证精确准点，实际执行可能延迟 5-15 分钟
- **风险**：用户本机与 GitHub Actions 并发操作同一 git 仓库可能导致 push 冲突，需 pull --rebase 策略
- **风险**：季报 cron（每月 28-31 号触发）需在 workflow 内判断是否为季度最后一天，非最后一天自动跳过
- **安全**：Server酱 webhook URL 含 key，CI 日志中需屏蔽；报告内容含个人隐私，不应输出到日志
- **安全**：GitHub Actions 需 `contents: write` 权限才能 push，需在 workflow 中显式声明
- **安全**：pip install 应使用项目的依赖声明（setup.py/pyproject.toml），不额外安装未审计的包
