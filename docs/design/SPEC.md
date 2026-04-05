# Huaqi - 个人 AI 同伴系统

> 不是使用 AI，而是养育 AI —— 让它越来越像你，越来越懂你

---

## 1. 项目愿景

### 1.1 核心理念

**Human 3.0**: 通过 AI 基础设施实现人类能力的大规模增强，应对"狗屁工作"时代的终结。

**关系定位**: 不是主仆，而是**同伴 (Peer)** —— 共同成长的数字伙伴。

**设计原则**: 
- Humans set direction, AI executes at scale
- 模块化、可进化、可迁移
- 隐私优先、本地优先、用户可控

### 1.2 系统目标

1. **记忆**: 建立完整的个人知识库，记录身份、偏好、项目、学习轨迹
2. **执行**: 信息收集、编码辅助、内容创作、学习辅导
3. **成长**: AI 随着对你的了解深入而进化，学习新技能
4. **陪伴**: 答疑解惑、辅助决策、提升认知

---

## 2. 架构设计

### 2.1 总体架构

```
┌─────────────────────────────────────────────────────────────┐
│                      7. 接口层 (Interface)                   │
│          CLI 为主 · 语音为辅 · 多端同步 · 沉浸式交互           │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      6. 编排层 (Orchestration)               │
│          Hook 系统 · 上下文管线 · 代理分级 · 自动化流          │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      1. 智能层 (Intelligence)                │
│         大模型核心 · 持续学习 · 经验积累 · 认知进化            │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 2. 上下文    │    │ 3. 个性      │    │ 4. 工具      │
│   (Context)  │    │ (Personality)│    │  (Tools)    │
├──────────────┤    ├──────────────┤    ├──────────────┤
│ • 会话记忆   │    │ • 性格特征   │    │ • MCP 技能   │
│ • 工作记忆   │    │ • 情绪表达   │    │ • 外部集成   │
│ • 学习记忆   │    │ • 声音身份   │    │ • 200+模式   │
│              │    │ • 同伴关系   │    │              │
└──────────────┘    └──────────────┘    └──────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                      5. 安全层 (Security)                    │
│          多层防御 · 提示注入防护 · 数据加密 · 权限控制         │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 存储架构 (混合方案)

**核心设计**: 文本文件 + 向量索引 + 云端同步

```
存储层级:
┌──────────────────────────────────────────┐
│  Layer 3: 云端备份 (GitHub Private / S3) │  ← 跨设备同步
├──────────────────────────────────────────┤
│  Layer 2: 向量索引 (Chroma/SQLite)       │  ← AI 语义检索
├──────────────────────────────────────────┤
│  Layer 1: 文本文件 (Markdown/YAML)       │  ← 人类可读、版本控制
└──────────────────────────────────────────┘
```

**迁移策略**:
- 所有数据存储在 `~/.huaqi/` 目录
- 使用 Git 进行版本控制
- 支持导出/导入完整数据包
- 配置云端同步端点 (可选)

---

## 3. 技术选型

| 组件 | 技术方案 | 选型理由 |
|------|----------|----------|
| **核心语言** | Python 3.10+ | 生态丰富、AI 友好 |
| **LLM 接口** | OpenAI API / Claude API / 本地模型 | 灵活切换、降级方案 |
| **向量数据库** | Chroma (SQLite 后端) | 本地优先、零配置、可迁移 |
| **Embedding** | OpenAI text-embedding-3 / text2vec | 质量高、成本低 |
| **配置管理** | Pydantic Settings + YAML | 类型安全、易维护 |
| **CLI 框架** | Typer + Rich | 现代化、交互友好 |
| **数据同步** | Git + 可选云存储 | 版本控制、跨设备 |
| **任务调度** | APScheduler / 系统 Cron | 轻量、可靠 |

---

## 4. 目录结构

```
huaqi/
│   ├── SPEC.md                    # 总体架构 (本文件)
│   ├── architecture/              # 架构设计文档
│   ├── roadmap/                   # 路线图
│   └── decisions/                 # 技术决策记录 (ADR)
│
├── huaqi/                         # 核心代码
│   ├── __init__.py
│   ├── core/                      # 核心模块
│   │   ├── config.py              # 配置管理
│   │   ├── memory.py              # 记忆管理器
│   │   ├── personality.py         # 个性引擎
│   │   └── intelligence.py        # LLM 接口
│   │
│   ├── memory/                    # 记忆系统实现
│   │   ├── storage/               # 存储层
│   │   │   ├── file_store.py      # 文件存储
│   │   │   └── vector_store.py    # 向量存储
│   │   ├── layers/                # 三层记忆
│   │   │   ├── session.py         # 会话记忆
│   │   │   ├── working.py         # 工作记忆
│   │   │   └── long_term.py       # 长期记忆
│   │   └── sync/                  # 同步机制
│   │       └── git_sync.py        # Git 同步
│   │
│   ├── skills/                    # 技能系统 (MCP)
│   │   ├── base.py                # 技能基类
│   │   ├── registry.py            # 技能注册表
│   │   ├── search/                # 信息收集
│   │   ├── coding/                # 代码辅助
│   │   ├── music/                 # 电吉他
│   │   ├── language/              # 英语学习
│   │   └── content/               # 内容创作
│   │
│   ├── orchestration/             # 编排层
│   │   ├── hooks.py               # Hook 系统
│   │   ├── pipeline.py            # 处理管线
│   │   └── agents.py              # 代理管理
│   │
│   ├── interface/                 # 交互层
│   │   ├── cli/                   # 命令行
│   │   │   ├── main.py
│   │   │   ├── chat.py            # 对话命令
│   │   │   ├── memory.py          # 记忆命令
│   │   │   └── config.py          # 配置命令
│   │   └── voice/                 # 语音接口 (Future)
│   │
│   └── security/                  # 安全层
│       ├── constitution.py        # AI 行为准则
│       └── guardrails.py          # 输入/输出防护
│
├── templates/                     # 模板文件
│   ├── personality/               # 个性模板
│   ├── memory/                    # 记忆结构模板
│   └── skills/                    # 技能模板
│
├── tests/                         # 测试
├── scripts/                       # 工具脚本
├── requirements.txt               # 依赖
├── pyproject.toml                 # 项目配置
└── README.md                      # 项目说明
```

---

## 5. 数据模型

### 5.1 记忆模型

```yaml
# 长期记忆条目
memory_entry:
  id: "mem_20240324_001"
  type: "insight"  # identity / project / skill / insight / conversation
  content: "用户在探索技术+创造力的结合，对 AI 个人助手有强烈兴趣"
  source: "conversation_20240324"
  embedding: [...]  # 向量表示
  metadata:
    created_at: "2026-03-24T10:00:00Z"
    updated_at: "2026-03-24T10:00:00Z"
    tags: ["interest", "ai", "career"]
    importance: 0.9  # 0-1
    access_count: 1
  relations:
    - target: "mem_identity_001"
      type: "related_to"
