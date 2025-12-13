"""
MiniCC 配置管理

处理 ~/.minicc 目录下的配置文件与系统提示词（AGENTS.md）。
"""

from __future__ import annotations

import os
from pathlib import Path

from .models import Config, Provider

# 配置文件路径
CONFIG_DIR = Path.home() / ".minicc"
CONFIG_FILE = CONFIG_DIR / "config.json"
AGENTS_FILE = CONFIG_DIR / "AGENTS.md"
MCP_CONFIG_FILE = CONFIG_DIR / "mcp.json"

# 项目级 MCP 配置位置：<cwd>/.minicc/mcp.json
PROJECT_CONFIG_DIRNAME = ".minicc"
PROJECT_MCP_CONFIG_NAME = "mcp.json"

# 内置系统提示词文件路径
BUILTIN_PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "system.md"


def _load_builtin_prompt() -> str:
    if BUILTIN_PROMPT_FILE.exists():
        return BUILTIN_PROMPT_FILE.read_text(encoding="utf-8")
    return "你是一个代码助手，帮助用户完成编程任务。"


def ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        save_config(Config())
    if not AGENTS_FILE.exists():
        AGENTS_FILE.write_text(_load_builtin_prompt(), encoding="utf-8")


def load_config() -> Config:
    ensure_config_dir()
    if CONFIG_FILE.exists():
        content = CONFIG_FILE.read_text(encoding="utf-8")
        return Config.model_validate_json(content)
    return Config()


def save_config(config: Config) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(config.model_dump_json(indent=2), encoding="utf-8")


def load_agents_prompt() -> str:
    ensure_config_dir()
    if AGENTS_FILE.exists():
        return AGENTS_FILE.read_text(encoding="utf-8")
    return _load_builtin_prompt()


def get_api_key(provider: Provider) -> str:
    config = load_config()
    if config.api_key:
        return config.api_key

    env_var_map = {
        Provider.ANTHROPIC: "ANTHROPIC_API_KEY",
        Provider.OPENAI: "OPENAI_API_KEY",
    }
    env_var = env_var_map.get(provider)
    if env_var:
        api_key = os.environ.get(env_var)
        if api_key:
            return api_key
    raise ValueError(
        f"未找到 {provider.value} 的 API 密钥。"
        f"请设置环境变量 {env_var} 或在 ~/.minicc/config.json 中配置 api_key"
    )


def find_mcp_config(cwd: str | Path | None = None) -> Path | None:
    base = Path(cwd) if cwd is not None else Path(os.getcwd())
    project_path = base / PROJECT_CONFIG_DIRNAME / PROJECT_MCP_CONFIG_NAME
    if project_path.exists():
        return project_path
    if MCP_CONFIG_FILE.exists():
        return MCP_CONFIG_FILE
    return None

