"""
MiniCC TUI 应用主模块

基于 Textual 实现的终端用户界面，支持流式对话和工具调用显示。
"""

import os
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll, Horizontal, Vertical
from textual.widgets import Footer, Header, Input, Static, TabbedContent, TabPane
from pydantic_ai import AgentRunResultEvent
from pydantic_ai.messages import PartDeltaEvent, PartStartEvent, TextPart, TextPartDelta

from .agent import create_agent
from .config import load_config
from .schemas import Config, MiniCCDeps
from .ui.widgets import MessagePanel, StatusBar, ToolCallPanel


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
        self.deps = MiniCCDeps(
            config=self.config,
            cwd=os.getcwd(),
            on_tool_call=self._on_tool_call
        )
        self.messages: list[Any] = []
        self._is_processing = False

    def compose(self) -> ComposeResult:
        """定义 UI 布局"""
        yield Header(show_clock=True)
        yield Horizontal(
            VerticalScroll(id="chat_container"),
            Vertical(
                StatusBar(id="status_bar"),
                Static(id="info_card"),
                TabbedContent(id="tabs"),
                id="side_panel"
            ),
            id="body"
        )
        yield Input(id="input", placeholder="输入消息... (Ctrl+C 退出)")
        yield Footer(id="footer")

    def on_mount(self) -> None:
        """应用挂载后初始化"""
        self.query_one("#input", Input).focus()
        # 初始化 Tab 页
        tabs = self.query_one(TabbedContent)
        tabs.add_pane(TabPane("工具", VerticalScroll(id="tool_container")))
        tabs.add_pane(TabPane("SubAgents", VerticalScroll(id="subagent_container")))

        self._show_welcome()
        self._set_status("就绪")
        self._refresh_info()
        self._refresh_subagents()

    def _show_welcome(self) -> None:
        """显示欢迎信息"""
        welcome = (
            "**MiniCC**\n"
            f"*模型*: `{self.config.provider.value}:{self.config.model}`\n"
            f"*工作目录*: `{self.deps.cwd}`"
        )
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
        self._set_status("处理中...")

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

        except Exception as e:
            self._append_message(f"❌ 错误: {e}", role="system")

        finally:
            self._is_processing = False
            self._set_status("就绪")
            # 自动滚动到底部
            self._chat_container().scroll_end()
            self._refresh_subagents()

    def _on_tool_call(
        self,
        tool_name: str,
        args: dict,
        result: Any
    ) -> None:
        """
        工具调用回调

        在工具执行后被调用，用于 UI 更新。
        """
        tool_panel = ToolCallPanel(tool_name, args, result)
        tools = self._tool_container()
        tools.mount(tool_panel)
        tools.scroll_end()
        self._set_status(f"执行工具: {tool_name}")

        # 恢复处理中状态（后续可能还有工具/回复）
        if self._is_processing:
            self._set_status("处理中...")
        self._refresh_subagents()

    def action_clear(self) -> None:
        """清屏动作"""
        chat = self._chat_container()
        for child in list(chat.children):
            child.remove()
        tools = self._tool_container()
        for child in list(tools.children):
            child.remove()
        self.messages = []
        self._show_welcome()

    def action_quit(self) -> None:
        """退出动作"""
        self.exit()

    def action_cancel(self) -> None:
        """取消当前操作"""
        if self._is_processing:
            self._append_message("⚠️ 正在取消...", role="system")
            # 注意：pydantic-ai 目前不支持取消正在进行的请求
            # 这里只是标记状态
            self._set_status("取消请求中")

    def _set_status(self, text: str) -> None:
        """更新状态栏文本"""
        try:
            status = self.query_one(StatusBar)
            status.update_status(text)
        except Exception:
            pass

    def _chat_container(self) -> VerticalScroll:
        return self.query_one("#chat_container", VerticalScroll)

    def _tool_container(self) -> VerticalScroll:
        return self.query_one("#tool_container", VerticalScroll)

    def _subagent_container(self) -> VerticalScroll:
        return self.query_one("#subagent_container", VerticalScroll)

    def _append_message(self, content: str, role: str = "assistant") -> MessagePanel:
        panel = MessagePanel(content, role=role)
        chat = self._chat_container()
        chat.mount(panel)
        chat.scroll_end()
        return panel

    def _refresh_info(self) -> None:
        """更新侧边信息卡片"""
        try:
            info = self.query_one("#info_card", Static)
            info.update(
                "**会话信息**\n"
                f"- 模型: `{self.config.provider.value}:{self.config.model}`\n"
                f"- 工作目录: `{self.deps.cwd}`"
            )
        except Exception:
            pass

    def _refresh_subagents(self) -> None:
        """刷新子任务状态展示"""
        try:
            container = self._subagent_container()
            for child in list(container.children):
                child.remove()
            if not self.deps.sub_agents:
                container.mount(Static("[dim]暂无 SubAgent[/dim]"))
                return

            for tid, task in self.deps.sub_agents.items():
                container.mount(Static(f"[dim]{tid}[/dim] {task.status}"))
        except Exception:
            pass


def main() -> None:
    """CLI 入口函数"""
    app = MiniCCApp()
    app.run()


if __name__ == "__main__":
    main()
