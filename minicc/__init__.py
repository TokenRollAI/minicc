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

__version__ = "0.1.0"
__author__ = "MiniCC Contributors"

from .app import MiniCCApp, main
from .agent import create_agent, run_agent
from .schemas import MiniCCDeps
from .config import (
    load_config,
    save_config,
    load_agents_prompt,
    get_api_key,
    CONFIG_DIR,
    CONFIG_FILE,
    AGENTS_FILE,
)
from .schemas import (
    Config,
    Provider,
    ToolResult,
    DiffLine,
    AgentTask,
    Message,
    ToolCall,
)

__all__ = [
    # 版本信息
    "__version__",
    "__author__",
    # 应用入口
    "MiniCCApp",
    "main",
    # Agent 相关
    "MiniCCDeps",
    "create_agent",
    "run_agent",
    # 配置相关
    "load_config",
    "save_config",
    "load_agents_prompt",
    "get_api_key",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "AGENTS_FILE",
    # 数据模型
    "Config",
    "Provider",
    "ToolResult",
    "DiffLine",
    "AgentTask",
    "Message",
    "ToolCall",
]
