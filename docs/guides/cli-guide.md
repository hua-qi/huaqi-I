# CLI 命令参考

> 当前版本命令参考。所有命令均以 `huaqi` 开头。

## 前置：首次配置

首次运行 `huaqi` 时，若未设置数据目录，系统会自动进入引导向导：

```bash
huaqi
# 自动提示设置数据目录，引导完成后进入对话
```

之后可通过以下命令修改数据目录：

```bash
huaqi config set data_dir
```

---

## 对话

```bash
huaqi                            # 启动 LangGraph Agent 对话（默认）
huaqi chat                       # 同上
huaqi chat --legacy               # 使用传统对话模式
huaqi chat -l                     # 列出最近 10 条历史会话
huaqi chat -s <thread_id>         # 恢复指定会话（thread_id 从 -l 列表获取）
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
| `/history` | 最近对话记录（传统模式）|
| `/history list` | 对话列表（传统模式）|
| `/history search <词>` | 搜索历史对话（传统模式）|
| `/reset` | 新建会话（LangGraph 模式）|
| `/state` | 查看当前会话 ID 和轮数（LangGraph 模式）|
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
huaqi config show                  # 查看所有配置项

# 通用设置
huaqi config set <KEY>             # 设置配置项（使用交互向导输入值）
huaqi config set <KEY> <VALUE>     # 单行直接设置配置项（如：huaqi config set modules.wechat true）

# 常用配置 KEY
huaqi config set llm               # 配置 LLM（交互向导）
huaqi config set git               # 配置 Git 远程同步（交互向导）
huaqi config set data_dir          # 修改数据目录（支持数据迁移）
```

**`config show` 展示的 KEY 一览：**

| KEY | 说明 |
|-----|------|
| `data_dir` | 数据目录 |
| `llm_default_provider` | 默认 LLM 提供商 |
| `llm_providers.<name>.model` | 模型名称 |
| `llm_providers.<name>.api_key` | API 密钥（自动掩码） |
| `llm_providers.<name>.api_base` | API 地址 |
| `memory.max_session_memory` | 最大会话记忆条数 |
| `modules.network_proxy` | 网络请求采集模块开启状态（`true`/`false`） |
| `modules.wechat` | 微信聊天记录采集模块开启状态（`true`/`false`） |
| `git.remote_url` | Git 远程地址 |
| `git.branch` | Git 分支 |
| `git.auto_push` | 自动推送开关 |

---

## 用户画像 `profile`

```bash
huaqi profile show                 # 查看画像（AI 叙事 + 结构化字段）

# 设置结构化字段
huaqi profile set name 子蒙
huaqi profile set occupation 工程师
huaqi profile set location 北京
huaqi profile set skills "Python,LangChain"
huaqi profile set hobbies "阅读,写作"
```

**可用字段：**

| 类型 | 字段名 |
|------|--------|
| 身份 | `name` `nickname` `birth_date` `location` `occupation` `company` |
| 背景（列表） | `skills` `hobbies` `life_goals` `values` |

---

## 人格画像 `personality`

```bash
huaqi personality show             # 查看当前 AI 人格配置（Big Five + 沟通风格）
huaqi personality update           # 主动触发日记分析，生成画像更新提案
huaqi personality review           # 审核或查看更新提案列表
huaqi personality review <id> -a   # 批准更新提案
huaqi personality review <id> -r   # 拒绝更新提案
```

> 人格画像由系统基于日记和对话自动演化，不支持手动全量覆盖。

---

## 人机协同与任务恢复 `resume`

```bash
huaqi resume <task_id>             # 恢复被中断的 LangGraph 任务（默认确认）
huaqi resume <task_id> reject      # 拒绝执行被中断的任务
```

当任务需要人工介入（如发布确认、关键画像更改）时，系统会生成中断任务 ID。

---

## 内容流水线 `pipeline`

```bash
huaqi pipeline show                # 查看流水线状态（草稿数量、待审核任务数）

huaqi pipeline run                 # 执行流水线（采集 → 处理 → 草稿）
huaqi pipeline run --dry-run       # 预览模式，不写入
huaqi pipeline run --limit 10      # 每源采集 10 条（默认 5）
huaqi pipeline run --source x      # 仅抓取 X/Twitter
huaqi pipeline run --source rss    # 仅抓取 RSS

huaqi pipeline drafts              # 查看草稿列表
huaqi pipeline drafts --limit 20

huaqi pipeline review              # 列出待审核任务
huaqi pipeline review <task-id>    # 查看任务详情
huaqi pipeline review <task-id> --approve 0   # 通过第 0 项
huaqi pipeline review <task-id> --reject 1    # 拒绝第 1 项
huaqi pipeline review <task-id> --publish     # 发布已审核内容
```

---

## 后台任务 `daemon`

```bash
huaqi daemon start                 # 后台启动定时任务
huaqi daemon start --foreground    # 前台运行（Ctrl+C 停止）
huaqi daemon stop                  # 停止
huaqi daemon status                # 查看运行状态和任务列表
huaqi daemon list                  # 列出所有注册任务
```

---

## 系统管理 `system`

```bash
huaqi system show                  # 查看系统状态（数据目录、记忆文件数、Git 状态）

huaqi system migrate               # 执行数据迁移 v3→v4
huaqi system migrate --dry-run     # 预览迁移内容
huaqi system migrate --skip-backup # 跳过备份（不推荐）

huaqi system hot-reload status     # 配置热重载状态
huaqi system hot-reload start      # 启动热重载
huaqi system hot-reload stop       # 停止热重载

huaqi system backup                # 创建 memory/ 备份快照
```

---

## 完整工作流示例

```bash
# 1. 首次运行，自动引导设置数据目录
huaqi

# 2. 配置 LLM
huaqi config set llm

# 3. 设置用户信息
huaqi profile set name 子蒙
huaqi profile set occupation 工程师
huaqi profile set skills "Python,LangChain,LangGraph"

# 4. 开始对话（内置日记、技能、目标管理）
huaqi chat
# 在对话中：
#   /diary       写今日日记
#   /skill Python 添加技能
#   /goal "完成项目重构" 设定目标

# 5. 查看本周报告
# 在对话中：/report

# 6. 查看配置
huaqi config show

# 7. 运行内容流水线
huaqi pipeline show                # 先查看状态
huaqi pipeline run --dry-run       # 预览
huaqi pipeline run                 # 正式运行
huaqi pipeline review              # 审核草稿
```
