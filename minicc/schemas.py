"""
MiniCC 数据模型定义

所有 Pydantic 模型集中定义在此文件中，提供类型安全的数据结构。
对标 Claude Code 工具系统设计。
"""

from asyncio import Task as AsyncTask
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, Field


# ============ 枚举类型 ============

class Provider(str, Enum):
    """LLM 提供商枚举"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


# ============ 配置模型 ============

class PromptCache(BaseModel):
    """
    Anthropic Prompt Cache 配置

    对应 pydantic-ai Anthropic 模型的 prompt caching 设置。
    每个字段支持 bool（True=5m TTL）或 '5m'/'1h'。
    """
    instructions: bool | Literal["5m", "1h"] = False
    messages: bool | Literal["5m", "1h"] = False
    tool_definitions: bool | Literal["5m", "1h"] = False


class Config(BaseModel):
    """
    应用配置结构

    存储在 ~/.minicc/config.json

    Attributes:
        provider: LLM 提供商 (anthropic/openai)
        model: 模型名称，如 claude-sonnet-4-20250514 或 gpt-4o
        api_key: API 密钥，若为 None 则从环境变量读取
        base_url: 自定义 API 端点（可选，用于代理服务）
        prompt_cache: Anthropic Prompt Cache 配置
    """
    provider: Provider = Provider.ANTHROPIC
    model: str = "claude-sonnet-4-20250514"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    prompt_cache: PromptCache = Field(default_factory=PromptCache)


# ============ 工具相关模型 ============

class ToolResult(BaseModel):
    """
    工具执行结果

    统一的工具返回格式，便于 Agent 解析。

    Attributes:
        success: 是否执行成功
        output: 执行输出（成功时的结果或错误时的详情）
        error: 错误信息（仅失败时有值）
    """
    success: bool
    output: str
    error: Optional[str] = None


class DiffLine(BaseModel):
    """
    Diff 行数据

    表示 diff 输出中的单行，用于简单文本 diff 显示。

    Attributes:
        type: 行类型 - "add"(新增), "remove"(删除), "context"(上下文)
        content: 行内容（不含 +/- 前缀）
        line_no: 行号（可选）
    """
    type: str  # "add", "remove", "context"
    content: str
    line_no: Optional[int] = None


class AgentTask(BaseModel):
    """
    SubAgent 任务定义

    用于追踪 Task 工具创建的子任务状态。

    Attributes:
        task_id: 唯一任务标识
        description: 3-5 词简短描述
        prompt: 任务描述/提示词
        subagent_type: 代理类型
        status: 任务状态 - pending/running/completed/failed
        result: 任务结果（完成后填充）
    """
    task_id: str
    description: str = ""
    prompt: str
    subagent_type: str = "general-purpose"
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None


class TodoItem(BaseModel):
    """
    任务列表项

    用于 TodoWrite 工具管理的任务追踪。

    Attributes:
        content: 任务描述（祈使句形式，如 "Run tests"）
        status: 任务状态 - pending/in_progress/completed
        active_form: 进行时描述（如 "Running tests"）
    """
    content: str
    status: Literal["pending", "in_progress", "completed"]
    active_form: str


class BackgroundShell(BaseModel):
    """
    后台 Shell 进程信息

    用于 Bash 工具的后台执行模式。

    Attributes:
        shell_id: 唯一标识
        command: 执行的命令
        description: 命令描述
        output_buffer: 输出缓冲
        is_running: 是否仍在运行
    """
    shell_id: str
    command: str
    description: str = ""
    output_buffer: str = ""
    is_running: bool = True


# ============ Agent 依赖类型 ============

@dataclass
class MiniCCDeps:
    """
    Agent 依赖注入容器

    通过 RunContext 传递给所有工具函数，提供共享状态。

    Attributes:
        config: 应用配置
        cwd: 当前工作目录
        fs: Agent-Gear FileSystem 实例（高性能文件操作）
        sub_agents: 子任务追踪字典 {task_id: AgentTask}
        sub_agent_tasks: 子任务的 asyncio 任务句柄
        todos: 任务列表（TodoWrite 工具管理）
        background_shells: 后台 Shell 进程 {shell_id: (process, BackgroundShell)}
        on_tool_call: 工具调用回调（用于 UI 更新）
        on_todo_update: 任务列表更新回调
    """
    config: Config
    cwd: str
    fs: Any = None  # agent_gear.FileSystem 实例
    sub_agents: dict[str, AgentTask] = field(default_factory=dict)
    sub_agent_tasks: dict[str, AsyncTask] = field(default_factory=dict)
    todos: list[TodoItem] = field(default_factory=list)
    background_shells: dict[str, tuple[Any, BackgroundShell]] = field(default_factory=dict)
    on_tool_call: Callable[[str, dict, Any], None] | None = None
    on_todo_update: Callable[[list[TodoItem]], None] | None = None
