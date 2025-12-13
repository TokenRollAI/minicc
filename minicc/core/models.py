"""
MiniCC 数据模型定义

注意：该项目允许 breaking change，模型仅服务于内部（TUI）与工具实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Provider(str, Enum):
    """LLM 提供商枚举"""

    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class PromptCache(BaseModel):
    """
    Anthropic Prompt Cache 配置

    每个字段支持 bool（True=5m TTL）或 '5m'/'1h'。
    """

    instructions: bool | Literal["5m", "1h"] = False
    messages: bool | Literal["5m", "1h"] = False
    tool_definitions: bool | Literal["5m", "1h"] = False


class Config(BaseModel):
    """应用配置结构（~/.minicc/config.json）。"""

    provider: Provider = Provider.ANTHROPIC
    model: str = "claude-sonnet-4-20250514"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    prompt_cache: PromptCache = Field(default_factory=PromptCache)


class ToolResult(BaseModel):
    """工具执行结果（供模型与 UI 渲染）。"""

    success: bool
    output: str
    error: Optional[str] = None


class DiffLine(BaseModel):
    type: str  # "add" | "remove" | "context"
    content: str
    line_no: Optional[int] = None


class AgentTask(BaseModel):
    task_id: str
    description: str = ""
    prompt: str
    subagent_type: str = "general-purpose"
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None


class TodoItem(BaseModel):
    content: str
    status: Literal["pending", "in_progress", "completed"]
    active_form: str


class BackgroundShell(BaseModel):
    shell_id: str
    command: str
    description: str = ""
    output_buffer: str = ""
    is_running: bool = True


class QuestionOption(BaseModel):
    label: str
    description: str = ""


class Question(BaseModel):
    question: str
    header: str
    options: list[QuestionOption]
    multi_select: bool = False


class AskUserRequest(BaseModel):
    questions: list[Question]


class AskUserResponse(BaseModel):
    submitted: bool
    answers: dict[str, str | list[str]]


class UserCancelledError(Exception):
    pass


@dataclass
class MiniCCDeps:
    """
    Agent 依赖注入容器（RunContext.deps）

    说明：与旧版本不同，本版本不再通过 on_tool_call 等回调耦合 UI，
    统一改为事件总线（core.events）。
    """

    config: Config
    cwd: str
    fs: Any = None  # agent_gear.FileSystem 实例（可选）
    todos: list[TodoItem] = field(default_factory=list)
    background_shells: dict[str, tuple[Any, BackgroundShell]] = field(default_factory=dict)
    sub_agents: dict[str, AgentTask] = field(default_factory=dict)
    sub_agent_tasks: dict[str, Any] = field(default_factory=dict)

    # 由运行时注入（避免 tools 直接依赖 Textual）
    event_bus: Any = None  # core.events.EventBus
    ask_user_service: Any = None  # core.services.ask_user.AskUserService
    subagent_service: Any = None  # core.services.subagents.SubAgentService