```

### 5.2 用户档案模型

```yaml
# ~/.huaqi/memory/identity/profile.yaml
profile:
  basic:
    name: "连子蒙"
    role: "软件工程师"
    current_stage: "探索期"
  
  values:
    - "成长 > 稳定"
    - "创造 > 消费"
    - "深度 > 广度"
  
  interests:
    - name: "电吉他"
      level: "入门"
      time_invested: "3个月"
      weekly_hours: 5
    - name: "AI/LLM"
      level: "进阶"
      current_project: "构建个人 AI 助手"
  
  patterns:
    decision_making: "先收集信息，再凭直觉"
    learning_style: "自主探索，不喜欢被安排"
    time_preference: "长期价值导向，能延迟满足"
  
  goals:
    short_term: [...]
    long_term: [...]
```

---

## 6. 接口设计

### 6.1 CLI 命令

```bash
# 基础交互
huaqi chat                    # 开始对话
huaqi chat --quick           # 快速问答模式
huaqi chat --voice           # 语音对话 (Future)

# 记忆管理
huaqi memory search "电吉他"  # 搜索记忆
huaqi memory add "..."       # 添加记忆
huaqi memory review          # 回顾今日记忆
huaqi memory status          # 记忆系统状态

# 技能调用
huaqi skill list             # 列出技能
huaqi skill run search "..." # 执行搜索技能
huaqi skill run guitar       # 电吉他辅导

