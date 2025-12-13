"""
聊天输入框（支持 Enter 提交、Ctrl+J 换行）

Textual 的 Input 组件不适合多行输入；这里基于 TextArea 实现一个轻量输入控件：
- Enter：提交（不会插入换行）
- Ctrl+J：插入换行
- 其余按键：沿用 TextArea 的编辑行为

另外支持可选的“@ 引用文件”键盘控制委托（up/down/enter/tab/escape）。
"""

from __future__ import annotations

from collections.abc import Callable

from textual import events
from textual.message import Message
from textual.widgets import TextArea


class ChatInput(TextArea):
    class Submitted(Message):
        def __init__(self, value: str):
            self.value = value
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._mention_key_handler: Callable[[str], bool] | None = None

    def set_mention_key_handler(self, handler: Callable[[str], bool] | None) -> None:
        self._mention_key_handler = handler

    async def _on_key(self, event: events.Key) -> None:
        # 先让 @ 引用面板拦截（如果已开启）
        if self._mention_key_handler is not None:
            try:
                if self._mention_key_handler(event.key):
                    event.stop()
                    event.prevent_default()
                    return
            except Exception:
                pass

        if self.read_only:
            return

        if event.key == "ctrl+j":
            event.stop()
            event.prevent_default()
            start, end = self.selection
            self._replace_via_keyboard("\n", start, end)
            self.scroll_cursor_visible()
            return

        if event.key == "enter":
            event.stop()
            event.prevent_default()
            self.post_message(self.Submitted(self.text))
            return

        # 其他按键走 TextArea 默认逻辑（含可打印字符插入、光标移动等）
        await super()._on_key(event)
