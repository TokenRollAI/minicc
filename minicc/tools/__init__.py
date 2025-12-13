"""
MiniCC 工具集合（按职责拆分）

说明：工具对外仅用于 Agent 调用；TUI 的展示由 stream events + 事件总线驱动。
"""

from .registry import register_tools

__all__ = ["register_tools"]

