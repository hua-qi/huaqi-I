# Huaqi Phase 3 使用指南

> **文档作用**: 本文档提供系统概览与面向开发者的集成使用指南。

## 快速开始

### 1. 安装依赖

```bash
cd /Users/lianzimeng/workspace/huaqi
pip install -e .
```

### 2. 运行演示 CLI

```bash
python demo_phase3.py
```

交互式菜单，可以体验：
- 个性引擎：选择预设、调整个性参数
- Hook 系统：查看/触发 Hooks、创建自定义 Hook
- 成长系统：添加技能、记录练习、管理目标

---

## 在项目中使用 Phase 3

### 1. 基础使用（单个功能）

```python
from pathlib import Path
from huaqi.core.personality import PersonalityEngine
from huaqi.core.hooks import HookManager, EventType
from huaqi.core.growth import GrowthTracker

DATA_DIR = Path.home() / ".huaqi"
USER_ID = "my_user"

# ===== 个性引擎 =====
personality = PersonalityEngine(DATA_DIR, USER_ID)

# 获取系统提示词
prompt = personality.get_system_prompt()
print(prompt)

# 应用预设（companion/mentor/friend/assistant）
personality.apply_preset("mentor")

# 自定义参数
personality.update_profile(
    tone="warm",
    empathy=0.9,
    humor=0.5
)

# ===== Hook 系统 =====
hook_mgr = HookManager(DATA_DIR, USER_ID)

# 列出所有 Hooks
for hook in hook_mgr.list_hooks():
    print(f"{hook.name}: {hook.description}")

# 手动触发事件
hook_mgr.trigger_event(EventType.MEMORY_CREATED, {
    "memory_type": "insight"
})

# 启动后台调度器（检查定时 Hooks）
hook_mgr.start_scheduler(interval_seconds=60)

# ===== 成长系统 =====
growth = GrowthTracker(DATA_DIR, USER_ID)

# 添加技能
skill = growth.add_skill("Python", "coding", "进阶", "精通")

# 记录练习
growth.record_practice("Python", 2.5, "完成了 CLI 开发")

# 添加目标
goal = growth.add_goal(
    title="掌握 Python",
    description="能够独立开发完整项目",
    category="short_term"
)

# 更新进度
growth.update_goal_progress(goal.id, 75)

# 生成周报
report = growth.generate_weekly_report()
print(f"本周对话: {report.conversations} 次")
```

### 2. 完整对话体验（V3 管理器）

```python
from pathlib import Path
from huaqi.core.config import init_config_manager
from huaqi.core.conversation_v3 import ConversationManagerV3

DATA_DIR = Path.home() / ".huaqi"
USER_ID = "my_user"

# 初始化配置
config = init_config_manager(DATA_DIR)
config.switch_user(USER_ID)

# 创建 V3 对话管理器（自动集成 Phase 3）
conversation = ConversationManagerV3(
    config_manager=config,
    user_id=USER_ID,
    data_dir=DATA_DIR
)

# 查看 Phase 3 状态
stats = conversation.get_stats()
print(f"个性角色: {stats['personality']['role']}")
print(f"Hooks数量: {stats['hooks']}")
print(f"技能数量: {stats['skills']}")

# 开始对话
response = conversation.chat("今天心情不错，刚完成了一个项目！")
print(response)

# 流式输出
for chunk in conversation.chat("讲个笑话吧", stream=True):
    print(chunk, end="")

# 结束会话（自动触发总结事件）
summary = conversation.end_session()
print(f"会话共 {summary['turns']} 轮，持续 {summary['duration_minutes']:.1f} 分钟")
```

### 3. 启动 Hook 调度器（后台服务）

**方式一：独立进程**

```bash
# 启动调度器（每60秒检查一次）
python -m huaqi.core.scheduler --user my_user --interval 60

# 或使用脚本
cd /Users/lianzimeng/workspace/huaqi
python huaqi/core/scheduler.py --user my_user
```

**方式二：在应用中集成**

```python
from huaqi.core.scheduler import HookSchedulerService, SchedulerConfig

config = SchedulerConfig(interval_seconds=60)
scheduler = HookSchedulerService(DATA_DIR, USER_ID, config)

# 后台启动
scheduler.start(blocking=False)

# ... 应用运行中 ...

# 应用关闭时
scheduler.stop()
```

---

## 完整工作流示例