# 配置管理
huaqi config init            # 初始化配置
huaqi config sync            # 同步数据
huaqi config export          # 导出数据
huaqi config import          # 导入数据

# 系统
huaqi status                 # 查看系统状态
huaqi doctor                 # 诊断问题
huaqi update                 # 更新系统
```

---

## 7. 安全与隐私

### 7.1 数据安全

- **本地优先**: 所有敏感数据本地存储
- **加密存储**: 配置文件和环境变量加密
- **权限控制**: 细粒度的 API 密钥管理
- **审计日志**: 记录所有敏感操作

### 7.2 AI 安全 (Constitution)

```yaml
# AI 行为准则
constitution:
  principles:
    - "永远尊重用户自主权"
    - "不替代用户做重大决策"
    - "保护用户隐私信息"
    - "承认不确定性，不编造"
  
  constraints:
    - "不执行有害或非法请求"
    - "不泄露用户的敏感记忆"
    - "不假装成人类"
```

---

## 8. 扩展性设计

### 8.1 技能扩展 (MCP 协议)

```python
# 技能接口定义
class Skill:
    name: str
    description: str
    
    def invoke(self, context: Context, **params) -> Result:
        pass
    
    def schema(self) -> dict:
        """返回 JSON Schema 定义参数"""
        pass
```

### 8.2 多 LLM 支持

```yaml
# ~/.huaqi/config.yaml
llm:
  default: "claude"
  providers:
    claude:
      model: "claude-3-7-sonnet-20250219"
      api_key: "${CLAUDE_API_KEY}"
    openai:
      model: "gpt-4"
      api_key: "${OPENAI_API_KEY}"
    local:
      model: "llama2-7b"
      endpoint: "http://localhost:11434"
```

---

## 9. 迁移与备份

### 9.1 数据迁移

```bash
# 导出完整数据
huaqi export --output huaqi_backup_20240324.tar.gz

# 导入数据
huaqi import huaqi_backup_20240324.tar.gz

# 同步到云端
huaqi sync push

# 从云端恢复
huaqi sync pull
```

### 9.2 跨设备同步

```yaml
# ~/.huaqi/config.yaml
sync:
  enabled: true
  provider: "github"  # github / s3 / webdav
  github:
    repo: "username/huaqi-data"
    branch: "main"
    token: "${GITHUB_TOKEN}"
```

---

## 10. 路线图

### Phase 1: 基础架构 (Week 1-2)
- [ ] 项目脚手架搭建
- [ ] 配置管理系统
- [ ] 基础 CLI 框架
- [ ] 记忆存储层 (文件 + 向量)

### Phase 2: 记忆系统 (Week 3-4)
- [ ] 三层记忆实现
- [ ] 记忆自动提取
- [ ] 语义检索
- [ ] Git 同步机制

### Phase 3: 智能核心 (Week 5-6)
- [ ] LLM 接口抽象
- [ ] 个性引擎
- [ ] 对话管理
- [ ] Hook 系统

### Phase 4: 技能生态 (Week 7-8)
- [ ] MCP 技能框架
- [ ] 搜索技能
- [ ] 代码辅助技能
- [ ] 学习辅导技能

### Phase 5: 高级功能 (Week 9-12)
- [ ] 自动化工作流
- [ ] 成长报告
- [ ] 语音接口
- [ ] 移动端适配

---

## 11. 开发规范

### 11.1 Spec-Driven 开发流程

1. **Design**: 编写/更新 Spec 文档
2. **Review**: 评审技术方案
3. **Implement**: 按 Spec 实现
4. **Test**: 验证符合 Spec
5. **Document**: 更新文档

### 11.2 代码规范

- 使用 `black` 格式化
- 使用 `mypy` 类型检查
- 测试覆盖率 > 80%
- 文档字符串遵循 Google Style

---

## 12. 参考与致谢

- Daniel Miessler - Personal AI Infrastructure
- 沈浪 - "养了个 AI" 系列
- Model Context Protocol (MCP)
- Mem0 - Memory Layer for AI

---

*文档版本: v0.1*
*最后更新: 2026-03-24*
*作者: 连子蒙*
