"""
MiniCC MCP（Model Context Protocol）预加载

目标：
- 程序启动时就加载 MCP servers，并将 toolsets 传给 Agent（不再运行中动态/懒加载）。
- 缺少可选依赖时，默认降级为空 toolsets（可通过环境变量开启严格模式）。
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Any

from pydantic_ai.toolsets import AbstractToolset

from .config import find_mcp_config

_CACHE: dict[str, list[AbstractToolset[Any]]] = {}


def load_mcp_toolsets(cwd: str | Path | None) -> list[AbstractToolset[Any]]:
    base = cwd if cwd is not None else os.getcwd()
    config_path = find_mcp_config(base)
    if not config_path:
        return []

    cache_key = str(Path(config_path).resolve())
    cached = _CACHE.get(cache_key)
    if cached is not None:
        return cached

    strict = os.environ.get("MINICC_MCP_STRICT") == "1"

    try:
        from pydantic_ai.mcp import load_mcp_servers
    except Exception as e:
        msg = f"加载 MCP 失败：未安装 MCP 依赖或导入异常：{e}"
        if strict:
            raise RuntimeError(msg) from e
        warnings.warn(msg)
        _CACHE[cache_key] = []
        return []

    try:
        servers = load_mcp_servers(Path(config_path))
        toolsets = list(servers or [])
    except Exception as e:
        msg = f"加载 MCP 失败：配置文件 {config_path} 解析/展开环境变量异常：{e}"
        if strict:
            raise RuntimeError(msg) from e
        warnings.warn(msg)
        toolsets = []

    _CACHE[cache_key] = toolsets
    return toolsets

