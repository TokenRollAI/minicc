from __future__ import annotations

import asyncio

import pytest

from minicc.core.events import EventBus


@pytest.mark.asyncio
async def test_event_bus_next_order():
    bus: EventBus[int] = EventBus()
    bus.emit(1)
    bus.emit(2)
    assert await bus.next() == 1
    assert await bus.next() == 2


@pytest.mark.asyncio
async def test_event_bus_iter_yields_values():
    bus: EventBus[str] = EventBus()

    async def consume_two() -> list[str]:
        out: list[str] = []
        async for ev in bus.iter():
            out.append(ev)
            if len(out) == 2:
                return out
        return out

    task = asyncio.create_task(consume_two())
    bus.emit("a")
    bus.emit("b")
    assert await asyncio.wait_for(task, timeout=1) == ["a", "b"]

