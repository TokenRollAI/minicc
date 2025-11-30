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

### schemas.py (179 行)
数据模型定义，所有 Pydantic 模型集中管理。

**关键类:**
- `Config`: 应用配置结构（新增 PromptCache 支持）
- `PromptCache`: Anthropic Prompt Cache 配置
- `Provider`: LLM 提供商枚举
- `ToolResult`: 工具执行结果
- `DiffLine`: Diff 行信息
- `AgentTask`: SubAgent 任务定义（新增 description, subagent_type）
- `TodoItem`: 任务列表项（新增）
- `BackgroundShell`: 后台 Shell 进程信息（新增）
- `MiniCCDeps`: Agent 依赖注入容器，新增字段：
  - `fs: Any = None`: agent-gear FileSystem 实例（高性能文件操作）
  - `todos`: 任务列表（TodoWrite 工具管理）
  - `background_shells`: 后台 Shell 进程字典
  - `on_todo_update`: 任务列表更新回调

### config.py (155 行)
配置文件管理，处理 ~/.minicc 目录。

**关键函数:**
- `load_config()`: 加载配置
- `save_config()`: 保存配置
- `load_agents_prompt()`: 加载系统提示词
- `get_api_key()`: 获取 API 密钥

### tools.py (1259 行)
工具函数实现，定义所有可供 Agent 调用的工具。基于 agent-gear FileSystem 进行性能优化，对标 Claude Code。

**工具分类:**
- **文件操作**（Agent-Gear 优化）:
  - `read_file`: 使用 `fs.read_lines()` 进行分段读取，支持 offset/limit，output 为 cat -n 格式
    - Fallback: `_read_file_fallback()` 基于 pathlib 的原始实现
  - `write_file`: 使用 `fs.write_file()` 原子写入（temp-fsync-rename），安全可靠
    - Fallback: `_write_file_fallback()` 基于原始 Path.write_text()
  - `edit_file`: 结合 `fs.read_file()` 和 `fs.write_file()` 实现精确字符串替换 + 空白容错
    - Fallback: `_edit_file_fallback()` 基于字符串操作的原始实现
- **搜索**（Agent-Gear 优化）:
  - `glob_files`: 使用 `fs.glob()` 利用内存索引 + LRU 缓存，2-3x 加速
    - Fallback: `_glob_fallback()` 基于 wcmatch 的原始实现
  - `grep_search`: 使用 `fs.grep()` 高性能搜索（基于 ripgrep 核心库）
    - Fallback: `_grep_ripgrepy()` 使用 ripgrepy 库
    - Fallback: `_grep_fallback()` 使用 pathlib 遍历
- **命令行**:
  - `bash` (同步执行，timeout/description/run_in_background 参数)
  - `bash_output` (获取后台命令输出)
  - `kill_shell` (终止后台命令)
- **任务管理**:
  - `task` (创建子任务)
  - `todo_write` (任务追踪)
- **Notebook**:
  - `notebook_edit` (Jupyter notebook 编辑)

**核心优化策略**:
- 内存文件索引 + LRU 缓存：避免重复 I/O
- 原子操作：temp-fsync-rename 保证数据完整性
- 文件监听：自动更新索引，无需手动刷新
- Fallback 兼容性：FileSystem 不可用时自动降级

### agent.py (148 行)
Agent 定义，使用 pydantic-ai 创建和配置。

**关键函数:**
- `create_model()`: 创建模型标识符
- `create_agent()`: 创建并配置 Agent
- `_build_tools()`: 注册工具到 Agent

### app.py (262 行)
Textual TUI 主应用，处理用户交互和消息流处理。

**关键功能:**
- 消息输入和显示（MessagePanel）
- 流式输出处理（工具调用和响应文本）
- 快捷键绑定（Ctrl+C 退出、Ctrl+L 清屏、Escape 取消）
- 工具调用回调处理（ToolCallLine / SubAgentLine）
- Token 使用量追踪和更新（BottomBar.add_tokens）
- **Agent-Gear FileSystem 集成**（新增）:
  - `__init__` 中初始化：`self._fs = FileSystem(cwd, auto_watch=True)`
  - `_wait_fs_ready()` 后台方法等待索引就绪（使用 @work 装饰器）
  - `action_quit()` 中关闭 FileSystem 释放资源

**布局结构:**
```
Header
↓
chat_container (VerticalScroll) - 消息/工具调用/SubAgent
  ├─ MessagePanel: 用户/助手消息
  ├─ ToolCallLine: 工具调用（单行简洁）
  ├─ SubAgentLine: SubAgent 任务（单行简洁）
  └─ DiffView: 文件变更预览
↓
Input - 用户输入框
↓
BottomBar - 模型/目录/分支/Token
↓
Footer
```

### ui/widgets.py (272 行)
自定义 UI 组件集合，已精简为核心组件。

**保留的组件:**
- `MessagePanel`: 消息面板，支持 Markdown 渲染和角色区分
- `ToolCallLine`: 工具调用单行显示 `🔧 tool_name (param) ✅/❌`
- `SubAgentLine`: SubAgent 单行显示 `🤖 prompt_summary ⏳/🔄/✅/❌`
- `DiffView`: Diff 显示，颜色区分添加/删除/上下文
- `BottomBar`: 底边栏，分区块显示模型/目录/分支/Token
- `TodoDisplay`: 任务列表显示（新增）

**已移除的组件:**
- `ToolCallPanel` → 被 `ToolCallLine` 替代（更简洁）
- `SubAgentPanel` → 被 `SubAgentLine` 替代
- `UsageDisplay` → 功能集成到 `BottomBar`
- `StatusBar` → 功能已弃用
- `CollapsibleToolPanel` → 被 `ToolCallLine` 替代
