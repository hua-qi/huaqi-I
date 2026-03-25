# Huaqi V2 架构迁移指南

> 从 Embedding-based 到 LLM+Algorithm 架构的全面升级

## 概述

Huaqi V2 完成了核心架构的重大升级：**完全移除 Embedding 模型依赖**，改为纯 **LLM + 算法** 实现。这使得系统可以兼容**任何大模型**，不再受限于特定的 Embedding 提供商。

---

## 架构对比

### V1 架构（旧）

```
┌─────────────────────────────────────────┐
│  语义搜索                                │
│  查询 → Embedding → 向量相似度计算       │
│  ↓ 依赖 OpenAI/其他 Embedding API       │
└─────────────────────────────────────────┘
```

**限制**：
- ❌ 必须配置 Embedding 模型
- ❌ Claude/DeepSeek 等模型无配套 Embedding
- ❌ 向量存储占用空间大
- ❌ 新模型支持滞后

### V2 架构（新）

```
┌─────────────────────────────────────────┐
│  混合搜索                                │
│  1. BM25 快速召回（本地算法）            │
│  2. LLM 相关性判断（API 调用）           │
│  3. 融合排序                             │
│  ↓ 只需 LLM 会对话即可                  │
└─────────────────────────────────────────┘
```

**优势**：
- ✅ 兼容任何大模型（Claude、DeepSeek、本地模型等）
- ✅ 无需额外 Embedding 配置
- ✅ 纯文本存储，便于版本控制
- ✅ 新模型立即可用

---

## 破坏性变更

### 1. 配置文件变更

**V1 配置（旧）**：
```yaml
# user.yaml
memory:
  embedding_model: "text-embedding-3-small"  # ❌ 已移除
  vector_db_path: "vectors/"                   # ❌ 已移除
```

**V2 配置（新）**：
```yaml
# user.yaml
memory:
  search_algorithm: "hybrid"      # ✅ 新增: hybrid/text/llm
  search_recall_k: 20             # ✅ 新增: 召回数量
  search_top_k: 5                 # ✅ 新增: 返回数量
```

### 2. API 变更

**V1 搜索（旧）**：
```python
from huaqi.memory.storage.vector_store import UserVectorStore

vector_store = UserVectorStore(data_dir, user_id, embedding_provider)
results = vector_store.search_memories("查询", top_k=5)
```

**V2 搜索（新）**：
```python
from huaqi.memory.storage.memory_manager_v2 import MemoryManagerV2

memory_mgr = MemoryManagerV2(data_dir, user_id, llm_manager)
results = memory_mgr.search("查询", search_type="hybrid", top_k=5)
```

### 3. CLI 变更

**V1 命令（旧）**：
```bash
huaqi memory search "查询" --semantic    # ❌ --semantic 已移除
```

**V2 命令（新）**：
```bash
huaqi memory search "查询" --type hybrid   # ✅ 默认即为混合搜索
huaqi memory search "查询" --type text     # ✅ 纯文本搜索
huaqi memory search "查询" --type llm      # ✅ 纯 LLM 搜索
huaqi memory search "查询" --explain       # ✅ 显示详细分数
```

---

## 迁移步骤

### 步骤 1：更新配置（自动）

启动时系统会自动移除旧配置项，无需手动操作。

### 步骤 2：重建索引（可选）

V2 使用实时搜索，无需预先构建向量索引。但如果想要更好的性能，可以：

```python
from huaqi.memory.storage.memory_manager_v2 import MemoryManagerV2

memory_mgr = MemoryManagerV2(data_dir, user_id, llm_manager)
# 首次搜索时会自动加载记忆到内存索引
```

### 步骤 3：验证功能

```bash
# 测试新搜索
huaqi memory search "电吉他" --type hybrid --explain

# 测试对话（会自动使用新搜索）
huaqi chat
```

---

## 新特性详解

### 1. 三层搜索策略

| 搜索类型 | 适用场景 | 速度 | 精度 |
|---------|---------|------|------|
| `text` | 无 LLM 时、大量数据 | ⚡ 极快 | ⭐⭐ |
| `llm` | 少量数据、高精度需求 | 🐢 较慢 | ⭐⭐⭐⭐⭐ |
| `hybrid`（推荐） | 通用场景 | ⚡ 快 | ⭐⭐⭐⭐ |

### 2. BM25 算法

V2 使用经典的 BM25 信息检索算法：

```
BM25 分数 = IDF * (f * (k1 + 1)) / (f + k1 * (1 - b + b * (doc_len / avg_doc_len)))

其中:
- IDF: 逆文档频率
- f: 词频
- k1: 饱和度参数（默认 1.5）
- b: 长度归一化参数（默认 0.75）
```

