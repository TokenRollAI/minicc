"""
MiniCC 数据模型定义

所有 Pydantic 模型集中定义在此文件中，提供类型安全的数据结构。
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Provider(str, Enum):
    """LLM 提供商枚举"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"


class Config(BaseModel):
    """
    应用配置结构

    存储在 ~/.minicc/config.json

    Attributes:
        provider: LLM 提供商 (anthropic/openai)
        model: 模型名称，如 claude-sonnet-4-20250514 或 gpt-4o
        api_key: API 密钥，若为 None 则从环境变量读取
        base_url: 自定义 API 端点（可选，用于代理服务）
    """
    provider: Provider = Provider.ANTHROPIC
    model: str = "claude-sonnet-4-20250514"
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class FileOperation(str, Enum):
    """文件操作类型"""
    READ = "read"
    WRITE = "write"
    UPDATE = "update"


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

    用于追踪 spawn_agent 创建的子任务状态。

    Attributes:
        task_id: 唯一任务标识
        prompt: 任务描述/提示词
        status: 任务状态 - pending/running/completed/failed
        result: 任务结果（完成后填充）
    """
    task_id: str
    prompt: str
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None


class Message(BaseModel):
    """
    对话消息

    表示用户或助手的单条消息。

    Attributes:
        role: 消息角色 - "user" 或 "assistant"
        content: 消息内容
    """
    role: str  # "user", "assistant"
    content: str


class ToolCall(BaseModel):
    """
    工具调用记录

    记录 Agent 进行的工具调用信息。

    Attributes:
        tool_name: 工具名称
        args: 调用参数
        result: 执行结果
    """
    tool_name: str
    args: dict
    result: ToolResult


# ============ Agent 依赖类型 ============
# 使用 dataclass 而非 Pydantic 以避免序列化问题

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class MiniCCDeps:
    """
    Agent 依赖注入容器

    通过 RunContext 传递给所有工具函数，提供共享状态。

    Attributes:
        config: 应用配置
        cwd: 当前工作目录
        sub_agents: 子任务追踪字典 {task_id: AgentTask}
        sub_agent_tasks: 子任务的 asyncio 任务句柄
        on_tool_call: 工具调用回调（用于 UI 更新）
    """
    config: Config
    cwd: str
    sub_agents: dict[str, AgentTask] = field(default_factory=dict)
    sub_agent_tasks: dict[str, Any] = field(default_factory=dict)
    on_tool_call: Callable[[str, dict, Any], None] | None = None
