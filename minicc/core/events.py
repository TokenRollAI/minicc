from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, AsyncIterator, Generic, TypeVar

T = TypeVar("T")


class EventBus(Generic[T]):
    """简单的单消费者事件总线（asyncio.Queue）。"""

    def __init__(self) -> None:
        self._queue: asyncio.Queue[T] = asyncio.Queue()

    def emit(self, event: T) -> None:
        self._queue.put_nowait(event)

    async def next(self) -> T:
        return await self._queue.get()

    async def iter(self) -> AsyncIterator[T]:
        while True:
            yield await self.next()


@dataclass(frozen=True)
class ToolCallStarted:
    tool_call_id: str
    tool_name: str
    args: dict[str, Any] | None


@dataclass(frozen=True)
class ToolCallFinished:
    tool_call_id: str
    tool_name: str
    ok: bool
    content: Any
    error: str | None = None


@dataclass(frozen=True)
class TodoUpdated:
    todos: list[Any]


@dataclass(frozen=True)
class AskUserRequested:
    request_id: str
    questions: list[Any]


@dataclass(frozen=True)
class AskUserResolved:
    request_id: str
    submitted: bool
    answers: dict[str, str | list[str]]


@dataclass(frozen=True)
class SubAgentCreated:
    task_id: str
    description: str
    prompt: str


@dataclass(frozen=True)
class SubAgentUpdated:
    task_id: str
    status: str
    result: str | None = None
