# Huaqi 架构改造实施计划

> 基于 PRD.md + TECH_SPEC.md + ARCHITECTURE.md 的详细实施路线

## 📋 总体路线

| 阶段 | 名称 | 工期 | 核心交付物 |
|------|------|------|-----------|
| **P1** | 基础架构搭建 | 1-2天 | 新目录结构、依赖配置 |
| **P2** | 向量存储系统 | 2-3天 | Chroma + BM25 混合搜索可运行 |
| **P3** | LangGraph Agent | 3-4天 | Chat Workflow 完整运行 |
| **P4** | 定时任务系统 | 2天 | 晨间问候、日报自动生成 |
| **P5** | 内容流水线 | 3-4天 | X/RSS → 小红书发布流程 |
| **P6** | 人机协同 | 2天 | Interrupt + Resume 机制 |
| **P7** | 画像更新 | 1-2天 | 自动分析 + 确认流程 |
| **P8** | 配置热重载 + 迁移 | 1-2天 | 不停机配置更新 |

---

## 🔨 Phase 1: 基础架构搭建

**工时**: 1-2天

### 步骤

| 子任务 | 具体工作 | 验证方式 |
|--------|----------|----------|
| **1.1** | 创建新目录结构 (`huaqi/agent/`, `huaqi/scheduler/`, `huaqi/pipeline/`) | `ls huaqi/` 看到新目录 |
| **1.2** | 添加依赖到 `pyproject.toml` | 依赖列表包含 langgraph≥0.2, apscheduler≥4.0, chromadb≥0.5 |
| **1.3** | 创建 `__init__.py` 和基础文件 | 各模块能正常 import |

### 人工验证命令

```bash
# 验证 1.1 - 目录结构
ls -la huaqi/agent huaqi/scheduler huaqi/pipeline

# 验证 1.2 - 依赖安装
pip install -e .
python -c "import langgraph; import chromadb; print('依赖安装成功')"
```

---

## 🔨 Phase 2: 向量存储系统

**工时**: 2-3天

### 步骤

| 子任务 | 具体工作 | 验证方式 |
|--------|----------|----------|
| **2.1** | 实现 `memory/vector/chroma_client.py` - Chroma 封装 | 能创建集合、添加文档 |
| **2.2** | 实现 `memory/vector/embedder.py` - Embedding 服务 | 能将文本转为向量 |
| **2.3** | 实现 `memory/vector/hybrid_search.py` - 混合检索 | 融合 BM25 + 向量 + 时间衰减 |
| **2.4** | 数据迁移脚本 - 旧日记导入向量库 | 现有日记能被索引 |

### 人工验证命令

```bash
# 验证 2.1 - 添加数据
python -c "
from huaqi.memory.vector.chroma_client import ChromaClient
client = ChromaClient()
client.add('test_1', '今天学习了 Python', {'type': 'diary', 'date': '2025-03-27'})
print('添加成功')
"

# 验证 2.3 - 混合搜索
python -c "
from huaqi.memory.vector.hybrid_search import HybridSearch
search = HybridSearch()
results = search.search('学习编程', top_k=3)
print(f'找到 {len(results)} 条结果')
for r in results:
    print(f'  - {r[\"id\"]}: {r[\"content\"][:50]}...')
"
```

---

## 🔨 Phase 3: LangGraph Agent 核心

**工时**: 3-4天

### 步骤

| 子任务 | 具体工作 | 验证方式 |
|--------|----------|----------|
| **3.1** | 定义 `agent/state.py` - AgentState TypedDict | 包含 messages, intent, memories 字段 |
| **3.2** | 实现 `agent/nodes/chat_nodes.py` - 对话节点 | classify_intent, build_context, generate_response |
| **3.3** | 实现 `agent/graph/chat.py` - Chat Workflow | 能编译执行完整对话流程 |
| **3.4** | 集成到 CLI - `huaqi chat` 命令 | CLI 能启动对话 |

### 人工验证命令

```bash
# 验证 3.3 - Workflow 运行
python -c "
from huaqi.agent.graph.chat import build_chat_graph
graph = build_chat_graph()
result = graph.invoke({'messages': [{'role': 'user', 'content': '你好'}]})
print('回复:', result['messages'][-1].content)
"

# 验证 3.4 - CLI 对话
huaqi chat
# 输入: "你好"
# 预期: AI 能正常回复
```

---

## 🔨 Phase 4: APScheduler 定时任务

**工时**: 2天

### 步骤

| 子任务 | 具体工作 | 验证方式 |
|--------|----------|----------|
| **4.1** | 实现 `scheduler/manager.py` - 调度器封装 | 支持添加/删除/列出任务 |
| **4.2** | 实现 `scheduler/handlers.py` - 任务处理器 | 晨间问候、日报生成 |
| **4.3** | 配置持久化 (SQLAlchemyJobStore) | 重启后任务不丢失 |
| **4.4** | CLI 命令 `huaqi daemon start/stop/status` | 能启停 Daemon |

### 人工验证命令

```bash
# 验证 4.1 - 添加定时任务
python -c "
from huaqi.scheduler.manager import SchedulerManager
sm = SchedulerManager()
sm.add_job('test_greeting', 'generate_morning_greeting', '* * * * *')  # 每分钟执行
sm.start()
import time; time.sleep(65)  # 等待任务触发
"

# 验证 4.4 - Daemon 管理
huaqi daemon start --foreground
# 预期: 看到定时任务日志
```

