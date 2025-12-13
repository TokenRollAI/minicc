# MiniCC 项目概述

## 项目目标

实现一个极简版、具有教学意义的 Claude Code，帮助开发者理解 AI Agent 的核心实现原理。

## 设计原则

1. **代码精简**: 约 1400 行代码实现完整功能
2. **注释充分**: 每个函数和类都有详细文档
3. **架构清晰**: 模块职责分明，易于理解
4. **易于扩展**: 基于 pydantic-ai 的工具注册机制

## 核心能力

### 工具 (Tools)
- **文件操作**: read_file, write_file, edit_file (精确字符串替换)
- **搜索**: glob_files (高级 glob 模式), grep_search (ripgrepy 高性能)
- **命令行**: bash, bash_output (后台执行), kill_shell (终止后台任务)
- **任务管理**: task (子任务/可等待), wait_subagents (等待后台子任务), todo_write (任务追踪)
- **用户交互**: ask_user (TUI 面板选择题/多选题)

### 提示词 (Prompt)
- 系统提示词: ~/.minicc/AGENTS.md
- 工具描述: 从函数 docstring 自动提取

### 子代理 (SubAgent)
- 使用 task() 工具创建子任务
- **默认等待**：`task(wait=True)` 会等待子代理完成并返回结果（主 Agent 可直接整合）
- 可并行：`task(wait=False)` 后台启动，最后用 `wait_subagents()` 汇总等待

### 用户界面 (UI)
- Textual TUI 终端界面，支持流式输出、快捷键、工具调用行与任务列表
- **事件驱动**：UI 直接消费 `agent.run_stream_events()` 的工具调用事件，ToolCallLine 支持 running/completed/failed 状态
- ask_user 使用面板交互并阻塞等待用户提交/取消
- 底边栏显示关键上下文（模型/目录/分支/Token 统计）

## 技术决策

| 决策项 | 选择 | 理由 |
|--------|------|------|
| LLM 后端 | Anthropic + OpenAI | 覆盖主流提供商，支持 Prompt Cache |
| 文件系统操作 | agent-gear FileSystem | 内存索引 + LRU 缓存，2-3x 性能提升，自动文件监听 |
| 搜索引擎 | ripgrepy + wcmatch | 高性能，对标 Claude Code（ripgrep 核心库） |
| 文件编辑 | edit_file 精确替换 | 避免歧义，支持空白容错，原子操作 |
| 后台任务 | bash_output + kill_shell | 支持长运行任务和交互式命令 |

## v0.3.0 架构变化（概要）

- **结构拆分**：`minicc/core`（运行时/模型/事件/MCP）、`minicc/tools`（工具实现）、`minicc/tui`（界面）
- **MCP 预加载**：启动阶段加载并缓存 toolsets（避免子代理重复加载）；可用 `MINICC_MCP_STRICT=1` 强制失败
