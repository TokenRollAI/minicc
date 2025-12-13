from __future__ import annotations

import asyncio
from dataclasses import dataclass
from uuid import uuid4

from minicc.core.events import AskUserRequested
from minicc.core.models import AskUserResponse, UserCancelledError


@dataclass
class AskUserResult:
    submitted: bool
    answers: dict[str, str | list[str]]


class AskUserService:
    def __init__(self, event_bus) -> None:
        self._bus = event_bus
        self._pending: dict[str, asyncio.Future[AskUserResult]] = {}

    async def ask(self, questions) -> AskUserResult:
        request_id = uuid4().hex[:8]
        fut: asyncio.Future[AskUserResult] = asyncio.get_running_loop().create_future()
        self._pending[request_id] = fut
        self._bus.emit(AskUserRequested(request_id=request_id, questions=questions))
        result = await fut
        if not result.submitted:
            raise UserCancelledError("用户取消了操作")
        return result

    def resolve(self, request_id: str, submitted: bool, answers: dict[str, str | list[str]]) -> None:
        fut = self._pending.pop(request_id, None)
        if fut is None or fut.done():
            return
        fut.set_result(AskUserResult(submitted=submitted, answers=answers))