---

## 🔨 Phase 5: 内容流水线

**工时**: 3-4天

### 步骤

| 子任务 | 具体工作 | 验证方式 |
|--------|----------|----------|
| **5.1** | 实现数据源适配器 (`pipeline/sources/twitter.py`, `rss.py`) | 能抓取 X/RSS 内容 |
| **5.2** | 实现 `pipeline/processors/summarizer.py` - 内容总结 | 长文能生成摘要 |
| **5.3** | 实现 `pipeline/processors/generator.py` - 文案生成 | 能生成小红书/微博文案 |
| **5.4** | 实现平台适配器 `pipeline/platforms/xiaohongshu.py` | 生成预览二维码/链接 |
| **5.5** | 组装 `agent/graph/content.py` - Content Pipeline | 完整流程可执行 |

### 人工验证命令

```bash
# 验证 5.1 - 数据源抓取
python -c "
from huaqi.pipeline.sources.rss import RSSAdapter
adapter = RSSAdapter()
contents = adapter.fetch_latest('https://example.com/feed', limit=5)
print(f'抓取到 {len(contents)} 条内容')
"

# 验证 5.5 - 完整流水线
python -c "
from huaqi.agent.graph.content import build_content_pipeline
graph = build_content_pipeline()
result = graph.invoke({'source_contents': []})  # 测试数据
print('生成的文案:', result.get('generated_posts', {}))
"
```

---

## 🔨 Phase 6: 人机协同中断恢复

**工时**: 2天

### 步骤

| 子任务 | 具体工作 | 验证方式 |
|--------|----------|----------|
| **6.1** | 实现 `agent/nodes/interrupt_nodes.py` - 中断节点 | 使用 LangGraph interrupt |
| **6.2** | 实现任务状态持久化 | 中断状态保存到文件/SQLite |
| **6.3** | CLI `huaqi resume [task_id]` 命令 | 能列出和恢复任务 |
| **6.4** | 中断通知机制 | 生成二维码/链接通知用户 |

### 人工验证命令

```bash
# 验证 6.3 - 恢复任务
huaqi chat
# 触发内容生成任务，等待中断
# 输入: resume
# 预期: 显示待确认的内容和选项

# 验证 - 确认发布
huaqi resume task_001
# 选择: confirm
# 预期: 任务继续执行，内容发布
```

---

## 🔨 Phase 7: 人格画像自动更新

**工时**: 1-2天

### 步骤

| 子任务 | 具体工作 | 验证方式 |
|--------|----------|----------|
| **7.1** | 实现 `core/personality/updater.py` - 更新分析器 | 分析日记提取画像变化 |
| **7.2** | 实现确认流程 | 重要变化需用户确认 |
| **7.3** | 定时触发画像更新 | 每周自动分析 |

### 人工验证命令

```bash
# 验证 7.1 - 画像分析
python -c "
from huaqi.core.personality.updater import PersonalityUpdater
from huaqi.core.personality.engine import PersonalityEngine
updater = PersonalityUpdater()
profile = PersonalityEngine().load_profile()
update = updater.analyze_diary_for_updates(diary_entry, profile)
print(f'检测到变化: {update.changes if update else \"无\"}')
"
```

---

## 🔨 Phase 8: 配置热重载与数据迁移

**工时**: 1-2天

### 步骤

| 子任务 | 具体工作 | 验证方式 |
|--------|----------|----------|
| **8.1** | 实现 `config/hot_reload.py` - 热重载监听 | 使用 watchdog 监听文件变化 |
| **8.2** | 各模块支持 on_config_change 回调 | 配置变更后自动生效 |
| **8.3** | 编写 `scripts/migrate_v3_to_v4.py` - 数据迁移 | 旧日记导入向量库 |
| **8.4** | 回滚机制 | 迁移失败可恢复 |

### 人工验证命令

```bash
# 验证 8.1 - 热重载
huaqi daemon start
# 修改 ~/.huaqi/config.yaml
# 预期: 日志显示 "配置热重载完成"

# 验证 8.3 - 数据迁移
python scripts/migrate_v3_to_v4.py
# 预期: 显示迁移进度，完成后向量库可用
```

---

## 📊 整体时间表

```
Week 1: | P1 | P2 (前半) |
        [基础] [向量存储]

Week 2: | P2 (后半) | P3 |
        [向量存储]  [LangGraph]

Week 3: | P4 | P5 (前半) |
        [定时任务] [流水线]

Week 4: | P5 (后半) | P6 | P7 |
        [流水线]    [人机协同] [画像]

Week 5: | P8 | 测试/优化 |
        [热重载] [收尾]
```

---

## 📝 开发规范

1. **每次任务调用 xp mcp 工具**: `search_best_practices` → 开发 → `extract_experience` + `record_session`
2. **每个 Phase 完成后提交代码**: `git add -A && git commit -m "feat: Phase X - 描述"`
3. **保持向后兼容**: 旧功能在新架构下仍能工作
4. **文档同步**: 每完成一个 Phase 更新 IMPLEMENTATION_PLAN.md 进度

---

**文档版本**: 1.0  
**创建时间**: 2025-03-27  
**完成时间**: 2025-03-30
**状态**: 已完成
