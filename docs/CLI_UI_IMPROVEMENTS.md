# Huaqi CLI UI 优化文档

本文档记录 Huaqi CLI 的 UI 交互优化改进，提升用户使用体验。

## 优化内容概览

| 功能 | 状态 | 说明 |
|------|------|------|
| 中文输入修复 | ✅ 已完成 | 使用 prompt-toolkit 正确处理 UTF-8 字符 |
| 历史记录 | ✅ 已完成 | 支持上下键切换历史输入 |
| 命令补全 | ✅ 已完成 | Tab 键自动补全斜杠命令 |
| 文本补全 | ✅ 已完成 | 从历史中学习中文词组 |
| 多行输入 | ✅ 已完成 | Ctrl+O 或 Esc+Enter 换行 |
| 快捷键支持 | ✅ 已完成 | Ctrl+L 清屏、Ctrl+R 搜索历史 |

---

## 1. 中文输入修复

### 问题
原生 `input()` 在终端中删除中文字符时会出现光标位置错误，导致无法正确删除。

### 解决方案
使用 `prompt-toolkit` 替代原生 `input()`：

```python
from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory

def _prompt_input() -> str:
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

### 代码实现
```python
from prompt_toolkit.history import FileHistory

_input_history: Optional[FileHistory] = None

def _get_history():
    global _input_history
    if _input_history is None:
        history_file = Path.home() / ".huaqi_history"
        _input_history = FileHistory(str(history_file))
    return _input_history
```

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

### 实现原理

```python
class HuaqiCommandCompleter(Completer):
    def __init__(self):
        self._word_cache: Dict[str, int] = {}  # 词频缓存

    def _extract_words_from_history(self, history: FileHistory):
        """从历史记录中提取中文词组 (2-6字)"""
        word_pattern = re.compile(r'[\u4e00-\u9fa5]{2,6}')
        # 提取并统计词频...

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor

        # 1. 命令补全
        if text.startswith("/"):
            # 返回匹配的命令...

        # 2. 中文词组补全
        # 返回匹配的词组，按频率排序...
```

### 配置参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 最小触发长度 | 1 字 | 输入多少字后开始补全 |
| 词组长度范围 | 2-6 字 | 提取的词组长度范围 |
| 最大补全数 | 无限制 | 显示的补全选项数量 |

---

## 4. 多行输入

### 使用场景
需要输入长文本、换行内容时使用。

### 快捷键
| 按键 | 功能 |
|------|------|
| `Ctrl+O` | 插入换行符 |
| `Esc + Enter` | 插入换行符 |
| `Enter` | 提交输入 |

### 代码实现
```python
@bindings.add("c-o")
def _(event):
    event.current_buffer.insert_text("\n")

@bindings.add("escape", "enter")
def _(event):
    event.current_buffer.insert_text("\n")
```

---

## 5. 快捷键总览

### 输入相关
| 快捷键 | 功能 |
|--------|------|
| `↑ / ↓` | 浏览历史记录 |
| `Tab` | 自动补全 |
| `Ctrl+R` | 反向搜索历史 |
| `Ctrl+C` | 取消当前输入 |
| `Ctrl+O` | 插入换行 |
| `Esc + Enter` | 插入换行 |

### 界面相关
| 快捷键 | 功能 |
|--------|------|
| `Ctrl+L` | 清屏 |

---

## 6. 技术栈

### 核心依赖
```toml
[project.dependencies]
"prompt-toolkit>=3.0.0"
"pygments>=2.15.0"
```

### 关键组件
- `prompt_toolkit.prompt`: 增强版输入函数
- `FileHistory`: 历史记录管理
- `Completer`: 自动补全接口
- `KeyBindings`: 自定义快捷键

---

## 7. 文件变更

### 修改文件
- `cli.py`: 重写 `_prompt_input()` 函数，添加补全器和键绑定
- `pyproject.toml`: 添加 `pygments` 依赖

### 新增文件
- `~/.huaqi_history`: 用户输入历史记录（自动生成）

---

## 8. 故障排除

### 问题：Tab 补全不工作
**原因：**
1. 历史记录文件为空，词库尚未建立
2. 输入内容不在词库中

**解决：**
- 多输入一些中文内容，建立词库
- 词库会在每次输入时自动更新

### 问题：历史记录丢失
**原因：**
- `~/.huaqi_history` 文件被删除或损坏

**解决：**
```bash
# 检查文件是否存在
ls -la ~/.huaqi_history

# 如损坏可重置
touch ~/.huaqi_history
```

### 问题：中文显示乱码
**原因：**
- 终端编码设置不正确

**解决：**
```bash
# 设置 UTF-8 编码
export LANG=zh_CN.UTF-8
export LC_ALL=zh_CN.UTF-8
```

---

## 9. 未来优化方向

- [ ] 模糊搜索：支持拼音首字母搜索历史
- [ ] 智能提示：基于上下文的输入建议
- [ ] 语法高亮：代码块的语法着色
- [ ] 鼠标支持：点击选择补全项

---

*最后更新：2025-03-28*
