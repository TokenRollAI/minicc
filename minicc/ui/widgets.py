"""
MiniCC 自定义 UI 组件

提供消息面板、工具调用面板、Diff 视图等自定义组件。
"""

from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from textual.widgets import Static

from ..schemas import DiffLine, ToolResult


class MessagePanel(Static):
    """
    消息面板组件

    用于显示用户或助手的单条消息，带有角色标识和边框样式。

    Attributes:
        role: 消息角色 ("user" 或 "assistant")
        content: 消息内容
    """

    def __init__(
        self,
        content: str,
        role: str = "user",
        **kwargs
    ):
        self.role = role
        self._content = content
        super().__init__(content, markup=False, **kwargs)

    def set_content(self, content: str) -> None:
        """更新消息内容并刷新渲染"""
        self._content = content
        self.update(content)

    def render(self) -> Panel:
        """渲染消息面板"""
        role_style = {
            "user": ("blue", "You"),
            "assistant": ("green", "Assistant"),
            "system": ("magenta", "System")
        }
        color, title = role_style.get(self.role, ("white", self.role.title()))

        markdown = Markdown(self._content or "", code_theme="monokai", justify="left")

        return Panel(
            markdown,
            title=title,
            border_style=color,
            expand=True
        )


class ToolCallPanel(Static):
    """
    工具调用显示面板

    用于显示 Agent 进行的工具调用，包括工具名、参数和结果。

    Attributes:
        tool_name: 工具名称
        args: 调用参数字典
        result: 执行结果
    """

    def __init__(
        self,
        tool_name: str,
        args: dict,
        result: ToolResult,
        **kwargs
    ):
        self.tool_name = tool_name
        self.args = args
        self.result = result
        super().__init__(**kwargs)

    def render(self) -> Panel:
        """渲染工具调用面板"""
        # 格式化参数
        args_lines = []
        for key, value in self.args.items():
            value_str = repr(value)
            if len(value_str) > 40:
                value_str = value_str[:40] + "..."
            args_lines.append(f"- **{key}**: `{value_str}`")

        args_text = "\n".join(args_lines) if args_lines else "- (无参数)"

        # 格式化结果
        if self.result.success:
            status = "✅"
            output = self.result.output[:500]
            if len(self.result.output) > 500:
                output += "\n..."
        else:
            status = "❌"
            output = self.result.error or ""

        content = f"**参数**\n{args_text}\n\n**结果** {status}\n\n{output}"
        markdown = Markdown(content, code_theme="monokai", justify="left")

        return Panel(
            markdown,
            title=f"🔧 {self.tool_name}",
            border_style="yellow",
            expand=True
        )


class DiffView(Static):
    """
    简单 Diff 显示组件

    用于显示文件变更的 diff，使用颜色区分添加/删除/上下文行。

    Attributes:
        diff_lines: DiffLine 列表
        filename: 可选的文件名
    """

    def __init__(
        self,
        diff_lines: list[DiffLine],
        filename: str = "",
        **kwargs
    ):
        self.diff_lines = diff_lines
        self.filename = filename
        super().__init__(**kwargs)

    def render(self) -> Panel:
        """渲染 Diff 视图"""
        text = Text()

        for line in self.diff_lines:
            if line.type == "add":
                text.append(f"+ {line.content}\n", style="green")
            elif line.type == "remove":
                text.append(f"- {line.content}\n", style="red")
            else:
                text.append(f"  {line.content}\n", style="dim")

        title = f"Diff: {self.filename}" if self.filename else "Diff"

        return Panel(
            text,
            title=title,
            border_style="cyan",
            expand=True
        )


class UsageDisplay(Static):
    """
    Token 使用量显示组件

    显示模型名称和 token 消耗信息。

    Attributes:
        model: 模型名称
        input_tokens: 输入 token 数
        output_tokens: 输出 token 数
    """

    def __init__(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        **kwargs
    ):
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        super().__init__(**kwargs)

    def render(self) -> Text:
        """渲染使用量显示"""
        total = self.input_tokens + self.output_tokens
        return Text(
            f"📊 {self.model} | ⬆️ {self.input_tokens} | ⬇️ {self.output_tokens} | 总计: {total}",
            style="dim"
        )


class StatusBar(Static):
    """
    状态栏组件

    显示当前状态信息，如处理中、就绪等。

    Attributes:
        status: 状态文本
    """

    def __init__(self, status: str = "就绪", **kwargs):
        self.status = status
        super().__init__(**kwargs)

    def update_status(self, status: str) -> None:
        """更新状态"""
        self.status = status
        self.refresh()

    def render(self) -> Text:
        """渲染状态栏"""
        if "处理中" in self.status or "运行" in self.status:
            style = "yellow"
        elif "错误" in self.status or "失败" in self.status:
            style = "red"
        else:
            style = "green"

        return Text(f"● {self.status}", style=style)
