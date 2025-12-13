"""
MiniCC TUI 应用（多行输入 + @ 引用文件）

关键点：
- 输入使用 TextArea（ChatInput）：Enter 提交；Ctrl+J 换行
- 工具调用展示：消费 pydantic-ai stream events
- ask_user/todo/subagent：消费事件总线（core.events.EventBus）
"""

from __future__ import annotations

import os
import re
import subprocess
import traceback
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.widgets import Footer, Header

from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import (
    BuiltinToolCallEvent,
    BuiltinToolResultEvent,
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    RetryPromptPart,
    TextPart,
    TextPartDelta,
    ToolReturnPart,
)

from minicc.core.config import load_config
from minicc.core.events import (
    AskUserRequested,
    SubAgentCreated,
    SubAgentUpdated,
    TodoUpdated,
    ToolCallFinished,
    ToolCallStarted,
)
from minicc.core.models import ToolResult, UserCancelledError
from minicc.core.runtime import MiniCCRuntime, build_runtime
from minicc.tui.ask_user_panel import AskUserPanel
from minicc.tui.chat_input import ChatInput
from minicc.tui.file_mention_panel import FileMentionPanel
from minicc.tui.widgets import BottomBar, MessagePanel, SubAgentLine, TodoDisplay, ToolCallLine