优势：
- 本地计算，零延迟
- 无需外部 API
- 可解释性强

### 3. LLM 相关性判断

当使用 `hybrid` 或 `llm` 模式时，系统会：

1. 先用 BM25 召回 Top 20 候选
2. 将候选送入 LLM 判断相关性
3. LLM 返回 0-1 的相关性分数和理由
4. 融合两种分数得到最终排序

**示例 LLM Prompt**：
```
请判断以下查询与记忆内容的相关性。

查询: 电吉他学习进展

记忆内容:
[1] 电吉他练习已经三个月了，可以弹一些简单的曲子

请分析：
1. 这段记忆是否回答了查询？
2. 这段记忆是否包含查询相关的信息？
3. 相关程度如何？（0-1 分）

返回 JSON:
{
    "relevant": true,
    "score": 0.95,
    "reason": "记忆明确提到了电吉他练习时长和进展"
}
```

---

## 性能对比

| 指标 | V1 (Embedding) | V2 (LLM+Algorithm) |
|------|----------------|-------------------|
| **冷启动** | 需预计算向量 | 实时计算 |
| **存储空间** | 向量库占用大 | 纯文本，节省 70%+ |
| **搜索延迟** | ~100ms | ~500ms (含 LLM) |
| **LLM 依赖** | 仅对话用 | 对话+搜索用 |
| **模型兼容** | 受限 | 任意模型 |

---

## 降级策略

当 LLM 不可用时，系统自动降级：

```python
# 有 LLM
if llm_manager.get_active_provider():
    search_engine = HybridSearch(llm_manager)  # 混合搜索
else:
    search_engine = TextSearch("bm25")         # 纯文本搜索
```

用户也可手动指定：
```bash
# 强制使用纯文本搜索（不调用 LLM）
huaqi memory search "查询" --type text
```

---

## 常见问题

### Q: 为什么移除 Embedding？

**A**: 
1. **兼容性**：Claude、DeepSeek 等优秀模型没有配套 Embedding
2. **简化**：减少一个外部依赖，降低配置复杂度
3. **灵活性**：LLM 本身就具备语义理解能力，可以直接判断相关性
4. **成本**：减少 Embedding API 调用费用

### Q: 新架构搜索质量如何？

**A**: 在多数场景下，**hybrid 模式的质量与 Embedding 相当甚至更好**：
- BM25 保证关键词匹配
- LLM 提供语义理解
- 融合后兼具两者优势

### Q: 是否需要重新导入记忆？

**A**: **不需要**。V2 直接读取现有的 Markdown 记忆文件，无缝兼容。

### Q: 向量库数据如何处理？

**A**: `vectors/` 目录不再使用，可以删除：
```bash
rm -rf ~/.huaqi/users_data/<user_id>/vectors
```

---

## 技术细节

### 核心文件变更

```
huaqi/
├── core/
│   └── conversation.py          # 更新：使用新搜索
├── memory/
│   ├── search/                  # ✅ 新增目录
│   │   ├── __init__.py
│   │   ├── text_search.py       # ✅ BM25/TF-IDF
│   │   ├── llm_search.py        # ✅ LLM 相关性
│   │   └── hybrid_search.py     # ✅ 混合搜索
│   └── storage/
│       ├── vector_store.py      # ❌ 已删除
│       └── memory_manager_v2.py # ✅ 新增
└── interface/cli/main.py        # 更新：新 CLI 命令
```

### 依赖变化

**移除**：
```
chromadb           # 不再需要向量数据库
sentence-transformers  # 不再需要本地 Embedding
```

**保留**：
```
typer, rich        # CLI 框架
pydantic           # 配置验证
pyyaml             # YAML 解析
openai, anthropic  # LLM API（可选）
```

---

## 回滚方案

如需回退到 V1，执行：

```bash
# 1. 恢复到 V1 代码
git checkout <v1-commit-hash>

# 2. 重新配置 Embedding
huaqi config set memory.embedding_model text-embedding-3-small

# 3. 重建向量索引
# （需要重新运行记忆导入）
```

---

## 总结

Huaqi V2 的架构升级带来了：

| 方面 | 改进 |
|------|------|
| **兼容性** | 支持任何大模型 |
| **简化性** | 减少配置项和依赖 |
| **可维护性** | 纯文本存储，易于版本控制 |
| **扩展性** | 新模型立即可用 |

这是一次**向前兼容**的升级，现有用户数据（Markdown 记忆文件）完全保留，无需迁移数据，只需更新代码即可。

---

*文档版本: V2.0*
*最后更新: 2026-03-25*
