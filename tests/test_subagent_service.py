from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

from minicc.core.events import EventBus, SubAgentCreated, SubAgentUpdated
from minicc.core.models import Config, MiniCCDeps, Provider
from minicc.core.services.subagents import SubAgentService


@dataclass
class _DummyResult:
    output: str


class _DummyAgent:
    def __init__(self, output: str, delay: float = 0.0):
        self._output = output
        self._delay = delay

    async def run(self, prompt: str, deps=None):
        if self._delay:
            await asyncio.sleep(self._delay)
        return _DummyResult(output=f"{self._output}:{prompt}")


def _make_deps() -> MiniCCDeps:
    cfg = Config(provider=Provider.ANTHROPIC, model="test-model", api_key="test-key")
    return MiniCCDeps(config=cfg, cwd="/tmp/minicc-test", fs=None)


@pytest.mark.asyncio
async def test_subagent_service_foreground_emits_events_and_returns_result():
    deps = _make_deps()
    bus: EventBus = EventBus()

    service = SubAgentService(
        deps=deps,
        event_bus=bus,
        agent_factory=lambda: _DummyAgent("ok"),
    )

    task_id, result = await service.run(prompt="P", description="D", background=False)
    assert result == "ok:P"
    assert deps.sub_agents[task_id].status == "completed"
    assert deps.sub_agents[task_id].result == "ok:P"

    ev1 = await asyncio.wait_for(bus.next(), timeout=1)
    ev2 = await asyncio.wait_for(bus.next(), timeout=1)
    ev3 = await asyncio.wait_for(bus.next(), timeout=1)
    ev4 = await asyncio.wait_for(bus.next(), timeout=1)

    assert isinstance(ev1, SubAgentCreated)
    assert ev1.task_id == task_id
    assert isinstance(ev2, SubAgentUpdated) and ev2.status == "pending"
    assert isinstance(ev3, SubAgentUpdated) and ev3.status == "running"
    assert isinstance(ev4, SubAgentUpdated) and ev4.status == "completed"


@pytest.mark.asyncio
async def test_subagent_service_background_tracks_task_and_cleans_up():
    deps = _make_deps()
    bus: EventBus = EventBus()

    service = SubAgentService(
        deps=deps,
        event_bus=bus,
        agent_factory=lambda: _DummyAgent("ok", delay=0.01),
    )

    task_id, result = await service.run(prompt="P", description="D", background=True)
    assert result is None
    assert task_id in deps.sub_agent_tasks

    await asyncio.wait_for(deps.sub_agent_tasks[task_id], timeout=1)
    assert task_id not in deps.sub_agent_tasks
    assert deps.sub_agents[task_id].status in ("completed", "failed")

