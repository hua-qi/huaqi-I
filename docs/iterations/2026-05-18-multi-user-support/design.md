# 多用户支持设计文档

> Huaqi 系统支持多用户，按账号隔离用户数据

---

## 核心设计

### 数据隔离模型

```
~/.huaqi/
├── users/                    # 用户档案（全局可访问）
│   ├── abc123.json          # 用户1档案
│   └── def456.json          # 用户2档案
│
├── users_data/               # 用户数据（完全隔离）
│   ├── abc123/              # 用户1数据
│   │   ├── config/          # 用户配置
│   │   ├── memory/          # 用户记忆
│   │   ├── skills/          # 用户技能
│   │   └── vectors/         # 用户向量库
│   │
│   └── def456/              # 用户2数据（相同结构）
│       ├── config/
│       ├── memory/
│       ├── skills/
│       └── vectors/
│
└── config/                   # 系统级全局配置
    └── system.yaml
```

### 隔离级别

| 数据类型 | 隔离方式 | 说明 |
|----------|----------|------|
| **用户档案** | 全局可读 | 存储用户基本信息（邮箱、用户名等） |
| **配置文件** | 完全隔离 | 每个用户独立的 LLM、记忆等配置 |
| **记忆数据** | 完全隔离 | 独立目录，互不访问 |
| **向量库** | 完全隔离 | 独立 Chroma 实例 |
| **技能配置** | 完全隔离 | 每个用户的技能启用状态独立 |

---

## 认证系统

### 支持的认证方式

1. **OAuth (GitHub/Google)** - 生产环境推荐
2. **本地用户** - 开发测试用

### 用户档案

```python
class UserProfile:
    user_id: str          # 唯一标识（16位哈希）
    email: str            # 邮箱
    username: str         # 用户名
    display_name: str     # 显示名称
    avatar_url: str       # 头像
    provider: str         # 认证提供商
    created_at: datetime  # 创建时间
    last_login: datetime  # 最后登录
    preferences: dict     # 用户偏好
```

### 会话管理

- 会话令牌 7 天有效期
- 支持多设备同时登录
- 服务端会话存储

---

## 关键组件

### 1. UserManager - 用户管理器

```python
# 创建/获取用户
user = user_manager.create_user(email, username, provider, ...)
user = user_manager.get_user(user_id)

# 会话管理
session = user_manager.create_session(user_id)
user_id = user_manager.validate_session(token)
```

### 2. ConfigManager - 配置管理器

```python
# 初始化时绑定用户
config_manager = ConfigManager(data_dir, user_id="abc123")

# 加载/保存用户配置
config = config_manager.load_config()
config_manager.save_config(config)

# 获取/设置配置项
value = config_manager.get("llm.temperature")
config_manager.set("llm.temperature", 0.8)
```

### 3. UserIsolatedStorage - 用户隔离存储基类

所有用户数据存储类都继承此类：

```python
class UserMemoryManager(UserIsolatedStorage):
    # 自动隔离到用户目录
    self.user_data_dir    # ~/.huaqi/users_data/abc123/
    self.user_memory_dir  # ~/.huaqi/users_data/abc123/memory/

class UserSkillManager(UserIsolatedStorage):
    # 技能配置隔离
    self.skills_dir       # ~/.huaqi/users_data/abc123/skills/
```

---

## CLI 使用

### 用户管理

```bash
# 查看系统状态
huaqi status

# 创建本地用户（开发测试）
huaqi auth create-local \
  --email user@example.com \
  --username username \
  --name "显示名称"

# 列出所有用户
huaqi auth list

# 切换用户
huaqi --user abc123 status

# 查看当前用户
huaqi auth whoami

# 退出登录
huaqi auth logout
```

### 用户隔离的数据操作

```bash
# 所有操作自动使用当前用户的数据

# 导入记忆（保存到当前用户目录）
huaqi import ~/Documents/notes/

# 查看当前用户的记忆
huaqi memory status

# 查看当前用户的配置
huaqi config show

# 设置当前用户的配置
huaqi config set llm.default_provider openai
```

---

## 数据安全

### 导出用户数据

```bash
# 导出为压缩包（方便迁移）
huaqi export --output backup.tar.gz
```

### 导入用户数据

```bash
# 导入数据（支持合并或覆盖）
huaqi import backup.tar.gz --merge
```

### 删除用户

```bash
# 删除用户（需要确认）
huaqi auth delete-user abc123 --confirm
```

---

## 多用户场景示例

### 场景 1：团队协作

```bash
# 团队成员各自有自己的账户
huaqi auth create-local --email alice@company.com --username alice
huaqi auth create-local --email bob@company.com --username bob

# 各自的记忆和数据完全隔离
huaqi --user alice memory status   # Alice 的数据
huaqi --user bob memory status     # Bob 的数据
```

### 场景 2：个人多用途

```bash
# 工作账户
huaqi auth create-local --email work@company.com --username work
# 个人学习账户
huaqi auth create-local --email personal@gmail.com --username personal

# 不同账户不同用途
huaqi --user work import ~/WorkProjects/
huaqi --user personal import ~/LearningNotes/
```

### 场景 3：家庭共享设备

```bash
# 家庭成员各自账户
huaqi auth create-local --email dad@family.com --username dad
huaqi auth create-local --email mom@family.com --username mom

# 完全隔离，互不干扰
```

---

## 未来扩展

### 计划功能

1. **角色权限** - 管理员/普通用户区分
2. **数据共享** - 选择性共享特定记忆
3. **团队协作** - 共享项目空间
4. **审计日志** - 记录用户操作

### OAuth 完整流程

```bash
# 1. 启动 OAuth 登录
huaqi auth login --provider github

# 2. 浏览器打开授权页面
# 3. 用户授权后回调到本地
# 4. 系统自动创建/获取用户
# 5. 登录成功
```

---

## 技术要点

### 用户上下文

```python
# 临时切换用户上下文
with memory_manager.with_user("other_user_id"):
    # 在此范围内操作的是 other_user_id 的数据
    memories = memory_manager.list_memories()

# 上下文结束后自动恢复
```

### 跨用户操作

```python
# 需要管理员权限的操作
for user_id in config_manager.get_all_users():
    with UserContext(config_manager, user_id):
        stats = memory_manager.get_user_stats()
        print(f"{user_id}: {stats['total_size_human']}")
```

---

## 文件结构

```
huaqi/
├── core/
│   ├── auth.py              # 用户认证系统
│   └── config.py            # 配置管理（支持多用户）
│
├── memory/
│   └── storage/
│       └── user_isolated.py # 用户隔离存储基类
│
└── interface/
    └── cli/
        └── main.py          # CLI 命令（含用户管理）
```

---

*设计版本: v0.1*
*最后更新: 2026-03-24*
