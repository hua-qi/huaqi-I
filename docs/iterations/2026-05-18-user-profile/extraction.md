# 用户信息提取方案

文档描述 Huaqi CLI 启动时的用户信息提取机制，包含多层级保障策略。

---

## 1. 方案概述

### 1.1 设计目标

- **非侵入式**：启动时异步执行，不阻塞用户输入
- **高可用**：LLM 失败时自动降级，确保功能可用
- **数据全面**：整合用户画像、日记、对话历史等多源数据

### 1.2 核心流程

```
CLI 启动
    │
    ▼
启动后台提取线程（异步）
    │
    ▼
┌─────────────────────────────────────┐
│ 第1层：LLM 智能提取                  │
│ - 分析日记、对话、画像               │
│ - 30秒超时，失败自动重试             │
└─────────────────────────────────────┘
    │ 成功：返回结构化信息
    │ 失败（3次重试后）
    ▼
┌─────────────────────────────────────┐
│ 第2层：规则兜底提取                  │
│ - 正则匹配关键词                     │
│ - 零延迟、零依赖                     │
└─────────────────────────────────────┘
    │ 成功：返回匹配信息
    │ 无匹配
    ▼
┌─────────────────────────────────────┐
│ 第3层：空结果兜底                    │
│ - 不影响正常使用                     │
│ - 下次启动再尝试                     │
└─────────────────────────────────────┘
```

---

## 2. 实现架构

### 2.1 核心类

```python
class UserDataExtractor:
    """启动时从多数据源提取用户信息"""
    
    MAX_RETRIES = 3           # 最大重试次数
    RETRY_DELAY_BASE = 2.0    # 基础延迟（秒），指数退避
    LLM_TIMEOUT = 30          # 每次 LLM 调用超时（秒）
```

### 2.2 数据源整合

| 数据源 | 范围 | 用途 |
|--------|------|------|
| 用户画像 | 已有身份信息 | 避免重复提取、增量更新 |
| 日记 | 最近 5 篇 | 情绪、日常、自我描述 |
| 对话历史 | 最近 3 次会话 | 互动中透露的信息 |

### 2.3 提取字段

```json
{
    "name": "名字",
    "nickname": "昵称",
    "occupation": "职业",
    "location": "所在地",
    "company": "公司",
    "skills": ["技能1", "技能2"],
    "hobbies": ["爱好1", "爱好2"],
    "life_goals": ["目标1"],
    "education": "教育背景",
    "family_info": "家庭信息"
}
```

---

## 3. 重试机制

### 3.1 指数退避策略

| 尝试次数 | 延迟时间 | 累计等待 |
|---------|---------|---------|
| 第1次 | 0秒 | 0秒 |
| 第2次 | 2秒 | 2秒 |
| 第3次 | 4秒 | 6秒 |
| 第4次 | 8秒 | 14秒 |

**最坏情况总耗时**：`30s × 4 + 14s ≈ 2分钟`

### 3.2 重试触发条件

- LLM API 超时
- 网络异常
- JSON 解析失败
- 返回格式不符合预期

---

## 4. 兜底方案（Fallback）

### 4.1 规则模式表

| 正则模式 | 提取字段 | 示例 |
|---------|---------|------|
| `我是([\u4e00-\u9fa5]{2,4})` | name | "我是子蒙" → 子蒙 |
| `我叫([\u4e00-\u9fa5]{2,4})` | name | "我叫小明" → 小明 |
| `昵称[是为]?([\u4e00-\u9fa5\w]{1,6})` | nickname | "昵称阿伟" → 阿伟 |
| `([\u4e00-\u9fa5]{2,6})工程师` | occupation | "软件工程师" → 软件工程师 |
| `职业[是为]([^，。]{2,10})` | occupation | "职业是设计师" → 设计师 |
| `住在([^，。]{2,10})` | location | "住在北京" → 北京 |
| `([^，。]{2,6})人` | location | "上海人" → 上海 |
| `在([^，。]{2,10})工作` | company | "在字节工作" → 字节 |
| `公司[是为]([^，。]{2,10})` | company | "公司是腾讯" → 腾讯 |
| `我会([\u4e00-\u9fa5\w\s,]+)` | skills | "我会Python和React" → ["Python", "React"] |
| `擅长([\u4e00-\u9fa5\w\s,]+)` | skills | "擅长写作" → ["写作"] |
| `喜欢([\u4e00-\u9fa5\w\s,]+)` | hobbies | "喜欢跑步和阅读" → ["跑步", "阅读"] |
| `爱好([\u4e00-\u9fa5\w\s,]+)` | hobbies | "爱好摄影" → ["摄影"] |

