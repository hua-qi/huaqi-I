#!/usr/bin/env python3
"""Huaqi UI 演示

展示新的 CLI 界面效果
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from rich.console import Console
from huaqi_src.core.ui_utils import HuaqiUI, get_ui, HuaqiTheme

console = Console()


def main():
    ui = get_ui(console)
    
    # 1. 欢迎界面
    ui.show_welcome(version="0.1.0")
    
    # 2. 状态卡片
    ui.show_header("当前状态", ui.theme.EMOJI_TARGET)
    ui.show_status_card("成长概览", {
        "技能数": "5",
        "总时长": "128.5h",
        "进行中目标": "3",
        "已完成目标": "2",
    }, ui.theme.EMOJI_FIRE)
    ui.blank_line()
    
    # 3. 对话示例
    ui.user_message("今天学习了 Python 的异步编程，感觉收获很大！")
    ui.bot_message("太棒了！🎉 异步编程是 Python 高阶技能之一。\n\n你目前累计学习 Python 已经达到 **45 小时**，正在稳步向「进阶」等级迈进。\n\n有什么具体的收获想分享吗？或者遇到了什么难点？")
    
    # 4. 提示和帮助
    ui.blank_line()
    ui.show_command_help({
        "/skill <名称>": "添加新技能",
        "/goal <标题>": "设定新目标", 
        "/log <技能> <时长>": "记录练习时间",
        "/status": "查看详细状态",
        "/help": "显示完整帮助",
        "exit": "退出对话",
    })
    
    # 5. 反馈消息
    ui.success("技能「Python」已成功添加！")
    ui.info("建议设定一个具体的学习目标")
    ui.warning("距离上次练习已经过去 3 天了")
    ui.tip("可以尝试使用 asyncio 写一个小项目")
    
    # 6. 引用
    ui.blank_line()
    ui.show_quote(
        "不是使用 AI，而是养育 AI。让每一次对话都留下痕迹。",
        "Huaqi 设计理念"
    )


if __name__ == "__main__":
    main()