class MiniCCApp(App):
    TITLE = "MiniCC"
    CSS_PATH = "styles.tcss"

    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", priority=True),
        Binding("ctrl+l", "clear", "清屏"),
        Binding("escape", "cancel", "取消"),
    ]

    def __init__(self, runtime: MiniCCRuntime | None = None):
        super().__init__()
        config = load_config()
        self.runtime = runtime or build_runtime(config=config, cwd=os.getcwd())
        self.messages: list[Any] = []
        self._is_processing = False
        self._git_branch = self._get_git_branch()

        self._tool_lines: dict[str, ToolCallLine] = {}
        self._subagent_lines: dict[str, SubAgentLine] = {}
        self._current_ask_panel: AskUserPanel | None = None
        self._streaming_assistant_panel: MessagePanel | None = None

        # @ 引用文件
        self._mention_active = False
        self._mention_at_pos: int | None = None  # 当前行内 @ 的索引
        self._mention_query = ""
        self._mention_items: list[str] = []
        self._mention_selected = 0

    def _get_git_branch(self) -> str | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.runtime.cwd,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield VerticalScroll(id="chat_container")
        yield TodoDisplay(id="todo_display")
        yield Container(id="ask_user_container")
        yield Container(id="mention_container")
        yield ChatInput(
            id="input",
            placeholder="输入消息… Enter 发送，Ctrl+J 换行",
            soft_wrap=True,
            show_line_numbers=False,
        )
        yield BottomBar(
            model=f"{self.runtime.config.provider.value}:{self.runtime.config.model}",
            cwd=self.runtime.cwd,
            git_branch=self._git_branch,
            id="bottom_bar",
        )
        yield Footer(id="footer")

    def on_mount(self) -> None:
        input_widget = self.query_one("#input", ChatInput)
        input_widget.focus()
        input_widget.set_mention_key_handler(self._handle_mention_key)

        self.query_one("#todo_display", TodoDisplay).display = False
        self.query_one("#ask_user_container", Container).display = False
        self.query_one("#mention_container", Container).display = False
        self._show_welcome()
        self._wait_fs_ready()
        self._consume_events()

    @work(thread=True, group="startup")
    def _wait_fs_ready(self) -> None:
        try:
            self.runtime.fs.wait_ready(timeout=30.0)
        except Exception:
            pass

    def _show_welcome(self) -> None:
        self._append_message("**MiniCC** - 极简 AI 编程助手\n\n输入问题开始对话，Ctrl+C 退出", role="system")

    async def on_chat_input_submitted(self, event: ChatInput.Submitted) -> None:
        raw_input = event.value
        if not raw_input.strip():
            return

        if self._is_processing:
            self._append_message("⚠️ 请等待当前请求完成...", role="system")
            return

        input_widget = self.query_one("#input", ChatInput)
        self._hide_mention_panel()
        input_widget.text = ""
        input_widget.cursor_location = (0, 0)
        input_widget.call_after_refresh(input_widget.scroll_cursor_visible)

        user_input = raw_input
        self._append_message(user_input, role="user")

        self._streaming_assistant_panel = None
        self._process_message(user_input)

    def on_text_area_changed(self, event: ChatInput.Changed) -> None:
        if getattr(event, "text_area", None) is None or event.text_area.id != "input":
            return

        if self._current_ask_panel is not None:
            self._hide_mention_panel()
            return

        input_widget = self.query_one("#input", ChatInput)
        cursor_row, cursor_col = input_widget.cursor_location
        lines = input_widget.text.split("\n")
        current_line = lines[cursor_row] if 0 <= cursor_row < len(lines) else ""
        prefix = current_line[:cursor_col]

        at_info = _find_at_reference(prefix, len(prefix))
        if at_info is None:
            self._hide_mention_panel()
            return

        at_pos, query = at_info
        if query == "":
            self._show_mention_panel(at_pos, query, [])
            return

        items = self._search_files_for_mention(query)
        self._show_mention_panel(at_pos, query, items)

    @work(exclusive=True, group="chat")
    async def _process_message(self, user_input: str) -> None:
        self._is_processing = True
        try:
            streamed_text = ""
            async for event in self.runtime.agent.run_stream_events(
                user_input,
                deps=self.runtime.deps,
                message_history=self.messages,
            ):
                if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                    streamed_text += event.part.content
                    self._update_streaming_assistant(streamed_text)
                elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                    streamed_text += event.delta.content_delta
                    self._update_streaming_assistant(streamed_text)
                elif isinstance(event, (FunctionToolCallEvent, BuiltinToolCallEvent)):
                    part = event.part
                    args = None
                    try:
                        args = part.args_as_dict()
                    except Exception:
                        try:
                            args = part.args if isinstance(part.args, dict) else None
                        except Exception:
                            args = None
                    self.runtime.event_bus.emit(
                        ToolCallStarted(tool_call_id=part.tool_call_id, tool_name=part.tool_name, args=args)
                    )
                elif isinstance(event, (FunctionToolResultEvent, BuiltinToolResultEvent)):
                    result_part = event.result
                    tool_name = getattr(result_part, "tool_name", "") or ""
                    ok, err = _tool_result_to_status(result_part)
                    self.runtime.event_bus.emit(
                        ToolCallFinished(
                            tool_call_id=result_part.tool_call_id,
                            tool_name=tool_name,
                            ok=ok,
                            content=getattr(result_part, "content", None),
                            error=err,
                        )
                    )
                elif isinstance(event, AgentRunResultEvent):
                    final_text = streamed_text or str(event.result.output)
                    if self._streaming_assistant_panel is not None:
                        self._streaming_assistant_panel.set_content(final_text)
                        self._scroll_chat_end()
                    else:
                        self._append_message(final_text, role="assistant")
                    self.messages = event.result.all_messages()
                    usage = event.result.usage()
                    if usage:
                        self._update_tokens(usage)

        except UserCancelledError:
            self._append_message("⚠️ 操作已取消", role="system")
        except Exception as e:
            if os.environ.get("MINICC_DEBUG"):
                tb = traceback.format_exc()
                self._append_message(f"❌ 错误: {e}\n\n```text\n{tb}\n```", role="system")
            else:
                self._append_message(f"❌ 错误: {e}", role="system")
        finally:
            self._is_processing = False
            self._scroll_chat_end()

    @work(group="events")
    async def _consume_events(self) -> None:
        async for ev in self.runtime.event_bus.iter():
            if isinstance(ev, ToolCallStarted):
                self._on_tool_started(ev)
            elif isinstance(ev, ToolCallFinished):
                self._on_tool_finished(ev)
            elif isinstance(ev, TodoUpdated):
                self._on_todo_updated(ev)
            elif isinstance(ev, AskUserRequested):
                self._on_ask_user_requested(ev)
            elif isinstance(ev, SubAgentCreated):
                self._on_subagent_created(ev)
            elif isinstance(ev, SubAgentUpdated):
                self._on_subagent_updated(ev)

    def _on_tool_started(self, ev: ToolCallStarted) -> None:
        line = ToolCallLine(ev.tool_name, ev.args, status="running")
        self._tool_lines[ev.tool_call_id] = line
        chat = self._chat_container()
        chat.mount(line)
        self._ensure_stream_panel_last()
        self._scroll_chat_end()

    def _on_tool_finished(self, ev: ToolCallFinished) -> None:
        line = self._tool_lines.get(ev.tool_call_id)
        if line is None:
            line = ToolCallLine(ev.tool_name, {}, status="running")
            self._tool_lines[ev.tool_call_id] = line
            self._chat_container().mount(line)
        line.update_status("completed" if ev.ok else "failed")
        self._ensure_stream_panel_last()
        self._scroll_chat_end()

    def _on_todo_updated(self, ev: TodoUpdated) -> None:
        todo_display = self.query_one("#todo_display", TodoDisplay)
        todo_display.update_todos(ev.todos)
        todo_display.display = len(ev.todos) > 0

    def _on_ask_user_requested(self, ev: AskUserRequested) -> None:
        container = self.query_one("#ask_user_container", Container)
        container.remove_children()
        panel = AskUserPanel(ev.request_id, ev.questions)
        self._current_ask_panel = panel
        container.mount(panel)
        container.display = True

        main_input = self.query_one("#input", ChatInput)
        main_input.disabled = True
        self.call_later(panel.focus)

    def _hide_ask_panel(self) -> None:
        try:
            container = self.query_one("#ask_user_container", Container)
            container.remove_children()
            container.display = False
        except Exception:
            pass

        self._current_ask_panel = None
        try:
            main_input = self.query_one("#input", ChatInput)
            main_input.disabled = False
            main_input.focus()
        except Exception:
            pass

        self._hide_mention_panel()

    def on_ask_user_panel_submitted(self, event: AskUserPanel.Submitted) -> None:
        self.runtime.deps.ask_user_service.resolve(event.request_id, submitted=True, answers=event.answers)
        self._hide_ask_panel()

    def on_ask_user_panel_cancelled(self, event: AskUserPanel.Cancelled) -> None:
        self.runtime.deps.ask_user_service.resolve(event.request_id, submitted=False, answers={})
        self._hide_ask_panel()

    def _on_subagent_created(self, ev: SubAgentCreated) -> None:
        line = SubAgentLine(task_id=ev.task_id, prompt=ev.description or ev.prompt, status="pending")
        self._subagent_lines[ev.task_id] = line
        self._chat_container().mount(line)
        self._ensure_stream_panel_last()
        self._scroll_chat_end()

    def _on_subagent_updated(self, ev: SubAgentUpdated) -> None:
        line = self._subagent_lines.get(ev.task_id)
        if line is None:
            line = SubAgentLine(task_id=ev.task_id, prompt=ev.task_id, status=ev.status)
            self._subagent_lines[ev.task_id] = line
            self._chat_container().mount(line)
        line.update_status(ev.status)
        self._ensure_stream_panel_last()
        self._scroll_chat_end()

    def on_todo_display_closed(self, message: TodoDisplay.Closed) -> None:
        todo_display = self.query_one("#todo_display", TodoDisplay)
        todo_display.update_todos([])
        todo_display.display = False
        self.runtime.deps.todos = []

    def action_clear(self) -> None:
        chat = self._chat_container()
        for child in list(chat.children):
            child.remove()
        self.messages = []
        self._tool_lines.clear()
        self._subagent_lines.clear()
        self._streaming_assistant_panel = None

        try:
            bottom_bar = self.query_one(BottomBar)
            bottom_bar.update_info(input_tokens=0, output_tokens=0)
        except Exception:
            pass

        todo_display = self.query_one("#todo_display", TodoDisplay)
        todo_display.update_todos([])
        todo_display.display = False
        self.runtime.deps.todos = []
        self._show_welcome()

    def action_quit(self) -> None:
        self.runtime.close()
        self.exit()

    def action_cancel(self) -> None:
        if self._is_processing:
            self._append_message("⚠️ 正在取消...", role="system")

    def _chat_container(self) -> VerticalScroll:
        return self.query_one("#chat_container", VerticalScroll)

    def _append_message(self, content: str, role: str = "assistant") -> MessagePanel:
        panel = MessagePanel(content, role=role)
        chat = self._chat_container()
        chat.mount(panel)
        self._scroll_chat_end()
        return panel

    def _scroll_chat_end(self) -> None:
        chat = self._chat_container()
        chat.call_after_refresh(chat.scroll_end, animate=False)

    def _update_streaming_assistant(self, content: str) -> None:
        if self._streaming_assistant_panel is None:
            self._streaming_assistant_panel = self._append_message("", role="assistant")
        self._streaming_assistant_panel.set_content(content)
        self._scroll_chat_end()

    def _ensure_stream_panel_last(self) -> None:
        if self._streaming_assistant_panel is None:
            return
        chat = self._chat_container()
        try:
            self._streaming_assistant_panel.remove()
        except Exception:
            return
        chat.mount(self._streaming_assistant_panel)

    def _update_tokens(self, usage: Any) -> None:
        try:
            bottom_bar = self.query_one(BottomBar)
            input_tokens = getattr(usage, "request_tokens", 0) or getattr(usage, "input_tokens", 0)
            output_tokens = getattr(usage, "response_tokens", 0) or getattr(usage, "output_tokens", 0)
            bottom_bar.add_tokens(input_tokens, output_tokens)
        except Exception:
            pass

    # ---------------- @ 引用文件 ----------------

    def _show_mention_panel(self, at_pos: int, query: str, items: list[str]) -> None:
        self._mention_active = True
        self._mention_at_pos = at_pos
        self._mention_query = query
        self._mention_items = items
        self._mention_selected = 0
        self._refresh_mention_panel()
        self.call_later(self.query_one("#input", ChatInput).focus)

    def _refresh_mention_panel(self) -> None:
        container = self.query_one("#mention_container", Container)
        container.remove_children()
        panel = FileMentionPanel(self._mention_query, self._mention_items, self._mention_selected)
        container.mount(panel)
        container.display = True

    def _hide_mention_panel(self) -> None:
        if not self._mention_active:
            return
        self._mention_active = False
        self._mention_at_pos = None
        self._mention_query = ""
        self._mention_items = []
        self._mention_selected = 0
        try:
            container = self.query_one("#mention_container", Container)
            container.remove_children()
            container.display = False
        except Exception:
            pass

    def _handle_mention_key(self, key: str) -> bool:
        if not self._mention_active:
            return False
        if key == "escape":
            self._hide_mention_panel()
            return True
        if key in ("up", "down"):
            if not self._mention_items:
                return True
            if key == "up":
                self._mention_selected = max(0, self._mention_selected - 1)
            else:
                self._mention_selected = min(len(self._mention_items) - 1, self._mention_selected + 1)
            self._refresh_mention_panel()
            return True
        if key in ("tab", "enter"):
            if self._mention_items:
                self._accept_mention()
                return True
        return False

    def _accept_mention(self) -> None:
        if not self._mention_items or self._mention_at_pos is None:
            self._hide_mention_panel()
            return

        selected = self._mention_items[self._mention_selected]
        input_widget = self.query_one("#input", ChatInput)
        cursor_row, cursor_col = input_widget.cursor_location
        lines = (input_widget.text.split("\n") or [""])
        if cursor_row >= len(lines):
            lines += [""] * (cursor_row - len(lines) + 1)

        line = lines[cursor_row]
        at_pos = self._mention_at_pos
        before = line[: at_pos + 1]
        after = line[cursor_col:]
        insert = selected + " "
        lines[cursor_row] = before + insert + after
        input_widget.text = "\n".join(lines)
        input_widget.cursor_location = (cursor_row, len(before) + len(insert))
        input_widget.call_after_refresh(input_widget.scroll_cursor_visible)

        self._hide_mention_panel()
        self.call_later(input_widget.focus)

    def _search_files_for_mention(self, query: str) -> list[str]:
        fs = getattr(self.runtime, "fs", None)
        ignored = {".git", ".venv", "dist", "__pycache__", ".pytest_cache"}

        def is_ignored(p: str) -> bool:
            parts = p.split("/")
            return any(x in ignored for x in parts)

        patterns: list[str]
        if "/" in query or query.startswith("."):
            patterns = [f"{query}*"]
        else:
            patterns = [f"**/*{query}*"]

        results: list[str] = []
        seen: set[str] = set()
        for pat in patterns:
            try:
                matches = fs.glob(pat) if fs is not None else []
            except Exception:
                matches = []
            for m in matches:
                if m in seen:
                    continue
                if is_ignored(m):
                    continue
                try:
                    if not (self.runtime.cwd and os.path.isfile(os.path.join(self.runtime.cwd, m))):
                        continue
                except Exception:
                    continue
                seen.add(m)
                results.append(m)
                if len(results) >= 100:
                    return results
        return results


_AT_PATTERN = re.compile(r"(^|[\\s\\(\\[\\{\\\"'])@([^\\s@]*)$")


def _find_at_reference(text: str, cursor_pos: int) -> tuple[int, str] | None:
    prefix = text[:cursor_pos]
    m = _AT_PATTERN.search(prefix)
    if not m:
        return None
    at_pos = m.start(0) + len(m.group(1))
    query = m.group(2)
    return at_pos, query


def _tool_result_to_status(result_part: ToolReturnPart | RetryPromptPart) -> tuple[bool, str | None]:
    if isinstance(result_part, RetryPromptPart):
        return False, str(result_part.content)
    content = result_part.content
    if isinstance(content, ToolResult):
        return bool(content.success), content.error
    if hasattr(content, "success") and hasattr(content, "error"):
        try:
            ok = bool(getattr(content, "success"))
            err = getattr(content, "error", None)
            return ok, err
        except Exception:
            pass
    return True, None


def main() -> None:
    MiniCCApp().run()
