"""
MiniCC Agent 定义

使用 pydantic-ai 创建和配置 Agent，支持 Anthropic 和 OpenAI 后端。
"""

from dataclasses import dataclass, field
from typing import Any

from pydantic_ai import Agent
from pydantic_ai.models.anthropic import AnthropicModel
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.openai import OpenAIProvider

from .config import get_api_key, load_agents_prompt
from .schemas import Config, MiniCCDeps, Provider
from . import tools


def create_model(config: Config) -> AnthropicModel | OpenAIModel | str:
    """
    根据配置创建模型

    支持自定义 base_url 用于代理服务。

    Args:
        config: 应用配置

    Returns:
        模型实例或标识符字符串
    """
    api_key = get_api_key(config.provider)

    # 如果有自定义 base_url 或 api_key，使用 Provider 类
    if config.base_url or config.api_key:
        if config.provider == Provider.ANTHROPIC:
            provider = AnthropicProvider(
                api_key=api_key,
                base_url=config.base_url
            )
            return AnthropicModel(config.model, provider=provider)
        else:  # OpenAI
            provider = OpenAIProvider(
                api_key=api_key,
                base_url=config.base_url
            )
            return OpenAIModel(config.model, provider=provider)

    # 否则使用字符串格式（使用环境变量中的 API key）
    if config.provider == Provider.ANTHROPIC:
        return f"anthropic:{config.model}"
    else:
        return f"openai:{config.model}"


def create_agent(config: Config) -> Agent[MiniCCDeps, str]:
    """
    创建并配置主 Agent

    注册所有工具函数，配置模型和系统提示词。

    Args:
        config: 应用配置

    Returns:
        配置好的 Agent 实例
    """
    model = create_model(config)
    system_prompt = load_agents_prompt()

    agent: Agent[MiniCCDeps, str] = Agent(
        model=model,
        deps_type=MiniCCDeps,
        system_prompt=system_prompt,
    )

    # 注册所有工具
    # 文件操作
    agent.tool(tools.read_file)
    agent.tool(tools.write_file)
    agent.tool(tools.update_file)

    # 搜索
    agent.tool(tools.search_files)
    agent.tool(tools.grep)

    # 命令行
    agent.tool(tools.bash)

    # SubAgent
    agent.tool(tools.spawn_agent)
    agent.tool(tools.get_agent_result)
    agent.tool(tools.wait_sub_agents)

    return agent


async def run_agent(
    agent: Agent[MiniCCDeps, str],
    prompt: str,
    deps: MiniCCDeps,
    message_history: list | None = None
) -> tuple[str, list]:
    """
    运行 Agent 并返回结果

    非流式版本，用于子 Agent 执行。

    Args:
        agent: Agent 实例
        prompt: 用户输入
        deps: 依赖注入
        message_history: 历史消息列表

    Returns:
        (响应文本, 更新后的消息历史)
    """
    result = await agent.run(
        prompt,
        deps=deps,
        message_history=message_history or []
    )
    return result.output, result.all_messages()
