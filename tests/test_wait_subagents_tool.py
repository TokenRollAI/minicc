from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from minicc.core.events import EventBus
from minicc.core.models import Config, MiniCCDeps, Provider
from minicc.core.services.subagents import SubAgentService
from minicc.tools.task import task as task_tool
from minicc.tools.task import wait_subagents


@dataclass
class _DummyResult:
    output: str


class _DummyAgent:
    async def run(self, prompt: str, deps=None):
        await asyncio.sleep(0.01)
        return _DummyResult(output=f"done:{prompt}")


@dataclass
class _Ctx:
    deps: MiniCCDeps


def _deps() -> MiniCCDeps:
    cfg = Config(provider=Provider.ANTHROPIC, model="test-model", api_key="test-key")
    return MiniCCDeps(config=cfg, cwd="/tmp/minicc-test", fs=None)


@pytest.mark.asyncio
async def test_wait_subagents_no_tasks_returns_message():
    deps = _deps()
    ctx = _Ctx(deps=deps)
    result = await wait_subagents(ctx)
    assert result.success is True
    assert "没有" in result.output


@pytest.mark.asyncio
async def test_task_wait_false_then_wait_subagents_returns_summary():
    deps = _deps()
    bus = EventBus()

    service = SubAgentService(
        deps=deps,
        event_bus=bus,
        agent_factory=lambda: _DummyAgent(),
    )
    deps.subagent_service = service

    ctx = _Ctx(deps=deps)

    r1 = await task_tool(ctx, prompt="P1", description="D1", wait=False)
    r2 = await task_tool(ctx, prompt="P2", description="D2", wait=False)
    assert r1.success and r2.success
    assert "已创建子任务" in r1.output

    summary = await wait_subagents(ctx)
    assert summary.success is True
    assert "D1" in summary.output
    assert "D2" in summary.output
    assert "(completed)" in summary.output
    assert "done:P1" in summary.output
    assert "done:P2" in summary.output

