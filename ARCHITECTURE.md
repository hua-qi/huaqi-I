# Huaqi 系统架构

> **Huaqi (花旗)** - 个人 AI 同伴系统架构文档

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           用户接口层 (Interface)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                    │
│  │  CLI (Typer) │  │  Web (待定)  │  │  API (待定)  │                    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                    │
└─────────┼─────────────────┼─────────────────┼───────────────────────────┘
          │                 │                 │
          └─────────────────┼─────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────────┐
│                          编排层 (Orchestration)                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │              ConversationManager (对话管理器)                      │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐            │   │
│  │  │ Personality│ │  Hooks   │ │ Growth   │ │ Memory   │            │   │
│  │  │  Engine  │ │  System  │ │ Tracker  │ │ Manager  │            │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────────┐
│                          核心层 (Core)                                   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │   Auth   │ │ Config   │ │   LLM    │ │  Memory  │ │   Sync   │      │
│  │  (认证)  │ │ (配置)   │ │ (模型)   │ │ (记忆)   │ │ (同步)   │      │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘      │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────────┐
│                         基础设施层 (Infrastructure)                       │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │  File Store  │ │   BM25       │ │  Embeddings  │ │    Git       │   │
│  │  (Markdown)  │ │   Search     │ │  (Optional)  │ │   Sync       │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

## 分层架构

### 1. 用户接口层 (Interface Layer)

负责与用户的交互，提供多种接入方式。

| 组件 | 技术 | 状态 | 说明 |
|------|------|------|------|
| CLI | Typer + Rich | ✅ 完成 | 命令行交互界面 |
| Web UI | (待定) | 🚧 规划 | 网页图形界面 |
| API | FastAPI (待定) | 🚧 规划 | RESTful API 接口 |

**CLI 模块结构：**
```
interface/cli/
├── main.py              # CLI 主入口
└── commands/
    ├── personality.py   # 个性引擎命令
    ├── hooks.py         # Hook 系统命令
    └── growth.py        # 成长系统命令
```

### 2. 编排层 (Orchestration Layer)

协调各核心模块，管理对话流程和状态。

#### 2.1 对话管理器 (ConversationManager)

```python
class ConversationManager:
    """
    核心编排器，负责：
    - 对话生命周期管理
    - 各子系统集成
    - 事件分发
    - 上下文维护
    """
```

**职责：**
- 会话管理（创建、维护、销毁）
- 消息编排（系统提示词组装）
- 事件触发（Hook 系统调用）
- 记忆检索与存储

#### 2.2 子系统集成

| 模块 | 文件 | 功能 |
|------|------|------|
| **个性引擎** | `core/personality.py` | AI 性格、语气、交互风格 |
| **Hook 系统** | `core/hooks.py` | 自动化工作流、事件响应 |
| **成长系统** | `core/growth.py` | 技能追踪、目标管理 |
| **记忆管理** | `memory/storage/` | 记忆存储、检索、导入 |

### 3. 核心层 (Core Layer)

提供底层业务能力。

#### 3.1 认证模块 (Auth)

```python
# core/auth.py
- UserProfile      # 用户档案
- UserManager      # 用户管理
- OAuthProviders   # OAuth 集成
```

**功能：**
- 本地用户创建
- OAuth 登录 (GitHub, Google)
- 用户隔离

#### 3.2 配置模块 (Config)

```python
# core/config.py
- ConfigManager    # 配置管理
- UserConfig       # 用户配置
- GlobalConfig     # 全局配置
```

**配置层级：**
```
全局配置 → 用户配置 → 会话配置
```

#### 3.3 LLM 模块

```python
# core/llm.py
- LLMManager       # LLM 管理器
- LLMConfig        # 模型配置
- Message          # 消息模型
```

**支持的提供商：**
| 提供商 | 状态 |
|--------|------|
| OpenAI | ✅ |
| Claude | ✅ |
| DeepSeek | ✅ |
| Dummy (测试) | ✅ |

#### 3.4 记忆模块

**存储层：**
```python
memory/storage/
├── markdown_store.py       # Markdown 存储
├── memory_manager_v2.py    # 记忆管理 V2
└── user_isolated.py        # 用户隔离
```

**搜索层：**
```python
memory/search/
├── text_search.py      # BM25 文本搜索
├── llm_search.py       # LLM 相关性搜索
└── hybrid_search.py    # 混合搜索
```

**导入层：**
```python
memory/importer/
├── markdown_importer.py  # Markdown 导入
├── pdf_importer.py       # PDF 导入
├── docx_importer.py      # Word 导入
└── batch.py              # 批量导入
```

#### 3.5 同步模块 (Sync)

```python
# core/sync.py
- UserGitSync    # Git 同步
- SyncStatus     # 同步状态
```

**功能：**
- 本地 Git 仓库管理
- 远程推送/拉取
- 冲突解决

### 4. 基础设施层 (Infrastructure Layer)

#### 4.1 存储

| 类型 | 技术 | 用途 |
|------|------|------|
| 主存储 | Markdown + YAML | 人类可读的数据存储 |
| 搜索索引 | BM25 / TF-IDF | 快速文本检索 |
| 向量存储 | Chroma (可选) | 语义检索 |