```python
#!/usr/bin/env python3
"""Huaqi Phase 3 完整工作流示例"""

from pathlib import Path
from huaqi.core.config import init_config_manager
from huaqi.core.conversation_v3 import ConversationManagerV3
from huaqi.core.scheduler import HookSchedulerService, SchedulerConfig

DATA_DIR = Path.home() / ".huaqi"
USER_ID = "demo_user"

# 1. 初始化
config = init_config_manager(DATA_DIR)
config.switch_user(USER_ID)

# 2. 启动 Hook 调度器（后台）
scheduler = HookSchedulerService(
    DATA_DIR, 
    USER_ID,
    SchedulerConfig(interval_seconds=60)
)
scheduler.start(blocking=False)

# 3. 创建对话管理器
conversation = ConversationManagerV3(
    config_manager=config,
    user_id=USER_ID
)

# 4. 配置个性（可选）
conversation.personality.apply_preset("companion")
conversation.personality.update_profile(
    tone="warm",
    empathy=0.9
)

# 5. 添加技能和目标（可选）
conversation.growth.add_skill("Python", "coding", "进阶", "精通")
goal = conversation.growth.add_goal(
    "完成 Huaqi Phase 3",
    "实现所有核心功能",
    "short_term"
)

# 6. 开始对话
print("🌸 Huaqi: 嗨！很高兴见到你。今天想聊点什么？")

while True:
    user_input = input("\n你: ").strip()
    
    if user_input.lower() in ("exit", "quit", "退出"):
        break
    
    if user_input.lower() == "status":
        stats = conversation.get_stats()
        print(f"\n[Huaqi状态] 角色:{stats['personality']['role']} | Hooks:{stats['hooks']} | 技能:{stats['skills']}")
        continue
    
    # 对话
    response = conversation.chat(user_input)
    print(f"\n🌸 Huaqi: {response}")
    
    # 记录技能练习（如果提到）
    if "学习" in user_input or "练习" in user_input:
        conversation.growth.record_practice("Python", 1.0)
        print("[成长系统] 已记录 1 小时练习时间")

# 7. 结束
summary = conversation.end_session()
print(f"\n[会话总结] {summary['turns']} 轮对话，{summary['duration_minutes']:.1f} 分钟")

# 更新目标进度
conversation.growth.update_goal_progress(goal.id, 100)
print("[成长系统] 目标进度更新为 100%")

# 停止调度器
scheduler.stop()
print("再见！👋")
```

---

## 数据存储

所有数据存储在 `~/.huaqi/users_data/{user_id}/` 下：

```
~/.huaqi/
├── users_data/
│   └── {user_id}/
│       ├── config/
│       │   └── personality.yaml    # 个性配置
│       ├── hooks/
│       │   ├── morning-greeting.json
│       │   ├── daily-summary.json
│       │   └── memory-insight.json
│       ├── growth/
│       │   ├── skills.yaml         # 技能追踪
│       │   └── goals.yaml          # 目标管理
│       ├── memory/
│       │   ├── identity/
│       │   ├── patterns/
│       │   └── conversations/      # 对话历史
│       └── ...
```

---

## 进阶配置

### 自定义 Hook

```python
from huaqi.core.hooks import Hook, TriggerType

my_hook = Hook(
    id="my-reminder",
    name="我的提醒",
    description="每天晚上8点提醒",
    trigger_type=TriggerType.SCHEDULE,
    trigger_config={
        "type": "daily",
        "time": "20:00"
    },
    conditions=[],
    actions=[
        {
            "type": "send_message",
            "params": {
                "message": "该休息一下了！"
            }
        }
    ]
)

hook_mgr.create_hook(my_hook)
```

### LLM 集成

```python
from huaqi.core.llm import init_llm_manager, LLMConfig

llm = init_llm_manager()

# 添加配置
llm.add_config(LLMConfig(
    provider="claude",
    model="claude-3-sonnet",
    api_key="your-api-key"
))

# 设置为默认
llm.set_active("claude")
```

---

## 常见问题

**Q: 如何重置所有数据？**
```bash
rm -rf ~/.huaqi
```

**Q: 如何查看 Hook 执行日志？**
Hook 执行会输出到控制台，可以在启动调度器时重定向到文件：
```bash
python -m huaqi.core.scheduler > hook.log 2>&1 &
```

**Q: 如何禁用某个 Hook？**
```python
hook_mgr.disable_hook("morning-greeting")
```

**Q: 如何导出成长数据？**
```python
growth_summary = conversation.growth.generate_growth_summary()
print(growth_summary)
```
