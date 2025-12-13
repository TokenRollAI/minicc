# MiniCC

极简版 Claude Code，用于教学。

**想知道 Claude Code 这类 AI 编程助手是怎么实现的？** 看这个项目就够了。核心代码约 1400 行，架构清晰，注释充分。

## 能干嘛

- 读写文件、搜索代码、执行 shell 命令
- 创建子任务并行处理
- 终端 UI 界面，支持流式输出

## 技术栈

- [pydantic-ai](https://ai.pydantic.dev/) - Agent 框架
- [Textual](https://textual.textualize.io/) - TUI 框架

## 快速开始

```bash
# 设置 API Key
export ANTHROPIC_API_KEY="your-key"
# 或 export OPENAI_API_KEY="your-key"

# 直接运行（无需安装）
uvx minicc

# 或者安装后运行
uv pip install minicc
minicc
```

## 开发

```bash
git clone https://github.com/TokenRollAI/miniCC.git
cd miniCC
uv sync
uv run minicc
```

## 项目结构

```
minicc/
├── cli.py       # 入口（仅启动 TUI）
├── core/        # 运行时/模型/事件总线/MCP 预加载
├── tools/       # 工具实现（按职责拆分）
└── tui/         # Textual TUI（消费 stream events）
```

## 配置

配置文件在 `~/.minicc/config.json`：

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-20250514"
}
```

可选 MCP 配置：

- 项目级：`<project>/.minicc/mcp.json`
- 全局：`~/.minicc/mcp.json`

MiniCC 会自动加载 MCP servers，并把它们的工具注册给 Agent。

如需启用 MCP（连接/启动 MCP servers），请安装可选依赖：`pip install "minicc[mcp]"`。

### Prompt Cache (Anthropic)

按照 [pydantic-ai Anthropic 指南](https://ai.pydantic.dev/models/anthropic/#how-cache-points-are-allocated) 可以在配置里开启 prompt caching：

```json
{
  "provider": "anthropic",
  "model": "claude-sonnet-4-20250514",
  "prompt_cache": {
    "instructions": true,
    "tool_definitions": "1h",
    "messages": true
  }
}
```

- `instructions` 缓存系统提示词；`tool_definitions` 缓存工具定义；`messages` 缓存最近一条用户消息  
- `true` 表示 5 分钟 TTL，或显式写 `"5m"` / `"1h"`  
- Anthropic 最多支持 4 个 cache points，pydantic-ai 会按指南自动裁剪超出的 CachePoint

## 工具列表

| 工具         | 作用           |
| ------------ | -------------- |
| read_file    | 读文件         |
| write_file   | 写文件         |
| edit_file    | 改文件         |
| glob_files   | 按模式搜索文件 |
| grep_search  | 正则搜索内容   |
| bash         | 执行命令       |
| task         | 子任务（默认等待） |
| wait_subagents | 等待所有后台子任务 |

## License

MIT
