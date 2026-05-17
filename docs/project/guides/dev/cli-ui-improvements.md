# Huaqi CLI UI 优化文档

本文档记录 Huaqi CLI 的 UI 交互优化改进，提升用户使用体验。

---

## 优化内容概览

| 功能 | 状态 | 说明 |
|------|------|------|
| 中文输入修复 | ✅ 已完成 | 使用 prompt-toolkit 正确处理 UTF-8 字符 |
| 历史记录 | ✅ 已完成 | 支持上下键切换历史输入 |
| 命令补全 | ✅ 已完成 | Tab 键自动补全斜杠命令 |
| 文本补全 | ✅ 已完成 | 从历史中学习中文词组 |
| 多行输入 | ✅ 已完成 | Ctrl+O 或 Esc+Enter 换行 |
| 快捷键支持 | ✅ 已完成 | Ctrl+L 清屏、Ctrl+R 搜索历史 |
| 气泡布局 | ✅ 已完成 | 无边框左右分列、60% 宽度居中 |
| 动态提示符 | ✅ 已完成 | 提示符显示当前对话轮数 |
| 启动去噪 | ✅ 已完成 | 关怀延迟、周报静默、分析提示移除 |

---

## 1. 中文输入修复

### 问题
原生 `input()` 在终端中删除中文字符时会出现光标位置错误，导致无法正确删除。

### 解决方案
使用 `prompt-toolkit` 替代原生 `input()`：

```python
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory

def prompt_input() -> str:
    result = prompt(
        "> ",
        history=FileHistory(str(history_file)),
    )
    return result
```

### 效果
- 中文输入时光标位置正确
- 退格键可正常删除任意字符
- 支持多字节字符的精确处理

---

## 2. 历史记录功能

### 功能说明
用户输入的历史记录会自动保存，支持通过键盘快速浏览和复用。

### 快捷键
| 按键 | 功能 |
|------|------|
| `↑` | 上一条历史记录 |
| `↓` | 下一条历史记录 |
| `Ctrl+R` | 搜索历史记录 |

### 存储位置
- 文件：`~/.huaqi_history`
- 格式：纯文本，每条记录一行

---

## 3. Tab 补全功能

### 3.1 命令补全

输入 `/` 后按 Tab 自动补全可用命令：

```
/help     /reset    /state    /exit
/quit     /clear    /history  /status
```

### 3.2 中文词组补全

系统会自动从历史记录中学习中文词组，输入时按 Tab 可快速补全。

**示例：**
```
用户输入：我叫什么名 [Tab]
系统提示：名字 (1次)
补全结果：我叫什么名字
```

---

## 4. 多行输入

### 快捷键
| 按键 | 功能 |
|------|------|
| `Ctrl+O` | 插入换行符 |
| `Esc + Enter` | 插入换行符 |
| `Enter` | 提交输入 |

---

## 5. 气泡布局（BubbleLayout）

### 概述

`BubbleLayout`（`huaqi_src/core/ui_utils.py`）实现无边框左右分列气泡布局：

- **内容区宽度**：60% 终端宽度，最小 40 字符
- **居中方式**：左右留白 = `(terminal_width - content_width) // 2`
- **AI 消息**：左对齐，`🌸 HH:MM` 前缀 + Markdown 正文
- **用户消息**：右对齐，`HH:MM  👤 你` 标头 + 白色正文
- **所有 Panel 边框已移除**

### 布局示意

```
      │← ─ ─ ─ ─ 60% 终端宽度 ─ ─ ─ →│
      │                                │
      │  🌸 14:22                      │
      │  嗨！很高兴见到你～             │
      │                                │
      │              14:23  👤 你      │
      │              我叫连子蒙        │
      │                                │
🌸 huaqi [2] > _
```

### 中文对齐

用户消息右对齐时使用 `rich.cells.cell_len` 而非 `len()`，正确处理中文双宽字符（每字占 2 列）和 emoji：

```python
from rich.cells import cell_len

body_pad = max(0, right_edge - cell_len(content))
console.print(f"{' ' * body_pad}{content}")
```

### AI 正文右边界约束

AI 的 Markdown 回复通过 `rich.Padding` 同时限制左右边距，防止超出内容列：

```python
from rich.padding import Padding

rp = max(0, terminal_width - lp - content_width)
console.print(Padding(Markdown(response_text), pad=(0, rp, 0, lp)))
```

---

## 6. 动态输入提示符

提示符根据当前对话轮数动态变化：

```
🌸 huaqi >        # 第 0 轮（初始）
🌸 huaqi [1] >    # 第 1 轮后
🌸 huaqi [N] >    # 第 N 轮后
```

`prompt_input()` 接受 `turn_count: int = 0` 参数：

```python
def prompt_input(turn_count: int = 0, ...) -> str:
    if turn_count > 0:
        prompt_message = ANSI(f"\x1b[35m🌸\x1b[0m \x1b[36mhuaqi\x1b[0m \x1b[2m[{turn_count}]\x1b[0m > ")
    else:
        prompt_message = ANSI("\x1b[35m🌸\x1b[0m \x1b[36mhuaqi\x1b[0m > ")
```

---

## 7. 启动流程去噪

### 改动前
启动时同时输出：分析提示 + 关怀消息 + 周报内容，造成视觉噪音。

### 改动后

| 内容 | 改动前 | 改动后 |
|------|--------|--------|
| 分析提示 `💡 正在分析...` | 启动时打印 | 完全移除 |
| 关怀消息 | 启动时打印 | 延迟至第一轮回复后以 `dim italic` 插入 |
| 周报 | 启动时全量打印 | 静默生成，欢迎屏仅显示一行提示 `/report 查看` |

### 欢迎屏结构

```
🌸 Huaqi  ·  你的个人 AI 同伴

今天是周三  ·  共 12 次对话  ·  上次昨天
「让每一次对话都留下痕迹」

📊 本周报告就绪，/report 查看

──────────────────────────────────────
```

---

## 8. 快捷键总览

| 快捷键 | 功能 |
|--------|------|
| `↑ / ↓` | 浏览历史记录 |
| `Tab` | 自动补全 |
| `Ctrl+R` | 反向搜索历史 |
| `Ctrl+C` | 取消当前输入 |
| `Ctrl+O` | 插入换行 |
| `Esc + Enter` | 插入换行 |
| `Ctrl+L` | 清屏 |

---

## 9. 相关文件

| 文件 | 说明 |
|------|------|
| `huaqi_src/core/ui_utils.py` | `BubbleLayout` 类，宽度计算、气泡渲染、欢迎屏 |
| `huaqi_src/cli/ui.py` | `prompt_input()`，动态提示符、快捷键绑定 |
| `huaqi_src/cli/chat.py` | `chat_mode()` / `run_langgraph_chat()`，流式渲染、启动流程 |

---

## 10. 故障排除

### 问题：Tab 补全不工作
历史记录文件为空，词库尚未建立。多输入一些中文内容后词库会自动建立。

### 问题：历史记录丢失
```bash
ls -la ~/.huaqi_history   # 检查文件
touch ~/.huaqi_history    # 如损坏可重置
```

### 问题：中文显示乱码
```bash
export LANG=zh_CN.UTF-8
export LC_ALL=zh_CN.UTF-8
```

### 问题：用户消息右对齐偏移
使用 `rich.cells.cell_len` 替代 `len()` 计算显示宽度，中文字符按 2 列计算。

---

**文档版本**: v2.0
**最后更新**: 2026-03-29
