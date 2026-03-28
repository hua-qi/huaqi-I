# Huaqi - 个人 AI 同伴系统

> 不是使用 AI，而是养育 AI —— 让它越来越像你，越来越懂你

**Huaqi (花旗)** 是一个个人 AI 同伴系统，定位为用户的数字伙伴而非工具。它通过长期对话积累对用户的理解，主动关心用户成长，成为真正懂你的 AI 同伴。

## 核心特性

| 特性 | 描述 |
|------|------|
| 💬 **智能对话** | 基于你的日记、技能、目标提供个性化回答 |
| 📝 **日记系统** | Markdown 格式，支持批量导入，AI 自动分析洞察 |
| 🎯 **技能追踪** | 记录练习时间，追踪成长进度 |
| 🎖️ **目标管理** | 设定短期/长期目标，可视化进展 |
| 🔗 **内容流水线** | 自动抓取 X/Twitter、RSS，生成小红书内容 |
| ⏰ **定时任务** | APScheduler 支持定时 Hook、周期性任务 |
| 🔒 **隐私优先** | 所有数据本地存储，用户完全可控 |

## 快速开始

```bash
# 安装
pip install -e .

# 启动
huaqi

# 配置 LLM
huaqi config set-llm
```

详见 [QUICK_START.md](QUICK_START.md)

## 常用命令

```bash
# 对话
huaqi chat                    # 开始对话

# 日记
huaqi diary                   # 写日记
huaqi diary list              # 查看日记
huaqi diary import <path>     # 导入 Markdown 日记

# 技能与目标
huaqi skill add "Python"      # 添加技能
huaqi skill log Python 2.5    # 记录练习时间
huaqi goal add "学习 LangGraph"  # 添加目标

# 内容流水线
huaqi pipeline add-source     # 添加内容源
huaqi pipeline fetch          # 手动抓取内容

# 配置
huaqi config set-data-dir <path>  # 设置数据目录
huaqi config migrate          # 数据迁移
```

详见 [docs/guides/cli-guide.md](docs/guides/cli-guide.md)

## 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        交互层 (CLI)                              │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                 编排层 (LangGraph Agent)                         │
│      ┌─────────┬─────────┬─────────┬─────────┐                  │
│      │  记忆   │  技能   │  日记   │ 流水线  │                  │
│      └─────────┴─────────┴─────────┴─────────┘                  │
└─────────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    基础设施层 (本地存储)                          │
│         Markdown · BM25 搜索 · Chroma 向量 · APScheduler         │
└─────────────────────────────────────────────────────────────────┘
```

详见 [docs/design/ARCHITECTURE.md](docs/design/ARCHITECTURE.md) 和 [docs/design/TECH_SPEC.md](docs/design/TECH_SPEC.md)

## 项目结构

```
huaqi-growing/
├── huaqi_src/           # 源码
│   ├── agent/           # LangGraph Agent 工作流
│   ├── core/            # 核心模块（配置、个性、LLM）
│   ├── memory/          # 记忆系统
│   ├── pipeline/        # 内容流水线
│   └── scheduler/       # 定时任务
├── cli.py               # CLI 入口
├── docs/                # 详细文档
│   ├── DOC_GUIDELINES.md  # 文档规范
│   ├── design/          # 产品与技术设计
│   ├── features/        # 功能模块文档
│   ├── guides/          # 用户与开发者指南
│   └── ops/             # 运维与工程
└── tests/               # 测试
```

## 数据存储

默认存储在 `~/.huaqi/`，可自定义：

```
~/.huaqi/
├── memory/
│   ├── diary/           # 日记
│   ├── conversations/   # 对话历史
│   ├── personality.yaml # 用户画像
│   └── growth.yaml      # 技能与目标
├── drafts/              # 内容草稿
├── config.yaml          # 配置
└── vector_db/           # 向量数据库
```

## 路线图

| Phase | 功能 | 状态 |
|-------|------|------|
| P1 | 基础对话系统 | ✅ |
| P2 | 记忆系统 (日记 + 对话历史) | ✅ |
| P3 | 技能追踪与目标管理 | ✅ |
| P4 | APScheduler 定时任务 | ✅ |
| P5 | 内容流水线 (X/RSS → 小红书) | ✅ |
| P6 | 人机协同中断恢复 | ✅ |
| P7 | 数据隔离与用户管理 | ✅ |
| P8 | 配置热重载与数据迁移 | ✅ |

详见 [spec/roadmap/ROADMAP.md](spec/roadmap/ROADMAP.md)

## 文档索引

| 文档 | 说明 |
|------|------|
| [QUICK_START.md](QUICK_START.md) | 5分钟快速上手 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |
| [docs/guides/cli-guide.md](docs/guides/cli-guide.md) | 完整命令参考 |
| [docs/design/ARCHITECTURE.md](docs/design/ARCHITECTURE.md) | 系统架构 |
| [docs/design/TECH_SPEC.md](docs/design/TECH_SPEC.md) | 详细技术规范 |
| [docs/design/PRD.md](docs/design/PRD.md) | 产品需求文档 |
| [docs/ops/test-plan.md](docs/ops/test-plan.md) | 测试计划 |
| [docs/ops/implementation-plan.md](docs/ops/implementation-plan.md) | 实施计划 |
| [spec/roadmap/ROADMAP.md](spec/roadmap/ROADMAP.md) | 开发路线图 |
| [docs/DOC_GUIDELINES.md](docs/DOC_GUIDELINES.md) | 文档编写规范 |

## License

MIT License

---

*文档版本: v0.2.0*  
*最后更新: 2026-03-27*