### 4.2 兜底方案特点

- **零依赖**：不调用任何外部 API
- **零延迟**：本地正则匹配，毫秒级响应
- **保守策略**：只提取明确匹配的内容，不误提取

---

## 5. 状态管理

### 5.1 提取状态

```python
# 获取提取器状态
extractor = get_data_extractor()

extractor.is_extracting()      # 是否正在提取
extractor.get_result()         # 获取结果（None 表示未完成）
extractor.get_retry_count()    # 已重试次数
extractor.get_last_error()     # 最后错误信息
```

### 5.2 状态回调

```python
def on_status(message: str):
    print(f"[提取状态] {message}")

def on_complete(result: dict):
    print(f"提取完成: {result}")

extractor.start_extraction(
    llm_manager,
    on_complete=on_complete,
    on_status=on_status
)
```

### 5.3 状态流转

```
初始化
    │
    ▼
┌─────────────┐    启动提取     ┌─────────────┐
│   IDLE      │ ──────────────▶ │ EXTRACTING  │
│  (未开始)   │                 │  (提取中)   │
└─────────────┘                 └─────────────┘
                                      │
                    成功/失败        │
                    /取消           ▼
                              ┌─────────────┐
                              │  COMPLETED  │
                              │  (已完成)   │
                              └─────────────┘
```

---

## 6. 使用方式

### 6.1 CLI 启动时自动触发

```python
# cli.py - chat_mode()
def chat_mode():
    ensure_initialized()
    
    # 启动时异步提取（后台执行）
    try:
        from huaqi_src.core.user_profile import get_data_extractor
        extractor = get_data_extractor()
        
        if not extractor.is_extracting() and extractor.get_result() is None:
            # 初始化 LLM
            _llm_for_extraction = LLMManager()
            # ... 配置 LLM ...
            
            extractor.start_extraction(_llm_for_extraction)
            console.print("[dim]💡 正在分析你的日记和对话...[/dim]\n")
    except Exception:
        pass  # 提取失败不影响主流程
```

### 6.2 手动触发提取

```python
from huaqi_src.core.user_profile import extract_user_info_on_startup

# 阻塞执行，带超时
result = extract_user_info_on_startup(
    llm_manager,
    timeout=60.0  # 最多等待60秒
)

print(f"提取结果: {result}")
```

---

## 7. 存储位置

提取的用户信息存储在：`~/.huaqi/memory/user_profile.yaml`

```yaml
identity:
  name: "子蒙"
  occupation: "工程师"
  location: "北京"

background:
  skills: ["Python", "React"]
  hobbies: ["阅读", "跑步"]

extraction_history:
  - timestamp: "2024-03-28T10:30:00"
    fields: {name: "子蒙", occupation: "工程师"}
    source_preview: "startup_analysis"
```

---

## 8. 与旧方案对比

| 特性 | 旧方案（每次对话） | 新方案（启动时） |
|------|-------------------|-----------------|
| 调用时机 | 每次用户输入后 | CLI 启动时一次 |
| 数据源 | 仅当前输入消息 | 日记+历史+画像 |
| API 调用次数 | N 次（对话轮数） | 1 次（最多4次含重试）|
| 阻塞用户 | 是（6秒超时） | 否（后台线程） |
| 失败处理 | 超时跳过 | 自动重试+兜底 |
| 失败率 | 高（DeepSeek 超时） | 低（多层保障） |

---

## 9. 相关文件

- `huaqi_src/core/user_profile.py` - 核心实现
- `cli.py` - CLI 集成
- `huaqi_src/core/diary_simple.py` - 日记存储
- `huaqi_src/memory/storage/markdown_store.py` - 对话存储

---

## 10. 后续优化方向

1. **增量提取**：只分析上次提取后的新数据
2. **提取质量评分**：基于置信度决定是否采用
3. **用户确认机制**：重要信息提取后询问用户确认
4. **多模型备份**：主模型失败时切换到备用模型
