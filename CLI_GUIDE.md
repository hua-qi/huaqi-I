# Huaqi-I CLI 使用指南

> `huaqi-I` 是 Huaqi Phase 3 的交互式 CLI 工具

## 快速开始

```bash
# 进入项目目录
cd /Users/lianzimeng/workspace/huaqi

# 安装依赖
pip install -e .

# 查看帮助
huaqi-I --help
```

## Phase 3 CLI 命令

### 🎭 个性引擎 (personality)

```bash
# 查看当前个性配置
huaqi-I personality show

# 应用预设 (companion/mentor/friend/assistant)
huaqi-I personality preset companion
huaqi-I personality preset mentor

# 设置个性参数
huaqi-I personality set tone warm
huaqi-I personality set empathy 0.9
huaqi-I personality set humor 0.5

# 查看所有预设
huaqi-I personality presets

# 查看生成的系统提示词
huaqi-I personality prompt

# 交互式配置向导
huaqi-I personality wizard
```

### ⚡ Hook 系统 (hooks)

```bash
# 列出所有 Hooks
huaqi-I hooks list
huaqi-I hooks list --enabled

# 查看 Hook 详情
huaqi-I hooks show morning-greeting

# 启用/禁用 Hook
huaqi-I hooks enable morning-greeting
huaqi-I hooks disable daily-summary

# 手动触发 Hook
huaqi-I hooks trigger morning-greeting

# 创建新 Hook
huaqi-I hooks create --name "我的提醒" --trigger schedule

# 删除 Hook
huaqi-I hooks delete my-hook-id

# 测试事件触发
huaqi-I hooks test memory_created

# 启动调度器
huaqi-I hooks scheduler start --interval 60
```

### 📈 成长系统 (growth)

```bash
# 查看成长概览
huaqi-I growth status

# ===== 技能管理 =====
# 列出所有技能
huaqi-I growth skills
huaqi-I growth skills --category coding

# 添加技能
huaqi-I growth skill-add Python --category coding --current 入门 --target 熟练

# 记录练习
huaqi-I growth skill-log Python --hours 2.5 --notes "完成了 CLI 开发"

# 查看技能详情
huaqi-I growth skill-show Python

# ===== 目标管理 =====
# 列出目标
huaqi-I growth goals
huaqi-I growth goals --status active

# 添加目标
huaqi-I growth goal-add "掌握 Python" --category short_term

# 更新进度
huaqi-I growth goal-progress goal_xxx 75

# 完成目标
huaqi-I growth goal-complete goal_xxx

# ===== 报告 =====
# 生成周报
huaqi-I growth report weekly

# 生成洞察 (需要 LLM)
huaqi-I growth insights
```

### 💬 对话 (chat)

```bash
# 开始对话 (使用 Phase 3 特性)
huaqi-I chat

# 快速问答
huaqi-I chat --quick "讲个笑话"

# 使用旧版本（不使用 Phase 3）
huaqi-I chat --legacy

# 在对话中可用命令:
#   exit/quit - 退出
#   clear     - 清除上下文
#   status    - 查看状态（包括 Phase 3 信息）
#   /personality - 查看当前个性
#   /growth   - 查看成长摘要
```

## 完整工作流示例

```bash
# 1. 初始化配置
huaqi-I config init
huaqi-I auth create-local --email user@example.com --username demo

# 2. 配置个性
huaqi-I personality preset companion
huaqi-I personality set empathy 0.9
huaqi-I personality set humor 0.3

# 3. 添加技能和目标
huaqi-I growth skill-add Python --category coding
huaqi-I growth goal-add "完成 Huaqi Phase 3" --category short_term

# 4. 查看 Hook 状态
huaqi-I hooks list

# 5. 开始对话（会自动触发 Phase 3 特性）
huaqi-I chat

# 6. 记录学习进展
huaqi-I growth skill-log Python --hours 3 --notes "完成了 CLI 集成"
huaqi-I growth goal-progress goal_xxx 100
huaqi-I growth goal-complete goal_xxx

# 7. 生成周报
huaqi-I growth report weekly
```

## 数据存储

所有数据存储在 `~/.huaqi/users_data/{user_id}/`：

```
~/.huaqi/
├── users_data/
│   └── {user_id}/
│       ├── config/
│       │   └── personality.yaml    # 个性配置
│       ├── hooks/
│       │   ├── morning-greeting.json
│       │   ├── daily-summary.json
│       │   └── memory-insight.json
│       ├── growth/
│       │   ├── skills.yaml         # 技能追踪
│       │   └── goals.yaml          # 目标管理
│       └── memory/
│           ├── conversations/      # 对话历史
│           └── ...
```

## 其他命令

```bash
# 系统状态
huaqi-I status
huaqi-I version

# 配置管理
huaqi-I config show
huaqi-I config get llm_default_provider
huaqi-I config set llm_default_provider claude

# 记忆管理
huaqi-I memory init
huaqi-I memory search "Python"
huaqi-I memory status

# 同步
huaqi-I sync status
huaqi-I sync push
huaqi-I sync pull
```

## 创建快捷方式

```bash
# 添加到 ~/.bashrc 或 ~/.zshrc
alias huaqi-I="/usr/bin/python3 -m huaqi.interface.cli.main"

# 或创建脚本
ln -s /usr/bin/python3 /usr/local/bin/huaqi-I
echo 'exec /usr/bin/python3 -m huaqi.interface.cli.main "$@"' > /usr/local/bin/huaqi-I
chmod +x /usr/local/bin/huaqi-I
```
