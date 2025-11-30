"""
MiniCC TUI 应用主模块

基于 Textual 实现的终端用户界面，支持流式对话和工具调用显示。
"""

import os
import subprocess
from typing import Any

from agent_gear import FileSystem
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Footer, Header, Input
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPart, TextPartDelta

from .agent import create_agent
from .config import load_config
from .schemas import AskUserRequest, AskUserResponse, Config, MiniCCDeps, UserCancelledError
from .ui.widgets import MessagePanel, BottomBar, ToolCallLine, SubAgentLine, TodoDisplay
from .ui.ask_user_panel import AskUserPanel
from textual.containers import Container


class MiniCCApp(App):
    """
    MiniCC 终端应用

    提供聊天界面，支持与 AI Agent 进行对话。

    Attributes:
        config: 应用配置
        agent: pydantic-ai Agent 实例
        deps: Agent 依赖注入
        messages: 对话历史
    """

    TITLE = "MiniCC"
    CSS_PATH = "ui/styles.tcss"

    BINDINGS = [
        Binding("ctrl+c", "quit", "退出", priority=True),
        Binding("ctrl+l", "clear", "清屏"),
        Binding("escape", "cancel", "取消"),
    ]

    def __init__(self, config: Config | None = None):
        """
        初始化应用

        Args:
            config: 可选配置，为 None 时从文件加载
        """
        super().__init__()
        self.config = config or load_config()
        self.agent = create_agent(self.config)
        cwd = os.getcwd()

        # 初始化 Agent-Gear FileSystem（全局单例，启用文件监听）
        self._fs = FileSystem(cwd, auto_watch=True)

        self.deps = MiniCCDeps(
            config=self.config,
            cwd=cwd,
            fs=self._fs,
            on_tool_call=self._on_tool_call,
            on_todo_update=self._on_todo_update,
            on_ask_user=self._on_ask_user
        )
        self.messages: list[Any] = []
        self._is_processing = False
        self._git_branch = self._get_git_branch()
        self._current_ask_panel: AskUserPanel | None = None

    def _get_git_branch(self) -> str | None:
        """获取当前 git 分支名"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                capture_output=True,
                text=True,
                cwd=self.deps.cwd,
                timeout=2
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def compose(self) -> ComposeResult:
        """定义 UI 布局"""
        yield Header(show_clock=True)
        yield VerticalScroll(id="chat_container")
        yield TodoDisplay(id="todo_display")  # 固定的任务列表区域
        yield Container(id="ask_user_container")  # ask_user 面板容器（固定在输入框上方）
        yield Input(id="input", placeholder="输入消息... (Ctrl+C 退出)")
        yield BottomBar(
            model=f"{self.config.provider.value}:{self.config.model}",
            cwd=self.deps.cwd,
            git_branch=self._git_branch,
            id="bottom_bar"
        )
        yield Footer(id="footer")

    def on_mount(self) -> None:
        """应用挂载后初始化"""
        self.query_one("#input", Input).focus()
        # 初始隐藏空的任务列表
        self.query_one("#todo_display", TodoDisplay).display = False
        # 初始隐藏 ask_user 容器
        self.query_one("#ask_user_container", Container).display = False
        self._show_welcome()
        # 等待 FileSystem 索引就绪（后台进行，不阻塞 UI）
        self._wait_fs_ready()

    @work(thread=True)
    def _wait_fs_ready(self) -> None:
        """后台等待 FileSystem 索引就绪"""
        if self._fs:
            self._fs.wait_ready(timeout=30.0)

    def _show_welcome(self) -> None:
        """显示欢迎信息"""
        welcome = "**MiniCC** - 极简 AI 编程助手\n\n输入问题开始对话，Ctrl+C 退出"
        self._append_message(welcome, role="system")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """处理用户输入提交"""
        user_input = event.value.strip()
        if not user_input:
            return

        if self._is_processing:
            self._append_message("⚠️ 请等待当前请求完成...", role="system")
            return

        # 清空输入框
        input_widget = self.query_one("#input", Input)
        input_widget.clear()

        # 显示用户消息
        self._append_message(user_input, role="user")

        # 后台处理
        self._process_message(user_input)

    @work(exclusive=True)
    async def _process_message(self, user_input: str) -> None:
        """
        后台处理用户消息

        使用 @work 装饰器确保不阻塞 UI，exclusive=True 防止并发请求。
        """
        self._is_processing = True

        try:
            # 使用 run_stream_events 确保工具调用后的循环不会提前结束
            streamed_text = ""
            async for event in self.agent.run_stream_events(
                user_input,
                deps=self.deps,
                message_history=self.messages
            ):
                if isinstance(event, PartStartEvent) and isinstance(event.part, TextPart):
                    streamed_text += event.part.content
                elif isinstance(event, PartDeltaEvent) and isinstance(event.delta, TextPartDelta):
                    streamed_text += event.delta.content_delta
                elif isinstance(event, AgentRunResultEvent):
                    # 优先使用流式累积的文本，否则回退到最终输出
                    final_text = streamed_text or str(event.result.output)
                    self._append_message(final_text, role="assistant")
                    self.messages = event.result.all_messages()
                    # 更新 token 使用量
                    usage = event.result.usage()
                    if usage:
                        self._update_tokens(usage)

        except UserCancelledError:
            self._append_message("⚠️ 操作已取消", role="system")

        except Exception as e:
            self._append_message(f"❌ 错误: {e}", role="system")

        finally:
            self._is_processing = False
            # 自动滚动到底部
            self._chat_container().scroll_end()

    def _on_tool_call(
        self,
        tool_name: str,
        args: dict,
        result: Any
    ) -> None:
        """
        工具调用回调

        在工具执行后被调用，将工具调用显示到会话框。
        """
        # 检查是否是 task 工具（原 spawn_agent）
        if tool_name == "task":
            description = args.get("description", "")
            line = SubAgentLine(
                task_id=result.output if result.success else "unknown",
                prompt=description,
                status="running" if result.success else "failed"
            )
        else:
            line = ToolCallLine(tool_name, args, result)

        chat = self._chat_container()
        chat.mount(line)
        chat.scroll_end(animate=False)

    def _on_todo_update(self, todos: list) -> None:
        """
        任务列表更新回调

        当 todo_write 工具被调用时触发，更新固定的任务列表显示。
        """
        try:
            todo_display = self.query_one("#todo_display", TodoDisplay)
            todo_display.update_todos(todos)
            # 有任务时显示，无任务时隐藏
            todo_display.display = len(todos) > 0
        except Exception:
            pass

    def _on_ask_user(self, request: AskUserRequest) -> None:
        """
        ask_user 回调

        当 ask_user 工具被调用时触发，显示问答面板（固定在输入框上方）。
        """
        panel = AskUserPanel(request.questions)
        self._current_ask_panel = panel
        container = self.query_one("#ask_user_container", Container)
        container.mount(panel)
        container.display = True
        # 禁用主输入框并让面板获取焦点
        main_input = self.query_one("#input", Input)
        main_input.disabled = True
        # 使用 call_later 确保面板完全挂载后再获取焦点
        self.call_later(panel.focus)

    def _remove_ask_panel(self) -> None:
        """移除当前问答面板"""
        if self._current_ask_panel:
            self._current_ask_panel.remove()
            self._current_ask_panel = None
        try:
            container = self.query_one("#ask_user_container", Container)
            container.display = False
        except Exception:
            pass
        # 恢复主输入框并获取焦点
        try:
            main_input = self.query_one("#input", Input)
            main_input.disabled = False
            main_input.focus()
        except Exception:
            pass

    def on_ask_user_panel_submitted(self, event: AskUserPanel.Submitted) -> None:
        """处理用户提交问答"""
        self._remove_ask_panel()
        self.deps.ask_user_response = AskUserResponse(
            submitted=True,
            answers=event.answers
        )
        if self.deps.ask_user_event:
            self.deps.ask_user_event.set()

    def on_ask_user_panel_cancelled(self, event: AskUserPanel.Cancelled) -> None:
        """处理用户取消问答"""
        self._remove_ask_panel()
        self.deps.ask_user_response = AskUserResponse(
            submitted=False,
            answers={}
        )
        if self.deps.ask_user_event:
            self.deps.ask_user_event.set()

    def on_todo_display_closed(self, message: TodoDisplay.Closed) -> None:
        """处理任务列表关闭事件"""
        try:
            todo_display = self.query_one("#todo_display", TodoDisplay)
            todo_display.update_todos([])
            todo_display.display = False
            self.deps.todos = []
        except Exception:
            pass

    def action_clear(self) -> None:
        """清屏动作"""
        chat = self._chat_container()
        for child in list(chat.children):
            child.remove()
        self.messages = []
        # 重置 token 计数
        try:
            bottom_bar = self.query_one(BottomBar)
            bottom_bar.update_info(input_tokens=0, output_tokens=0)
        except Exception:
            pass
        # 清除并隐藏 todo 列表
        try:
            todo_display = self.query_one("#todo_display", TodoDisplay)
            todo_display.update_todos([])
            todo_display.display = False
            self.deps.todos = []
        except Exception:
            pass
        self._show_welcome()

    def action_quit(self) -> None:
        """退出动作"""
        # 关闭 FileSystem 释放资源
        if self._fs:
            self._fs.close()
        self.exit()

    def action_cancel(self) -> None:
        """取消当前操作"""
        if self._is_processing:
            self._append_message("⚠️ 正在取消...", role="system")

    def _chat_container(self) -> VerticalScroll:
        return self.query_one("#chat_container", VerticalScroll)

    def _append_message(self, content: str, role: str = "assistant") -> MessagePanel:
        panel = MessagePanel(content, role=role)
        chat = self._chat_container()
        chat.mount(panel)
        chat.scroll_end(animate=False)
        return panel

    def _update_tokens(self, usage: Any) -> None:
        """更新 token 使用量到底边栏"""
        try:
            bottom_bar = self.query_one(BottomBar)
            input_tokens = getattr(usage, "request_tokens", 0) or getattr(usage, "input_tokens", 0)
            output_tokens = getattr(usage, "response_tokens", 0) or getattr(usage, "output_tokens", 0)
            bottom_bar.add_tokens(input_tokens, output_tokens)
        except Exception:
            pass


def main() -> None:
    """CLI 入口函数"""
    app = MiniCCApp()
    app.run()


if __name__ == "__main__":
    main()
