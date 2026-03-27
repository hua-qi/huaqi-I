# Huaqi - 个人 AI 同伴系统 (简化版)

> 一个 Git 友好的 AI 同伴系统，所有配置和记忆存储在一起，随时可迁移到新设备。

## 设计理念

**数据即代码**：所有配置（个性、Hooks、技能、目标）与记忆存储在同一个目录，方便：
- ✅ Git 版本管理
- ✅ 跨设备同步（GitHub/GitLab/自建仓库）
- ✅ 随时导出导入
- ✅ 数据完全可控

## 目录结构

```
~/.huaqi/                    # 数据目录（可自定义）
└── memory/                  # 所有数据和配置
    ├── config.yaml          # 应用配置（LLM 等）
    ├── personality.yaml     # AI 个性档案
    ├── hooks.yaml           # Hook 定义
    ├── growth.yaml          # 技能和目标
    ├── identity/            # 身份记忆
    ├── patterns/            # 模式洞察
    ├── conversations/       # 对话历史
    └── imports/             # 导入的文档
```

## 快速开始

```bash
# 进入项目目录
cd /Users/lianzimeng/workspace/huaqi

# 运行 CLI（单用户版）
/usr/bin/python3 -m huaqi.cli_simple status

# 或使用自定义数据目录
/usr/bin/python3 -m huaqi.cli_simple --data-dir ~/Documents/my-huaqi status
```

## 使用方式

```bash
# 查看状态
/usr/bin/python3 -m huaqi.cli_simple status

# 个性引擎
/usr/bin/python3 -m huaqi.cli_simple personality show
/usr/bin/python3 -m huaqi.cli_simple personality set empathy 0.9
/usr/bin/python3 -m huaqi.cli_simple personality preset mentor

# Hook 系统
/usr/bin/python3 -m huaqi.cli_simple hooks list
/usr/bin/python3 -m huaqi.cli_simple hooks enable morning-greeting

# 成长系统
/usr/bin/python3 -m huaqi.cli_simple growth skills
/usr/bin/python3 -m huaqi.cli_simple growth skill-add Python --category coding
/usr/bin/python3 -m huaqi.cli_simple growth skill-log Python --hours 2.5
/usr/bin/python3 -m huaqi.cli_simple growth goals
/usr/bin/python3 -m huaqi.cli_simple growth goal-add "完成项目"
```

## Git 同步

```bash
# 初始化 Git 仓库
cd ~/.huaqi/memory
git init
git add .
git commit -m "Initial commit"

# 推送到远程（GitHub/GitLab）
git remote add origin https://github.com/username/huaqi-data.git
git push -u origin main

# 在新设备上同步
git clone https://github.com/username/huaqi-data.git ~/.huaqi/memory
```

## 数据迁移

```bash
# 导出数据
cp -r ~/.huaqi/memory ~/backup/huaqi-$(date +%Y%m%d)

# 或打包
tar czf huaqi-backup.tar.gz -C ~/.huaqi memory

# 在新设备导入
tar xzf huaqi-backup.tar.gz -C ~/.huaqi
```

## 配置说明

### 个性配置 (personality.yaml)
```yaml
name: Huaqi
role: 同伴
tone: warm
empathy: 0.8
humor: 0.3
values:
  - 成长优于稳定
  - 真诚优于讨好
```

### Hook 配置 (hooks.yaml)
```yaml
hooks:
  - id: morning-greeting
    name: 晨间问候
    trigger_type: schedule
    trigger_config:
      type: daily
      time: "09:00"
    actions:
      - type: send_message
        params:
          message: "早安！"
```

### 成长配置 (growth.yaml)
```yaml
skills:
  Python:
    name: Python
    category: coding
    current_level: 进阶
    target_level: 精通
    total_hours: 100.5

goals:
  goal_20240325120000:
    id: goal_20240325120000
    title: 完成 Huaqi 项目
    progress: 75
    status: active
```

## 特点

| 特性 | 说明 |
|------|------|
| **单用户** | 无需登录，开箱即用 |
| **Git 友好** | 所有配置 YAML 格式，易于版本管理 |
| **便携** | 随时打包带走，换设备无缝迁移 |
| **简洁** | 移除复杂用户体系，专注核心功能 |

## 技术栈

- Python 3.9+
- Typer (CLI)
- Rich (终端美化)
- PyYAML (数据存储)

## 许可证

MIT
