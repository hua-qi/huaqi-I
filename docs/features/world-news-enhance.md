# world-news-enhance

> 优化世界新闻采集产出：中英对照 + 链接 + 摘要 + TELOS 个性化重点关注建议。

**Spec:** `docs/specs/world-news-enhance.md`
**Plan:** `docs/plans/world-news-enhance.md`

## 设计要点

### 个性化重点关注判断

使用 TELOS 全部 8 个维度的用户画像（信念、心理模型、自我叙事、目标、挑战、策略、所学、盲点），注入到 LLM 增强 prompt 中，让模型以「这条新闻和这个用户有什么关系」为标准判断关注优先级。

### 数据流

```
CLI (world.py)
  ├─ WorldPipeline.run() → RSSSource.fetch() → content 含链接 → Storage.save()
  ├─ _load_user_context() → TelosManager.list_active() → 8 维度文本
  └─ WorldNewsEnricher.enrich_file(path, user_context=ctx)
      ├─ _build_user_context_section(snapshot) → 清理 frontmatter 噪音
      ├─ _ENRICH_PROMPT.format(raw_content, user_context)
      └─ LLM 输出 → 覆写 world 文件

WorldProvider.get_context()
  └─ _extract_for_report(content) → 优先返回「重点关注建议」板块
```

### 降级路径

- TELOS 目录不存在 / 无数据 → `user_context` 为 None → LLM 回退到通用新闻重要性判断
- LLM 调用失败 → 保留原始内容，不崩溃
- 空文件 → 直接返回 False，不调用 LLM

## 关键决策

- **全 8 维度注入**（非仅 4 个）：用户画像越完整，LLM 判断越精准
- **报告优先展示建议**：WorldProvider 用正则提取「重点关注建议」板块，而非简单截断
- **enricher 不依赖 TELOS**：通过 `user_context` 参数注入，保持单向依赖方向

## 涉及文件

| 文件 | 变更类型 |
|------|---------|
| `huaqi_src/layers/data/world/sources/rss_source.py` | Modify - content 加链接 |
| `huaqi_src/layers/capabilities/world_news_enricher.py` | Modify - 重写 prompt + user_context |
| `huaqi_src/cli/commands/world.py` | Modify - 加载 TELOS 并传入 |
| `huaqi_src/layers/capabilities/reports/providers/world.py` | Modify - 智能提取 |
| `tests/unit/layers/data/world/test_rss_source.py` | Create |
| `tests/unit/layers/capabilities/test_world_news_enricher.py` | Create |
| `tests/unit/cli/commands/test_world_command.py` | Modify |
| `tests/unit/layers/data/world/test_world_provider.py` | Modify |
| `tests/smoke_test.py` | Modify - TestWorldNewsEnhance |
