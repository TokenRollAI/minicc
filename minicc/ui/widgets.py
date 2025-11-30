"""
MiniCC 自定义 UI 组件

提供消息面板、工具调用面板、Diff 视图等自定义组件。
"""

from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from textual.widgets import Static
from textual.message import Message

from ..schemas import DiffLine, TodoItem, ToolResult


class MessagePanel(Static):
    """
    消息面板组件

    用于显示用户或助手的单条消息，带有角色标识和边框样式。
    """

    def __init__(self, content: str, role: str = "user", **kwargs):
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
        return Panel(markdown, title=title, border_style=color, expand=True)


class ToolCallLine(Static):
    """
    工具调用单行显示

    简洁显示工具调用：🔧 tool_name (key_param) ✅/❌
    """

    def __init__(self, tool_name: str, args: dict, result: ToolResult, **kwargs):
        self.tool_name = tool_name
        self.args = args
        self.result = result
        super().__init__(**kwargs)

    def render(self) -> Text:
        """渲染工具调用行"""
        text = Text()
        text.append("  🔧 ", style="yellow")
        text.append(self.tool_name, style="bold yellow")

        # 提取关键参数
        summary = self._get_summary()
        if summary:
            text.append(f" {summary}", style="dim")

        # 状态
        if self.result.success:
            text.append(" ✅", style="green")
        else:
            text.append(" ❌", style="red")

        return text

    def _get_summary(self) -> str:
        """获取参数摘要"""
        key_params = ["path", "file_path", "pattern", "command", "query", "prompt"]
        for key in key_params:
            if key in self.args:
                value = str(self.args[key])
                if len(value) > 40:
                    value = value[:40] + "..."
                return f"({value})"
        return ""


class SubAgentLine(Static):
    """
    SubAgent 任务单行显示

    简洁显示：🤖 prompt_short ⏳/🔄/✅/❌
    """

    def __init__(self, task_id: str, prompt: str, status: str, **kwargs):
        self.task_id = task_id
        self.prompt = prompt
        self._status = status
        super().__init__(**kwargs)

    def render(self) -> Text:
        """渲染 SubAgent 行"""
        text = Text()
        text.append("  🤖 ", style="magenta")

        # 截断 prompt
        prompt_short = self.prompt[:50] + "..." if len(self.prompt) > 50 else self.prompt
        text.append(prompt_short, style="bold magenta")

        # 状态图标
        status_icon = {
            "pending": " ⏳",
            "running": " 🔄",
            "completed": " ✅",
            "failed": " ❌"
        }.get(self._status, " ❓")
        text.append(status_icon)

        return text


class DiffView(Static):
    """
    简单 Diff 显示组件

    用于显示文件变更的 diff，使用颜色区分添加/删除/上下文行。
    """

    def __init__(self, diff_lines: list[DiffLine], filename: str = "", **kwargs):
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
        return Panel(text, title=title, border_style="cyan", expand=True)


class BottomBar(Static):
    """
    底边栏组件

    分区块显示：模型、目录、git 分支、token 使用情况。
    """

    def __init__(
        self,
        model: str = "",
        cwd: str = "",
        git_branch: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        **kwargs
    ):
        self.model = model
        self.cwd = cwd
        self.git_branch = git_branch
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        super().__init__(**kwargs)

    def update_info(
        self,
        model: str | None = None,
        cwd: str | None = None,
        git_branch: str | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None
    ) -> None:
        """更新信息"""
        if model is not None:
            self.model = model
        if cwd is not None:
            self.cwd = cwd
        if git_branch is not None:
            self.git_branch = git_branch
        if input_tokens is not None:
            self.input_tokens = input_tokens
        if output_tokens is not None:
            self.output_tokens = output_tokens
        self.refresh()

    def add_tokens(self, input_delta: int = 0, output_delta: int = 0) -> None:
        """累加 token 使用量"""
        self.input_tokens += input_delta
        self.output_tokens += output_delta
        self.refresh()

    def render(self) -> Text:
        """渲染底边栏"""
        text = Text()

        # 模型
        text.append(" 📦 ", style="dim")
        text.append(self.model or "N/A", style="cyan")
        text.append("  │  ", style="dim")

        # 目录
        text.append("📁 ", style="dim")
        cwd_short = self.cwd
        if len(cwd_short) > 25:
            cwd_short = "..." + cwd_short[-22:]
        text.append(cwd_short, style="green")
        text.append("  │  ", style="dim")

        # Git 分支
        text.append("🌿 ", style="dim")
        if self.git_branch:
            text.append(self.git_branch, style="magenta")
        else:
            text.append("N/A", style="dim")
        text.append("  │  ", style="dim")

        # Token 使用
        text.append("⬆️", style="dim")
        text.append(f"{self.input_tokens}", style="yellow")
        text.append(" ⬇️", style="dim")
        text.append(f"{self.output_tokens}", style="yellow")

        return text


class TodoDisplay(Static):
    """
    任务列表显示组件

    固定显示当前会话的任务追踪状态，分区显示未完成和已完成任务。
    任务全部完成时，标题显示关闭按钮 [×]，点击可关闭。
    """

    class Closed(Message):
        """任务列表关闭消息"""
        pass

    def __init__(self, todos: list[TodoItem] | None = None, **kwargs):
        self.todos: list[TodoItem] = todos or []
        super().__init__(**kwargs)

    def update_todos(self, todos: list[TodoItem]) -> None:
        """更新任务列表"""
        self.todos = todos
        self.refresh()

    def has_todos(self) -> bool:
        """是否有任务"""
        return len(self.todos) > 0

    def is_all_completed(self) -> bool:
        """是否全部完成"""
        if not self.todos:
            return False
        return all(t.status == "completed" for t in self.todos)

    async def on_click(self, event) -> None:
        """点击事件：全部完成时点击右上角关闭"""
        if self.is_all_completed():
            # 检查点击位置是否在右上角（大约前5个字符宽度）
            if event.x >= self.size.width - 6:
                self.post_message(self.Closed())

    def render(self) -> Panel:
        """渲染任务列表，分区显示未完成和已完成"""
        if not self.todos:
            return Panel(Text("暂无任务", style="dim"), title="📋 任务", border_style="dim")

        text = Text()

        # 分离未完成和已完成
        pending = [t for t in self.todos if t.status in ("pending", "in_progress")]
        completed = [t for t in self.todos if t.status == "completed"]

        # 统计
        total = len(self.todos)
        done = len(completed)
        progress = f"{done}/{total}"

        # 渲染未完成任务
        if pending:
            for todo in pending:
                if todo.status == "in_progress":
                    text.append("🔄 ", style="yellow")
                    text.append(f"{todo.active_form}\n", style="yellow bold")
                else:
                    text.append("⏳ ", style="dim")
                    text.append(f"{todo.content}\n", style="dim")

        # 渲染已完成任务（折叠显示）
        if completed:
            if pending:
                text.append("─" * 20 + "\n", style="dim")
            text.append(f"✅ 已完成 {done} 项", style="green dim")
            # 只显示最近3个已完成的
            recent = completed[-3:] if len(completed) > 3 else completed
            for todo in recent:
                text.append(f"\n   ✓ {todo.content}", style="green dim")
            if len(completed) > 3:
                text.append(f"\n   ... 及其他 {len(completed) - 3} 项", style="dim")

        # 标题：全部完成时显示关闭按钮
        all_done = done == total and total > 0
        if all_done:
            title = f"📋 任务 ✓ 全部完成 [×]"
        else:
            title = f"📋 任务 [{progress}]"

        border = "green" if all_done else "cyan"
        return Panel(text, title=title, title_align="left", border_style=border)
