# CLI 命令参考

> 当前版本命令参考。所有命令均以 `huaqi` 开头，需先通过 `--data-dir` 或环境变量指定数据目录。

## 前置：配置数据目录

每次调用必须指定数据目录（或已保存过一次）：

```bash
# 方式一：命令行参数（首次推荐）
huaqi --data-dir ~/my-huaqi <command>

# 方式二：环境变量
export HUAQI_DATA_DIR=~/my-huaqi
huaqi <command>
```

---

## 对话

```bash
huaqi chat                       # 启动 LangGraph Agent 对话（默认）
huaqi chat --legacy               # 使用传统对话模式
huaqi status                      # 查看系统状态（技能、目标、人格）
```

### 对话中的斜杠命令

进入 `huaqi chat` 后，可在输入框中使用以下命令：

| 命令 | 说明 |
|------|------|
| `/help` | 显示帮助 |
| `/status` | 查看详细状态 |
| `/clear` | 清屏 |
| `/skill <名称>` | 添加技能 |
| `/log <技能> <小时>` | 记录练习时间 |
| `/goal <标题>` | 设定目标 |
| `/diary` | 写今日日记 |
| `/diary list` | 查看日记列表 |
| `/diary search <词>` | 搜索日记 |
| `/diary import <路径>` | 从文件/目录导入日记 |
| `/skills` | 查看技能列表 |
| `/goals` | 查看目标列表 |
| `/report` | 查看本周报告 |
| `/report insights` | 查看模式洞察 |
| `/care` | 手动触发关怀检查 |
| `/care status` | 查看关怀统计 |
| `/history` | 最近对话记录 |
| `/history list` | 对话列表 |
| `/history search <词>` | 搜索历史对话 |
| `exit` / `quit` | 退出对话 |

### 快捷键

| 快捷键 | 功能 |
|--------|------|
| `↑` / `↓` | 历史记录 |
| `Tab` | 自动补全（命令 + 历史词组） |
| `Ctrl+R` | 搜索历史 |
| `Ctrl+L` | 清屏 |
| `Ctrl+O` 或 `Esc+Enter` | 插入换行（多行输入） |
| `Enter` | 提交 |
| `Ctrl+C` | 取消当前输入 |

---

## 配置管理 `config`

```bash
huaqi config show                              # 查看当前配置
huaqi config get <key>                         # 获取配置项
huaqi config set <key> <value>                 # 设置配置项

# 配置 LLM
huaqi config set-llm openai \
  --api-key sk-xxx \
  --api-base https://api.openai.com/v1 \
  --model gpt-4o

# 配置其他提供商
huaqi config set-llm deepseek --api-key sk-xxx
huaqi config set-llm claude --api-key sk-xxx

# 修改数据目录（支持数据迁移）
huaqi config set-data-dir ~/new-huaqi
huaqi config set-data-dir ~/new-huaqi --no-migrate  # 不迁移数据
```

---

## 用户画像 `profile`

```bash
huaqi profile show                             # 查看画像（AI 叙事 + 结构化字段）
huaqi profile refresh                          # 立即重新生成 AI 叙事画像（调用 LLM）

# 设置结构化字段
huaqi profile set name 子蒙
huaqi profile set occupation 工程师
huaqi profile set location 北京
huaqi profile set skills "Python,LangChain"
huaqi profile set hobbies "阅读,写作"

# 删除字段
huaqi profile forget name
huaqi profile forget skills                    # 清空技能列表
```

**可用字段：**

| 类型 | 字段名 |
|------|--------|
| 身份 | `name` `nickname` `birth_date` `location` `occupation` `company` |
| 背景（列表） | `skills` `hobbies` `life_goals` `values` |

---

## 人格画像 `personality`

```bash
huaqi personality show                         # 查看当前 AI 人格配置
huaqi personality update                       # 分析近 7 天日记，生成更新提案
huaqi personality update --days 14             # 分析近 14 天

huaqi personality review                       # 列出待审核提案
huaqi personality review <id>                  # 查看提案详情
huaqi personality review <id> --approve        # 批准并应用
huaqi personality review <id> --reject         # 拒绝
huaqi personality review <id> --approve --notes "手动确认"
```

---

## 内容流水线 `pipeline`

```bash
huaqi pipeline run                             # 执行流水线（采集 → 处理 → 草稿）
huaqi pipeline run --dry-run                   # 预览模式，不写入
huaqi pipeline run --limit 10                  # 每源采集 10 条（默认 5）
huaqi pipeline run --source x                  # 仅抓取 X/Twitter
huaqi pipeline run --source rss                # 仅抓取 RSS

huaqi pipeline drafts                          # 查看草稿列表
huaqi pipeline drafts --limit 20

huaqi pipeline review                          # 列出待审核任务
huaqi pipeline review <task-id>                # 查看任务详情
huaqi pipeline review <task-id> --approve 0   # 通过第 0 项
huaqi pipeline review <task-id> --reject 1    # 拒绝第 1 项
huaqi pipeline review <task-id> --publish      # 发布已审核内容
```

---

## 后台任务 `daemon`

```bash
huaqi daemon start                             # 后台启动定时任务
huaqi daemon start --foreground               # 前台运行（Ctrl+C 停止）
huaqi daemon stop                              # 停止
huaqi daemon status                            # 查看运行状态和任务列表
huaqi daemon list                              # 列出所有注册任务
```

---

## 系统管理 `system`

```bash
huaqi system migrate                           # 执行数据迁移 v3→v4
huaqi system migrate --dry-run                 # 预览迁移内容
huaqi system migrate --skip-backup             # 跳过备份（不推荐）

huaqi system hot-reload status                 # 配置热重载状态
huaqi system hot-reload start                  # 启动热重载
huaqi system hot-reload stop                   # 停止热重载

huaqi system backup                            # 创建 memory/ 备份快照
```

---

## 完整工作流示例

```bash
# 1. 首次配置
huaqi --data-dir ~/huaqi config set-llm openai \
  --api-key $OPENAI_API_KEY \
  --api-base https://api.openai.com/v1

# 2. 设置用户信息
huaqi profile set name 子蒙
huaqi profile set occupation 工程师
huaqi profile set skills "Python,LangChain,LangGraph"

# 3. 开始对话（内置日记、技能、目标管理）
huaqi chat
# 在对话中：
#   /diary       写今日日记
#   /skill Python 添加技能
#   /goal "完成项目重构" 设定目标

# 4. 查看本周报告
# 在对话中：/report

# 5. 生成 AI 画像
huaqi profile refresh

# 6. 运行内容流水线
huaqi pipeline run --dry-run   # 先预览
huaqi pipeline run             # 正式运行
huaqi pipeline review          # 审核草稿
```
