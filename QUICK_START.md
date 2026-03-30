# Huaqi 快速开始指南

> 个人 AI 同伴系统 - 不是使用 AI，而是养育 AI

## 安装

```bash
cd /Users/lianzimeng/workspace/huaqi-growing
pip install -e .
```

## 启动对话

```bash
# 首次运行：自动引导设置数据目录
huaqi
```

或

```bash
python cli.py
```

## 基本交互

### 对话输入

- **Ctrl+O** - 换行（多行输入）
- **Enter** - 提交

### 退出对话

输入 `exit`、`quit` 或 `退出`

## 斜杠命令

| 命令 | 功能 |
|------|------|
| `/skill <名称>` | 添加技能 |
| `/log <技能> <小时>` | 记录练习时间 |
| `/goal <标题>` | 添加目标 |
| `/skills` | 查看技能列表 |
| `/goals` | 查看目标列表 |
| `/status` | 查看详细状态 |
| `/help` | 显示帮助 |

### 日记管理

| 命令 | 功能 |
|------|------|
| `/diary` | 写今天的日记 |
| `/diary list` | 查看日记列表 |
| `/diary search <关键词>` | 搜索日记 |
| `/diary import <路径>` | 从 Markdown 导入日记 |

### 历史对话

| 命令 | 功能 |
|------|------|
| `/history` | 查看最近对话 |
| `/history list` | 查看历史对话列表 |
| `/history search <关键词>` | 搜索历史对话 |

## 数据存储

所有数据存储在 `/Users/lianzimeng/workspace/huaqi/memory/`：

```
memory/
├── config.yaml           # 全局配置
├── personality.yaml      # 用户画像
├── growth.yaml           # 技能与目标
├── diary/                # 日记
│   └── YYYY-MM/
│       └── YYYY-MM-DD.md
└── conversations/        # 对话历史
    └── YYYY/MM/
        └── YYYYMMDD_HHMMSS_*.md
```

## AI 如何了解你

Huaqi 会根据以下信息回答你的问题：

1. **用户画像** - 性格、沟通风格、共情水平
2. **技能列表** - 你正在学习的技能
3. **目标追踪** - 你的短期和长期目标
4. **日记内容** - 最近7天的日记
5. **对话历史** - 当前会话的上下文

## 示例工作流

```bash
# 1. 启动 huaqi
huaqi

# 2. 添加技能
> /skill Python

# 3. 记录练习
> /log Python 2.5

# 4. 写日记
> /diary
情绪: 充实
标签: 学习 编程
内容: 今天完成了 CLI 开发，感觉很有成就感

# 5. 查看状态
> /status

# 6. 退出
> exit
```

## 配置 LLM

```bash
huaqi config set llm
```

按提示输入：
- 提供商 (openai/claude/deepseek)
- API Key
- 模型名称

## 更新日志

- **v0.2.0** - 添加日记系统、对话历史保存
- **v0.1.0** - 基础对话、技能追踪、目标管理
