"""
文件引用面板（@ 引用文件）

用于在输入框中输入 `@` 时展示文件候选列表，并允许键盘选择插入路径。
"""

from __future__ import annotations

from rich.panel import Panel
from rich.text import Text
from textual.widgets import Static


class FileMentionPanel(Static):
    def __init__(self, query: str, items: list[str], selected: int = 0, **kwargs):
        self.query = query
        self.items = items
        self.selected = selected
        super().__init__(**kwargs)

    def update_items(self, query: str, items: list[str], selected: int = 0) -> None:
        self.query = query
        self.items = items
        self.selected = selected
        self.refresh()

    def render(self) -> Panel:
        text = Text()
        text.append("@", style="bold cyan")
        text.append(self.query or "", style="cyan")
        text.append("  选择文件（↑↓ 选择，Enter/Tab 插入，Esc 关闭）\n", style="dim")

        if not self.items:
            text.append("（无匹配文件）", style="dim")
            return Panel(text, title="文件引用", border_style="cyan", padding=(0, 1))

        for i, p in enumerate(self.items[:20]):
            is_sel = i == self.selected
            text.append("❯ " if is_sel else "  ", style="bold yellow" if is_sel else "dim")
            text.append(p, style="bold yellow" if is_sel else "")
            text.append("\n")

        if len(self.items) > 20:
            text.append(f"... 还有 {len(self.items) - 20} 个结果", style="dim")

        return Panel(text, title="文件引用", border_style="cyan", padding=(0, 1))

