# 模块架构

## 模块依赖关系

```
┌─────────────┐
│   app.py    │  TUI 入口
└──────┬──────┘
       │
       ▼
┌─────────────┐     ┌─────────────┐
│  agent.py   │────▶│  tools.py   │
└──────┬──────┘     └──────┬──────┘
       │                   │
       ▼                   ▼
┌─────────────┐     ┌─────────────┐
│  config.py  │     │ schemas.py  │
└─────────────┘     └─────────────┘
```

## 模块职责

### schemas.py (118 行)
数据模型定义，所有 Pydantic 模型集中管理。

**关键类:**
- `Config`: 应用配置结构
- `Provider`: LLM 提供商枚举
- `ToolResult`: 工具执行结果
- `AgentTask`: 子任务状态

### config.py (155 行)
配置文件管理，处理 ~/.minicc 目录。

**关键函数:**
- `load_config()`: 加载配置
- `save_config()`: 保存配置
- `load_agents_prompt()`: 加载系统提示词
- `get_api_key()`: 获取 API 密钥

### tools.py (494 行)
工具函数实现，定义所有可供 Agent 调用的工具。

**工具分类:**
- 文件操作: read_file, write_file, update_file
- 搜索: search_files, grep
- 命令行: bash
- 子任务: spawn_agent, get_agent_result

### agent.py (123 行)
Agent 定义，使用 pydantic-ai 创建和配置。

**关键组件:**
- `MiniCCDeps`: 依赖注入容器
- `create_model()`: 创建模型标识符
- `create_agent()`: 创建并配置 Agent

### app.py (203 行)
Textual TUI 主应用，处理用户交互。

**关键功能:**
- 消息输入和显示
- 流式输出处理
- 快捷键绑定

### ui/widgets.py (212 行)
自定义 UI 组件。

**组件:**
- `MessagePanel`: 消息面板
- `ToolCallPanel`: 工具调用面板
- `DiffView`: Diff 显示
- `UsageDisplay`: Token 使用量显示
