# 记忆导入指南

> **文档作用**: 本文档介绍如何将外部已有的文本、日志等内容结构化地导入系统的记忆库。
> 如何将你的现有文档导入 Huaqi 记忆库

---

## 支持的文件格式

| 格式 | 扩展名 | 状态 | 说明 |
|------|--------|------|------|
| **Markdown** | `.md`, `.markdown` | ✅ 支持 | 笔记、文档首选 |
| **PDF** | `.pdf` | ✅ 支持 | 需安装 `pdfplumber` |
| **Word** | `.docx`, `.doc` | ✅ 支持 | 需安装 `python-docx` |
| **纯文本** | `.txt`, `.rst` | 🔜 即将支持 | 简单文本文件 |
| **Excel** | `.xlsx`, `.csv` | 🔜 即将支持 | 表格数据 |
| **代码文件** | `.py`, `.js`, etc. | 🔜 即将支持 | 自动提取注释 |
| **图片** | `.png`, `.jpg` | 🔜 即将支持 | OCR 文字识别 |

---

## 快速导入

### 1. 导入单个文件

```bash
huaqi import /path/to/your/document.md
```

### 2. 批量导入整个目录

```bash
huaqi import /path/to/documents/
```

### 3. 预览导入结果（不实际导入）

```bash
huaqi import /path/to/documents/ --dry-run
```

### 4. 使用交互式向导

```bash
huaqi import --wizard
```

---

## 智能分类

导入时，Huaqi 会自动根据内容判断记忆类型：

| 记忆类型 | 触发关键词 | 存储位置 |
|----------|-----------|----------|
| **identity** | about, me, profile, 个人, 简介 | `memory/learning/identity/` |
| **project** | project, 项目, work, 工作 | `memory/working/projects/` |
| **skill** | learn, skill, 学习, guitar, 英语 | `memory/learning/skills/` |
| **insight** | 顿悟、思考、总结 | `memory/learning/insights/` |
| **note** | 其他 | `memory/working/notes/` |

你也可以手动指定类型：

```bash
huaqi import document.md --type project --tags "AI,learning"
```

---

## 存储格式

所有记忆以 **Markdown 格式** 存储，包含：
- **YAML Frontmatter**: 元数据（类型、标签、时间等）
- **Markdown 正文**: 人类可读的内容

### 示例

```markdown
---
type: project
title: 项目规划
imported_at: 2026-03-24T10:30:00
tags: [work, ai]
---

# 项目规划

**类型**: project  
**来源**: /Users/me/Documents/plan.md  
**导入时间**: 2026-03-24T10:30:00  
**标签**: work, ai  

---

## 内容

原始文档内容...
```

---

## 导入流程

```
┌──────────────────────────────────────────────────────┐
│ 1. 选择文件/目录                                      │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│ 2. 提取文本内容                                       │
│    - Markdown: 直接读取                              │
│    - PDF: pdfplumber 提取                            │
│    - Word: python-docx 提取                          │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│ 3. 智能分类 (LLM 辅助)                                │
│    - 分析内容主题                                    │
│    - 判断记忆类型                                    │
│    - 提取关键标签                                    │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│ 4. 提取洞察                                           │
│    - 提取关键信息                                    │
│    - 生成摘要                                        │
│    - 识别重要概念                                    │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│ 5. 保存到记忆库                                       │
│    - 写入 Markdown 文件                              │
│    - 生成向量嵌入                                    │
│    - 建立索引                                        │
└──────────────────────────────────────────────────────┘
```

---

## 批量导入最佳实践

### 1. 整理源文件

```
documents/
├── about/              # 个人相关
│   ├── intro.md
│   └── values.md
├── projects/           # 项目相关
│   ├── project-a/
│   └── project-b/
├── learning/           # 学习笔记
│   ├── guitar/
│   └── english/
└── notes/              # 其他笔记
```

### 2. 逐步导入

```bash
# 先导入个人资料
huaqi import documents/about/ --tags "identity,core"

# 再导入项目文档
huaqi import documents/projects/ --tags "work,project"

# 最后导入学习笔记
huaqi import documents/learning/ --tags "skill,learning"
```

### 3. 验证导入结果

```bash
huaqi memory status
huaqi memory search "电吉他"
```

---

## 冲突处理

如果文件已存在，Huaqi 提供以下策略：

| 策略 | 说明 |
|------|------|
| **skip** (默认) | 跳过已存在的文件 |
| **overwrite** | 覆盖现有文件 |
| **rename** | 重命名新文件 |
| **ask** | 询问用户 |

配置冲突策略：

```bash
huaqi config set import.conflict_strategy ask
```

---

## 从常见工具导入

### Obsidian

```bash
# 导入整个 Obsidian 库
huaqi import ~/Library/Mobile\ Documents/iCloud~md~obsidian/Documents/Vault/
```

### Notion

```bash
# 1. 从 Notion 导出为 Markdown
# 2. 解压导出文件
# 3. 导入
huaqi import ~/Downloads/Export-*/ --wizard
```

### 印象笔记 (Evernote)

```bash
# 1. 导出为 .enex
# 2. 使用工具转换为 Markdown
# 3. 导入
```

### Apple Notes

```bash
# 1. 使用第三方工具导出
# 2. 导入 Markdown 文件
```

---

## 导入后的下一步

### 1. 同步到云端

```bash
huaqi config sync push
```

### 2. 与 AI 对话

```bash
huaqi chat
# > 我记得我学过电吉他，现在进展如何？
```

### 3. 持续更新

```bash
# 设置自动同步（可选）
huaqi config set sync.auto true
```

---

## 故障排除

### PDF 导入失败

```bash
# 安装依赖
pip install pdfplumber

# 或使用替代方案
pip install PyPDF2
```

### Word 导入失败

```bash
pip install python-docx
```

### 中文乱码

确保文件使用 UTF-8 编码：

```bash
# 转换文件编码
iconv -f GBK -t UTF-8 input.txt > output.txt
```

---

## 相关命令

| 命令 | 说明 |
|------|------|
| `huaqi import <path>` | 导入文件或目录 |
| `huaqi import --wizard` | 交互式导入向导 |
| `huaqi import --dry-run` | 预览导入结果 |
| `huaqi memory search <query>` | 搜索记忆 |
| `huaqi memory status` | 查看记忆库状态 |
| `huaqi memory review` | 回顾今日记忆 |

---

*最后更新: 2026-03-24*
