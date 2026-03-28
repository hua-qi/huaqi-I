# 用户画像叙事生成系统

本文档描述 Huaqi 的动态用户画像机制：由 LLM 每日生成一份客观、多维度的叙事性画像，取代原有的固定结构化字段展示。

---

## 设计思路

原有 `profile show` 展示的是 `user_profile.yaml` 中的键值对（名字、职业、爱好等固定字段），本质上是一个"数据库记录"，无法反映用户的性格特质、思维模式、情绪倾向等深层维度。

新方案的核心思路：

- **数据来源**：结构化字段 + 最近 10 篇日记完整内容 + 最近 5 次对话记录
- **生成方式**：由 LLM 综合以上数据，生成 300-600 字的叙事性段落
- **缓存策略**：每天生成一次，缓存到 `profile_narrative.yaml`，当天内重复查看不重复调用 LLM
- **客观原则**：Prompt 明确要求包含优缺点，覆盖多维度，不美化

---

## 数据流

```
huaqi profile refresh
        │
        ├─ 收集结构化字段（identity / background / preferences）
        ├─ 读取最近 10 篇日记（完整内容，超 500 字截断）
        ├─ 读取最近 5 次对话摘要
        │
        ├─ 构建 Prompt（见下文）
        ├─ 调用 LLM（temperature=0.7，max_tokens=1500）
        │
        └─ 保存到 ~/.huaqi/memory/profile_narrative.yaml
```

---

## Prompt 设计

Prompt 核心要求：

1. **完全客观**，同时包含优势和缺点/局限性，不要美化
2. **维度尽可能多**，覆盖但不限于：性格特质、思维方式、工作风格、情绪模式、人际关系倾向、价值观、成长轨迹、潜在矛盾或挣扎
3. 用**第三人称**叙事，语言凝练但有温度
4. 基于数据说话，有推断时要标注"推测"
5. 长度 300-600 字，分段落，**不要列清单**

---

## 核心类

### `ProfileNarrative`（`user_profile.py`）

```python
@dataclass
class ProfileNarrative:
    content: str                    # LLM 生成的叙事正文
    generated_at: str               # 生成时间（ISO 格式）
    data_sources: List[str]         # 数据来源标注（如 "日记(8篇)"）

    def is_today(self) -> bool:
        """判断是否为今日生成（用于缓存有效性检查）"""
```

### `ProfileNarrativeManager`（`user_profile.py`）

| 方法 | 说明 |
|------|------|
| `needs_refresh()` | 是否需要重新生成（无缓存或非今日） |
| `get_cached()` | 读取本地缓存 |
| `generate(llm_manager)` | 调用 LLM 生成并保存缓存 |
| `get_or_generate(llm_manager)` | 有效缓存直接返回，否则生成 |
| `generate_async(llm_manager, on_complete)` | 异步生成，不阻塞主线程 |

全局单例通过 `get_narrative_manager()` 获取。

---

## CLI 命令

### `huaqi profile show`

优先展示叙事画像，结构化字段作为补充（仅展示有值的字段）：

- 今日缓存存在 → 用 Panel 高亮展示，附数据来源和生成时间
- 旧缓存存在 → 标注"旧"并展示，提示运行 refresh
- 无缓存 → 提示运行 refresh

### `huaqi profile refresh`

立即重新生成，忽略今日缓存，调用结束后展示结果并保存。

---

## 缓存文件

位置：`~/.huaqi/memory/profile_narrative.yaml`

```yaml
content: |
  这是一段由 LLM 生成的叙事性画像描述...
generated_at: "2026-03-29T10:30:00.000000"
data_sources:
  - 结构化画像
  - 日记(8篇)
  - 对话(3次)
```

---

## 与原有结构化提取的关系

两套机制并行存在，各有分工：

| 机制 | 文件 | 用途 |
|------|------|------|
| 结构化提取（`UserDataExtractor`） | `user_profile.yaml` | 供 LLM 对话时注入系统提示词，精确信息（名字、职业等） |
| 叙事生成（`ProfileNarrativeManager`） | `profile_narrative.yaml` | 供用户查阅，反映深层画像 |

叙事生成在收集数据时会读取结构化字段作为输入之一。
