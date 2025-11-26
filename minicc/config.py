"""
MiniCC 配置管理

处理 ~/.minicc 目录下的配置文件和 AGENTS.md 系统提示词。
"""

import os
from pathlib import Path

from .schemas import Config, Provider


# 配置文件路径
CONFIG_DIR = Path.home() / ".minicc"
CONFIG_FILE = CONFIG_DIR / "config.json"
AGENTS_FILE = CONFIG_DIR / "AGENTS.md"

# 默认系统提示词（当 AGENTS.md 不存在时使用）
DEFAULT_SYSTEM_PROMPT = """# MiniCC Agent

你是一个代码助手，可以帮助用户完成各种编程任务。

## 可用工具

### 文件操作
- `read_file`: 读取文件内容
- `write_file`: 创建或覆盖文件
- `update_file`: 更新文件中的特定内容

### 搜索
- `search_files`: 按 glob 模式搜索文件
- `grep`: 在文件内容中搜索正则表达式

### 命令行
- `bash`: 执行 shell 命令

### 子任务
- `spawn_agent`: 创建子 Agent 处理独立任务
- `wait_sub_agents`: 等待一个或多个子任务完成（可设置超时）

## 使用指南

1. 在修改文件前，先使用 `read_file` 了解当前内容
2. 对于复杂任务，可以使用 `spawn_agent` 并行处理
3. 执行命令时注意安全性，避免危险操作
4. 使用 `update_file` 进行精确的内容替换，避免覆盖整个文件
"""


def ensure_config_dir() -> None:
    """
    确保配置目录存在

    创建 ~/.minicc 目录（如不存在），并初始化默认配置文件。
    """
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # 创建默认配置文件
    if not CONFIG_FILE.exists():
        default_config = Config()
        save_config(default_config)

    # 创建默认 AGENTS.md
    if not AGENTS_FILE.exists():
        AGENTS_FILE.write_text(DEFAULT_SYSTEM_PROMPT, encoding="utf-8")


def load_config() -> Config:
    """
    加载应用配置

    从 ~/.minicc/config.json 读取配置，若不存在则返回默认配置。

    Returns:
        Config: 应用配置对象
    """
    ensure_config_dir()

    if CONFIG_FILE.exists():
        content = CONFIG_FILE.read_text(encoding="utf-8")
        return Config.model_validate_json(content)

    return Config()


def save_config(config: Config) -> None:
    """
    保存应用配置

    将配置写入 ~/.minicc/config.json

    Args:
        config: 要保存的配置对象
    """
    # 只确保目录存在，不调用 ensure_config_dir 避免递归
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(
        config.model_dump_json(indent=2),
        encoding="utf-8"
    )


def load_agents_prompt() -> str:
    """
    加载系统提示词

    从 ~/.minicc/AGENTS.md 读取，若不存在则返回默认提示词。

    Returns:
        str: 系统提示词内容
    """
    ensure_config_dir()

    if AGENTS_FILE.exists():
        return AGENTS_FILE.read_text(encoding="utf-8")

    return DEFAULT_SYSTEM_PROMPT


def get_api_key(provider: Provider) -> str:
    """
    获取 API 密钥

    优先从配置文件读取，否则从环境变量获取。

    Args:
        provider: LLM 提供商

    Returns:
        str: API 密钥

    Raises:
        ValueError: 未找到 API 密钥时抛出
    """
    config = load_config()

    # 优先使用配置文件中的密钥
    if config.api_key:
        return config.api_key

    # 根据提供商查找环境变量
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