**数据目录结构：**
```
~/.huaqi/
├── users_data/
│   └── {user_id}/
│       ├── config/
│       │   └── personality.yaml
│       ├── hooks/
│       │   └── *.json
│       ├── growth/
│       │   ├── skills.yaml
│       │   └── goals.yaml
│       └── memory/
│           ├── identity/
│           ├── patterns/
│           ├── conversations/
│           └── imports/
└── global/
    └── config.yaml
```

#### 4.2 搜索架构 V2

**设计理念：** 无需 Embedding，兼容所有 LLM

```
用户查询
    │
    ├──→ [BM25 文本搜索] ──→ 候选记忆
    │                         │
    └──→ [LLM 相关性判断] ←──┘
                │
                ↓
           返回结果
```

**搜索策略：**
- `hybrid`: BM25 + LLM 排序（推荐）
- `text`: 纯 BM25
- `llm`: LLM 遍历判断

## 关键设计决策

### 1. 存储格式选择

**选择 Markdown + YAML Frontmatter**

| 优点 | 说明 |
|------|------|
| 人类可读 | 直接查看和编辑 |
| Git 友好 | 版本控制、diff 友好 |
| Obsidian 兼容 | 与知识库工具互通 |
| 无锁定 | 避免数据库锁定 |

### 2. 搜索架构演进

| 版本 | 方案 | 问题 |
|------|------|------|
| V1 | Embedding + Vector DB | 依赖 Embedding 模型 |
| **V2** | **BM25 + LLM** | **无需 Embedding，兼容所有 LLM** |

### 3. 多用户隔离

```
数据隔离策略: 目录隔离

~/.huaqi/users_data/
├── user_a/      # 用户 A 的数据
├── user_b/      # 用户 B 的数据
└── user_c/      # 用户 C 的数据
```

### 4. 模块化设计

**原则：** 高内聚、低耦合

```
core/                    # 核心逻辑
├── personality.py       # 可独立使用
├── hooks.py             # 可独立使用
├── growth.py            # 可独立使用
└── ...

interface/cli/           # 接口层
├── commands/            # 各命令独立
└── main.py              # 入口组装
```

## 数据流

### 对话流程

```
用户输入
    │
    ▼
┌─────────────────┐
│  1. 检索记忆     │ ←── 搜索相关历史记忆
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. 组装提示词   │ ←── 个性 + 记忆 + 成长摘要
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. LLM 生成     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  4. 后处理      │ ←── 提取记忆、触发 Hooks、记录成长
└────────┬────────┘
         │
         ▼
    返回响应
```

### Hook 触发流程

```
事件发生 (conversation_started/memory_created/...)
    │
    ▼
┌─────────────────┐
│  1. 匹配 Hooks   │ ←── 查找订阅该事件的 Hooks
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  2. 条件判断     │ ←── 评估 Hook 条件
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  3. 执行动作     │ ←── 发送消息、创建记忆、通知等
└────────┬────────┘
         │
         ▼
    完成
```

## 扩展点

### 1. 添加新 CLI 命令

```python
# interface/cli/commands/mycommand.py
import typer

app = typer.Typer(name="mycommand")

@app.command("action")
def my_action():
    pass

# 在 main.py 中注册
from .commands import mycommand
app.add_typer(mycommand.app, name="mycommand")
```

### 2. 添加新 Hook 类型

```python
# core/hooks.py
class CustomTrigger(Trigger):
    def should_trigger(self, context):
        # 自定义触发逻辑
        pass
```

### 3. 添加新 LLM 提供商

```python
# core/llm.py
class CustomProvider(LLMProvider):
    def chat(self, messages):
        # 自定义调用逻辑
        pass
```

## 技术栈

| 类别 | 技术 |
|------|------|
| 语言 | Python 3.9+ |
| CLI | Typer, Rich, Click |
| 数据验证 | Pydantic, Pydantic-Settings |
| 存储 | Markdown, YAML, JSON |
| 搜索 | BM25, TF-IDF, Rank-BM25 |
| LLM | OpenAI, Claude, DeepSeek |
| 同步 | GitPython |
| 测试 | pytest, pytest-cov |
| 代码质量 | black, isort, mypy, ruff |

## 性能考虑

| 方面 | 策略 |
|------|------|
| 记忆检索 | 增量索引，首次加载后缓存 |
| 搜索响应 | BM25 毫秒级，LLM 判断异步 |
| 存储优化 | 按日期分区，定期归档 |
| 并发 | 用户数据隔离，无共享状态 |

## 安全考虑

| 方面 | 措施 |
|------|------|
| 数据隔离 | 目录级用户隔离 |
| API 密钥 | 存储在用户配置，不提交 Git |
| 敏感信息 | 支持 .env 文件，环境变量 |
| 输入验证 | Pydantic 自动验证 |

## 未来演进

| 方向 | 计划 |
|------|------|
| 架构 | 微服务化，插件系统 |
| 接口 | Web UI, Mobile App, API |
| 智能 | 自主规划，主动交互 |
| 协作 | 多用户协作，共享空间 |

---

**文档版本:** 1.0  
**最后更新:** 2025-03-25  
**作者:** Huaqi Team
