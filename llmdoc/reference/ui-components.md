# UI 组件参考

本文档提供 MiniCC 自定义 UI 组件的接口说明。

## MessagePanel

**文件:** `minicc/tui/widgets.py`

显示用户或助手的单条消息，支持 Markdown 渲染。

**参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| content | str | 消息内容（Markdown） |
| role | str | "user" \| "assistant" \| "system" |

**方法:** `set_content(content: str)` - 更新内容

**角色样式:** user(蓝) / assistant(绿) / system(洋红)

## ToolCallLine

**文件:** `minicc/tui/widgets.py`

工具调用单行显示，简洁展示执行状态。

**参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| tool_name | str | 工具名称 |
| args | dict | 调用参数 |
| status | str | "pending" \| "running" \| "completed" \| "failed" |

**显示格式:** `🔧 {tool_name} ({key_param}) {status_icon}`

**参数选择优先级:** path > file_path > pattern > command > query > prompt (30字符截断)

**状态图标:**
- `⏳` (pending)
- `🔄` (running)
- `✅` (completed)
- `❌` (failed)

## SubAgentLine

**文件:** `minicc/tui/widgets.py`

SubAgent 任务单行显示，简洁展示子任务状态。

**参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| task_id | str | 任务 ID |
| prompt | str | 任务描述 |
| status | str | "pending" \| "running" \| "completed" \| "failed" |
| result | Optional[str] | 任务结果 |

**显示格式:** `🤖 {prompt摘要} {status_icon}`

**提示词截断:** 40 字符

**状态图标:**
- `⏳` (pending)
- `🔄` (running)
- `✅` (completed)
- `❌` (failed)

## DiffView

**文件:** `minicc/tui/widgets.py`

显示文件变更的 Diff 视图，支持颜色区分。

**参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| diff_lines | list[DiffLine] | Diff 行列表 |
| filename | Optional[str] | 可选文件名 |

**DiffLine 结构 (core/models.py):**
```python
class DiffLine:
    type: str  # "add" | "remove" | "context"
    content: str  # 行内容
    line_no: Optional[int]  # 行号
```

**显示样式:**
- `add` (绿色 `+`)
- `remove` (红色 `-`)
- `context` (暗灰色 ` `)

## BottomBar

**文件:** `minicc/tui/widgets.py`

底边栏，恒定显示关键上下文信息（模型/目录/分支/Token）。

**参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| model | str | provider:model (如 `anthropic:claude-sonnet-4`) |
| cwd | str | 工作目录（超长时显示尾部） |
| git_branch | Optional[str] | Git 分支名 |
| input_tokens | int | 累计输入 token 数 |
| output_tokens | int | 累计输出 token 数 |

**方法:**
- `update_info(**kwargs)` - 更新任何字段（支持 model, cwd, git_branch, input_tokens, output_tokens）
- `add_tokens(input_delta, output_delta)` - 累加 token 数

**显示格式:**
```
📦 anthropic:claude-sonnet-4 │ 📁 /home/user/proj │ 🌿 main │ ↑123 ↓456
```

**设计特点:**
- 恒定显示，不可折叠
- 实时更新（接收 AgentRunResultEvent）
- 超长目录自动截断，显示尾部路径

## 工具调用展示（v0.3.0）

v0.3.0 起不再使用 “tools 内部回调” 来显示工具调用；TUI 直接消费 `agent.run_stream_events()` 的：
- `FunctionToolCallEvent` / `BuiltinToolCallEvent`：创建 ToolCallLine（running）
- `FunctionToolResultEvent` / `BuiltinToolResultEvent`：更新 ToolCallLine（completed/failed）

## FileMentionPanel（@ 引用文件）

**文件:** `minicc/tui/file_mention_panel.py`

输入框中输入 `@` + 文件名片段会弹出候选列表：
- `↑/↓`：选择候选
- `Enter` / `Tab`：插入路径到输入框
- `Esc`：关闭候选

## 集成指南

创建新组件步骤：

1. **定义组件** (`minicc/tui/widgets.py`)
   - 继承 `Static` 或 `Collapsible`
   - 实现 `render()` 或 `compose()` 方法
   - 添加 `__init__()` 方法初始化参数

2. **导出组件** (`minicc/tui/__init__.py`)
   - 添加到 `__all__`

3. **定义样式** (`minicc/tui/styles.tcss`)
   - 使用选择器 `<ComponentName>`
   - 定义颜色、宽度、边框等

4. **使用组件** (`minicc/tui/app.py`)
   - 导入组件类
   - 使用 `self.query_one(selector).mount(component_instance)`
   - 或直接在 `compose()` 中使用 `yield`

**示例:**
```python
# widgets.py (minicc/tui/widgets.py)
class MyComponent(Static):
    def render(self) -> str:
        return "Hello"

# __init__.py (minicc/tui/__init__.py)
from .widgets import MyComponent
__all__ = [..., "MyComponent"]

# styles.tcss (minicc/tui/styles.tcss)
MyComponent { width: 100%; }

# app.py (minicc/tui/app.py)
from .widgets import MyComponent
container.mount(MyComponent())
```
