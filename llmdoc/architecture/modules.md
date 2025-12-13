# 模块架构（v0.3.0 大重构）

## 模块依赖关系

```
┌──────────────┐
│  minicc/cli  │  CLI 入口
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ minicc/tui   │  Textual TUI
└──────┬───────┘
       │  build_runtime()
       ▼
┌──────────────┐     ┌──────────────┐
│ minicc/core  │◀───▶│ minicc/tools │
└──────────────┘     └──────────────┘
```

关键设计点：
- **TUI 不再依赖 tools 内部回调**，而是消费 `Agent.run_stream_events()` 的工具事件。
- **core 提供事件总线与服务层**（ask_user、subagents），tools 只做业务逻辑与依赖注入读取。
- **MCP 在启动阶段预加载并缓存**，避免每次 create_agent 重复加载。

## 模块职责

### minicc/core/models.py
数据模型定义（内部使用）。

核心模型：
- `Config` / `Provider` / `PromptCache`
- `ToolResult` / `DiffLine`
- `AgentTask` / `TodoItem` / `BackgroundShell`
- `Question*` / `AskUserRequest` / `AskUserResponse`
- `MiniCCDeps`：依赖注入容器（增加 `event_bus`、`ask_user_service`、`subagent_service`）

### minicc/core/config.py
配置管理（~/.minicc/config.json、AGENTS.md、MCP 配置查找）。

### minicc/core/mcp.py
MCP toolsets 加载与缓存：
- `load_mcp_toolsets(cwd)`：启动时加载；按配置路径缓存；支持 `MINICC_MCP_STRICT=1` 严格模式。

### minicc/core/agent.py
Agent 创建：
- `create_agent(config, cwd, toolsets, register_tools)`：支持外部传入预加载的 MCP toolsets。

### minicc/core/events.py
事件总线与事件类型：
- `EventBus`：`emit()` + `iter()` 消费。
- `ToolCallStarted/Finished`、`TodoUpdated`、`AskUserRequested`、`SubAgentCreated/Updated` 等。

### minicc/core/runtime.py
运行时组装：
- `build_runtime()`：创建 FileSystem、预加载 MCP toolsets、构造 deps 与 services、创建 Agent。

### minicc/core/services/*
服务层（与 UI 解耦）：
- `AskUserService`：通过事件总线请求 UI，等待 UI resolve。
- `SubAgentService`：支持等待或后台运行（`background`）。

### minicc/tools/*
按职责拆分的工具实现：
- `file.py`：read_file/write_file/edit_file（无 fs 时自动 fallback）。
- `search.py`：glob_files/grep_search（优先 ripgrepy，缺依赖 fallback）。
- `shell.py`：bash/bash_output/kill_shell（超时会杀进程组避免残留）。
- `task.py`：task/todo_write/wait_subagents。
- `registry.py`：统一注册工具。

### minicc/tui/*
Textual TUI：
- `app.py`：消费 stream events + event_bus，渲染 ToolCallLine/SubAgentLine/Todo/ask_user。
- `widgets.py`：组件（ToolCallLine 支持状态更新；BottomBar 使用通用箭头符号）。
- `ask_user_panel.py`：问答面板。
