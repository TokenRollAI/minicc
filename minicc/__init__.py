"""
MiniCC - 极简教学版 AI 编程助手

基于 pydantic-ai 和 textual 实现的轻量级 Claude Code 替代品，
用于学习 AI Agent 的核心实现原理。

基本用法:
    $ minicc              # 启动 TUI 界面
    $ python -m minicc    # 等效启动方式

编程接口:
    from minicc import MiniCCApp, create_agent

    # 使用应用
    app = MiniCCApp()
    app.run()

    # 直接使用 Agent
    agent = create_agent(config)
    result = await agent.run("你的问题")

配置:
    配置文件位于 ~/.minicc/config.json
    系统提示词位于 ~/.minicc/AGENTS.md
"""

__version__ = "0.3.1"
__author__ = "MiniCC Contributors"

# 仅对外暴露 TUI 入口
from minicc.cli import main
from minicc.tui.app import MiniCCApp

__all__ = ["__version__", "__author__", "MiniCCApp", "main"]
