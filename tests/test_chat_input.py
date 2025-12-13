from __future__ import annotations

import pytest
from textual.app import App, ComposeResult

from minicc.tui.chat_input import ChatInput


class _ChatInputTestApp(App):
    def __init__(self):
        super().__init__()
        self.submitted: str | None = None

    def compose(self) -> ComposeResult:
        yield ChatInput(id="input", soft_wrap=True, show_line_numbers=False)

    def on_mount(self) -> None:
        self.query_one(ChatInput).focus()

    def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        self.submitted = event.value


@pytest.mark.asyncio
async def test_ctrl_j_inserts_newline_and_moves_cursor():
    app = _ChatInputTestApp()
    async with app.run_test() as pilot:
        await pilot.press("h", "i", "ctrl+j", "t", "h", "e", "r", "e")
        widget = app.query_one(ChatInput)
        assert widget.text == "hi\nthere"
        assert widget.cursor_location == (1, 5)


@pytest.mark.asyncio
async def test_enter_submits_without_inserting_newline():
    app = _ChatInputTestApp()
    async with app.run_test() as pilot:
        await pilot.press("h", "i", "ctrl+j", "t", "h", "e", "r", "e")
        await pilot.press("enter")
        await pilot.pause()

        widget = app.query_one(ChatInput)
        assert app.submitted == "hi\nthere"
        assert widget.text == "hi\nthere"


@pytest.mark.asyncio
async def test_mention_handler_can_intercept_enter():
    app = _ChatInputTestApp()
    async with app.run_test() as pilot:
        widget = app.query_one(ChatInput)
        widget.set_mention_key_handler(lambda key: key == "enter")

        await pilot.press("h", "i")
        await pilot.press("enter")
        await pilot.pause()

        assert app.submitted is None
        assert widget.text == "hi"

