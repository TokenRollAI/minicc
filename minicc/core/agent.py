"""
MiniCC Agent 创建与运行
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.toolsets import AbstractToolset

from .config import get_api_key, load_agents_prompt
from .mcp import load_mcp_toolsets
from .models import Config, MiniCCDeps, Provider


def create_model(config: Config) -> AnthropicModel | OpenAIModel | str:
    api_key = get_api_key(config.provider)

    if config.base_url or config.api_key:
        if config.provider == Provider.ANTHROPIC:
            provider = AnthropicProvider(api_key=api_key, base_url=config.base_url)
            return AnthropicModel(config.model, provider=provider)
        provider = OpenAIProvider(api_key=api_key, base_url=config.base_url)
        return OpenAIModel(config.model, provider=provider)

    if config.provider == Provider.ANTHROPIC:
        return f"anthropic:{config.model}"
    return f"openai:{config.model}"


def _build_model_settings(config: Config) -> dict[str, Any] | None:
    if config.provider != Provider.ANTHROPIC:
        return None

    cache = config.prompt_cache
    settings: dict[str, Any] = {}
    if cache.instructions:
        settings["anthropic_cache_instructions"] = cache.instructions
    if cache.tool_definitions:
        settings["anthropic_cache_tool_definitions"] = cache.tool_definitions
    if cache.messages:
        settings["anthropic_cache_messages"] = cache.messages
    return settings or None


def create_agent(
    config: Config,
    *,
    cwd: str | Path | None = None,
    toolsets: list[AbstractToolset[Any]] | None = None,
    register_tools: Callable[[Agent[MiniCCDeps, str]], None] | None = None,
) -> Agent[MiniCCDeps, str]:
    """
    创建并配置主 Agent

    说明：
    - MCP toolsets 默认在此处加载，但 TUI 运行时会在启动阶段预加载并传入（避免重复加载）。
    - 工具注册通过 register_tools 回调注入（便于拆分 tools 模块）。
    """

    model = create_model(config)
    system_prompt = load_agents_prompt()
    model_settings = _build_model_settings(config)

    if toolsets is None:
        toolsets = load_mcp_toolsets(cwd)

    agent: Agent[MiniCCDeps, str] = Agent(
        model=model,
        deps_type=MiniCCDeps,
        system_prompt=system_prompt,
        model_settings=model_settings,
        toolsets=toolsets,
    )

    if register_tools is not None:
        register_tools(agent)

    return agent


async def run_agent(
    agent: Agent[MiniCCDeps, str],
    prompt: str,
    deps: MiniCCDeps,
    message_history: list | None = None,
) -> tuple[str, list]:
    result = await agent.run(prompt, deps=deps, message_history=message_history or [])
    return result.output, result.all_messages()
