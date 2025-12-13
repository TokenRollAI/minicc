from __future__ import annotations

import asyncio

import pytest

from minicc.core.events import AskUserRequested, EventBus
from minicc.core.models import Question, QuestionOption, UserCancelledError
from minicc.core.services.ask_user import AskUserService


@pytest.mark.asyncio
async def test_ask_user_emits_event_and_resolves():
    bus: EventBus = EventBus()
    service = AskUserService(bus)

    questions = [
        Question(
            question="Q1",
            header="H1",
            options=[QuestionOption(label="A")],
            multi_select=False,
        )
    ]

    async def runner():
        return await service.ask(questions)

    t = asyncio.create_task(runner())
    ev = await asyncio.wait_for(bus.next(), timeout=1)
    assert isinstance(ev, AskUserRequested)
    assert ev.questions[0].header == "H1"

    service.resolve(ev.request_id, submitted=True, answers={"H1": "A"})
    result = await asyncio.wait_for(t, timeout=1)
    assert result.answers == {"H1": "A"}


@pytest.mark.asyncio
async def test_ask_user_cancel_raises():
    bus: EventBus = EventBus()
    service = AskUserService(bus)

    questions = [
        Question(
            question="Q1",
            header="H1",
            options=[QuestionOption(label="A")],
            multi_select=False,
        )
    ]

    async def runner():
        await service.ask(questions)

    t = asyncio.create_task(runner())
    ev = await asyncio.wait_for(bus.next(), timeout=1)
    assert isinstance(ev, AskUserRequested)

    service.resolve(ev.request_id, submitted=False, answers={})
    with pytest.raises(UserCancelledError):
        await asyncio.wait_for(t, timeout=1)

