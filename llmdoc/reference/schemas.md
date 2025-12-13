# 数据模型参考（v0.3.0）

## Provider (枚举)

LLM 提供商枚举。

```python
class Provider(str, Enum):
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
```

## Config

应用配置结构，存储在 ~/.minicc/config.json

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| provider | Provider | ANTHROPIC | LLM 提供商 |
| model | str | claude-sonnet-4-20250514 | 模型名称 |
| api_key | Optional[str] | None | API 密钥 |
| base_url | Optional[str] | None | 自定义 API 端点（可选） |
| prompt_cache | PromptCache | {} | Anthropic Prompt Cache 配置 |

> v0.3.0 模型定义位置：`minicc/core/models.py`

## ToolResult

工具执行结果，统一返回格式。

| 字段 | 类型 | 说明 |
|------|------|------|
| success | bool | 是否成功 |
| output | str | 执行输出 |
| error | Optional[str] | 错误信息 |

## AgentTask

子任务状态追踪。

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| task_id | str | - | 唯一任务 ID |
| description | str | "" | 简短描述（用于 UI 展示） |
| prompt | str | - | 任务提示词 |
| subagent_type | str | general-purpose | 代理类型（预留） |
| status | str | "pending" | 状态 |
| result | Optional[str] | None | 执行结果 |

**status 取值:**
- `pending`: 等待执行
- `running`: 执行中
- `completed`: 已完成
- `failed`: 失败

## DiffLine

Diff 行数据。

| 字段 | 类型 | 说明 |
|------|------|------|
| type | str | 行类型: add/remove/context |
| content | str | 行内容 |
| line_no | Optional[int] | 行号 |

## MiniCCDeps（依赖注入容器）

`MiniCCDeps` 由运行时组装（见 `minicc/core/runtime.py`），关键字段：

| 字段 | 类型 | 说明 |
|------|------|------|
| config | Config | 应用配置 |
| cwd | str | 工作目录 |
| fs | Any | agent-gear FileSystem（可选） |
| todos | list[TodoItem] | 任务列表（todo_write 更新） |
| background_shells | dict | 后台命令进程信息 |
| sub_agents | dict[str, AgentTask] | 子代理任务状态 |
| sub_agent_tasks | dict[str, Any] | 子代理 asyncio 任务句柄（后台模式） |
| event_bus | Any | 事件总线（TUI 消费） |
| ask_user_service | Any | ask_user 服务（等待用户回答） |
| subagent_service | Any | 子代理服务（支持等待/后台） |
