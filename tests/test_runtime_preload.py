from __future__ import annotations

from dataclasses import dataclass

import pytest

import minicc.core.runtime as runtime
from minicc.core.models import Config, Provider


@dataclass
class _DummyFS:
    cwd: str
    auto_watch: bool = True

    def close(self) -> None:
        return None


def test_build_runtime_preloads_mcp_and_passes_toolsets(monkeypatch):
    calls: list[tuple[str, object]] = []
    toolsets = ["ts-1"]

    monkeypatch.setattr(runtime, "load_mcp_toolsets", lambda cwd: toolsets)
    monkeypatch.setattr(runtime, "FileSystem", lambda cwd, auto_watch=True: _DummyFS(cwd=cwd, auto_watch=auto_watch))

    def fake_create_agent(cfg, cwd, toolsets, register_tools):
        calls.append((cwd, toolsets))
        return object()

    monkeypatch.setattr(runtime, "create_agent", fake_create_agent)

    cfg = Config(provider=Provider.ANTHROPIC, model="test-model", api_key="test-key")
    rt = runtime.build_runtime(config=cfg, cwd="/tmp/minicc-test")
    assert rt.toolsets == toolsets
    assert calls == [("/tmp/minicc-test", toolsets)]

    # 子代理 factory 也必须复用启动时预加载的 toolsets（不再懒加载）
    assert rt.deps.subagent_service is not None
    rt.deps.subagent_service.agent_factory()
    assert calls == [("/tmp/minicc-test", toolsets), ("/tmp/minicc-test", toolsets)]
