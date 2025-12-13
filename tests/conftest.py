from __future__ import annotations

import pytest

from minicc.core.events import EventBus
from minicc.core.models import Config, MiniCCDeps, Provider


@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()


@pytest.fixture
def config() -> Config:
    return Config(provider=Provider.ANTHROPIC, model="test-model", api_key="test-key")


@pytest.fixture
def deps(config: Config) -> MiniCCDeps:
    return MiniCCDeps(config=config, cwd="/tmp/minicc-test", fs=None)

