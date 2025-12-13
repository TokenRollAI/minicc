from __future__ import annotations

import builtins
import sys
import types
import warnings

import pytest

import minicc.core.mcp as mcp


def test_load_mcp_toolsets_no_config_returns_empty(monkeypatch):
    monkeypatch.setattr(mcp, "find_mcp_config", lambda _: None)
    monkeypatch.setattr(mcp, "_CACHE", {})
    assert mcp.load_mcp_toolsets("/tmp/x") == []


def test_load_mcp_toolsets_caches_by_config_path(monkeypatch):
    monkeypatch.setattr(mcp, "find_mcp_config", lambda _: "/tmp/minicc-mcp.json")
    monkeypatch.setattr(mcp, "_CACHE", {})

    calls = {"n": 0}
    mod = types.ModuleType("pydantic_ai.mcp")

    def load_mcp_servers(_):
        calls["n"] += 1
        return ["toolset-a"]

    mod.load_mcp_servers = load_mcp_servers
    monkeypatch.setitem(sys.modules, "pydantic_ai.mcp", mod)

    a = mcp.load_mcp_toolsets("/tmp/x")
    b = mcp.load_mcp_toolsets("/tmp/x")
    assert a == ["toolset-a"]
    assert b == ["toolset-a"]
    assert calls["n"] == 1


def test_load_mcp_toolsets_import_error_non_strict_warns_and_returns_empty(monkeypatch):
    monkeypatch.setattr(mcp, "find_mcp_config", lambda _: "/tmp/minicc-mcp.json")
    monkeypatch.setattr(mcp, "_CACHE", {})
    monkeypatch.delenv("MINICC_MCP_STRICT", raising=False)
    monkeypatch.setitem(sys.modules, "pydantic_ai.mcp", None)

    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pydantic_ai.mcp":
            raise ImportError("no mcp")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with warnings.catch_warnings(record=True) as rec:
        warnings.simplefilter("always")
        out = mcp.load_mcp_toolsets("/tmp/x")
        assert out == []
        assert any("加载 MCP 失败" in str(w.message) for w in rec)


def test_load_mcp_toolsets_import_error_strict_raises(monkeypatch):
    monkeypatch.setattr(mcp, "find_mcp_config", lambda _: "/tmp/minicc-mcp.json")
    monkeypatch.setattr(mcp, "_CACHE", {})
    monkeypatch.setenv("MINICC_MCP_STRICT", "1")
    monkeypatch.setitem(sys.modules, "pydantic_ai.mcp", None)

    orig_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "pydantic_ai.mcp":
            raise ImportError("no mcp")
        return orig_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    with pytest.raises(RuntimeError):
        mcp.load_mcp_toolsets("/tmp/x")
