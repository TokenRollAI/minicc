# 数据模型参考

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
| prompt | str | - | 任务描述 |
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
