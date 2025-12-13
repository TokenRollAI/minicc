from __future__ import annotations

import os
from dataclasses import dataclass

from agent_gear import FileSystem

from minicc.core.agent import create_agent
from minicc.core.events import EventBus
from minicc.core.mcp import load_mcp_toolsets
from minicc.core.models import Config, MiniCCDeps
from minicc.core.services.ask_user import AskUserService
from minicc.core.services.subagents import SubAgentService
from minicc.tools import register_tools


@dataclass
class MiniCCRuntime:
    config: Config
    cwd: str
    deps: MiniCCDeps
    agent: object
    event_bus: EventBus
    fs: FileSystem
    toolsets: list

    def close(self) -> None:
        try:
            self.fs.close()
        except Exception:
            pass


def build_runtime(config: Config | None = None, cwd: str | None = None) -> MiniCCRuntime:
    cwd = cwd or os.getcwd()
    cfg = config or Config()

    event_bus: EventBus = EventBus()
    toolsets = load_mcp_toolsets(cwd)

    fs = FileSystem(cwd, auto_watch=True)

    deps = MiniCCDeps(config=cfg, cwd=cwd, fs=fs)
    deps.event_bus = event_bus
    deps.ask_user_service = AskUserService(event_bus)

    def _subagent_factory():
        return create_agent(cfg, cwd=cwd, toolsets=toolsets, register_tools=register_tools)

    deps.subagent_service = SubAgentService(deps=deps, event_bus=event_bus, agent_factory=_subagent_factory)

    agent = create_agent(cfg, cwd=cwd, toolsets=toolsets, register_tools=register_tools)
    return MiniCCRuntime(config=cfg, cwd=cwd, deps=deps, agent=agent, event_bus=event_bus, fs=fs, toolsets=toolsets)

