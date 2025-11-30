"""
MiniCC Ask User Panel 组件

提供 ask_user 工具的可交互问答面板。
"""

from rich.panel import Panel
from rich.text import Text
from textual.widgets import Static
from textual.message import Message

from ..schemas import Question


class AskUserPanel(Static, can_focus=True):
    """
    用户问答面板（表单向导样式）

    用于 ask_user 工具，显示可交互的问答界面。
    使用纯 render() 方式渲染，确保显示正确。
    """

    BINDINGS = [
        ("left", "prev_question", "上一个问题"),
        ("right", "next_question", "下一个问题"),
        ("up", "prev_option", "上一个选项"),
        ("down", "next_option", "下一个选项"),
        ("enter", "select_option", "选择"),
        ("escape", "cancel", "取消"),
    ]

    class Submitted(Message):
        """提交事件"""
        def __init__(self, answers: dict[str, str | list[str]]):
            self.answers = answers
            super().__init__()

    class Cancelled(Message):
        """取消事件"""
        pass

    def __init__(self, questions: list[Question], **kwargs):
        self.questions = questions
        self.current_question = 0
        self.current_option = 0
        self.typing_mode = False  # 是否在输入自定义内容
        self.typing_buffer = ""   # 输入缓冲
        # 存储每个问题的答案：单选为 int 索引，多选为 set
        self.answers: dict[int, int | set] = {}
        # 自定义输入内容
        self.custom_inputs: dict[int, str] = {}
        # 初始化答案
        for i, q in enumerate(self.questions):
            if q.multi_select:
                self.answers[i] = set()
            else:
                self.answers[i] = -1  # -1 表示未选择
        super().__init__(**kwargs)

    def render(self) -> Panel:
        """渲染问答面板"""
        text = Text()

        # 1. 顶部导航栏
        text.append("← ", style="dim")
        for i, q in enumerate(self.questions):
            if i == self.current_question:
                text.append(f" □ {q.header} ", style="bold reverse magenta")
            else:
                answered = self._is_answered(i)
                if answered:
                    text.append(f" □ {q.header} ", style="green")
                else:
                    text.append(f" □ {q.header} ", style="dim")

        text.append(" →\n\n", style="dim")

        # 2. 当前问题标题
        q = self.questions[self.current_question]
        multi_hint = "（可多选）" if q.multi_select else ""
        text.append(f"{q.question} {multi_hint}\n\n", style="bold cyan")

        # 3. 选项列表
        for j, opt in enumerate(q.options):
            is_selected = self.current_option == j and not self.typing_mode
            is_checked = self._is_option_checked(self.current_question, j)

            # 选中标记
            if is_selected:
                text.append("❯ ", style="bold yellow")
            else:
                text.append("  ")

            # 编号
            text.append(f"{j + 1}. ", style="bold" if is_selected else "dim")

            # 选项标签
            if is_checked:
                text.append(f"{opt.label}", style="bold green")
                if q.multi_select:
                    text.append(" ✓", style="green")
            else:
                text.append(f"{opt.label}", style="bold" if is_selected else "")

            text.append("\n")

            # 选项描述
            if opt.description:
                text.append(f"    {opt.description}\n", style="dim italic")

        # 4. 自定义输入选项
        custom_idx = len(q.options)
        is_selected = self.current_option == custom_idx or self.typing_mode
        is_custom_active = self._is_custom_selected(self.current_question)

        if is_selected:
            text.append("❯ ", style="bold yellow")
        else:
            text.append("  ")

        text.append(f"{custom_idx + 1}. ", style="bold" if is_selected else "dim")

        # 显示自定义输入
        custom_text = self.custom_inputs.get(self.current_question, "")
        if self.typing_mode:
            # 输入模式：显示带光标的输入
            text.append("Type: ", style="dim")
            text.append(self.typing_buffer, style="bold cyan")
            text.append("█", style="bold cyan blink")  # 光标
        elif custom_text:
            text.append(f"Type: {custom_text}", style="bold green" if is_custom_active else "green")
            if q.multi_select and is_custom_active:
                text.append(" ✓", style="green")
        else:
            text.append("Type something.", style="bold" if is_selected else "dim italic")

        text.append("\n\n")

        # 5. 底部提示
        all_answered = all(self._is_answered(i) for i in range(len(self.questions)))
        if self.typing_mode:
            text.append("输入内容，Enter 确认，Esc 取消", style="dim")
        elif all_answered:
            text.append("✔ 全部已选择，按 ", style="green")
            text.append("S", style="bold green reverse")
            text.append(" 提交 · Esc 取消", style="green")
        else:
            text.append("Enter 选择 · ←→ 切换问题 · ↑↓ 移动 · Esc 取消", style="dim")

        return Panel(
            text,
            title="📝 请回答以下问题",
            border_style="cyan",
            padding=(0, 1),
        )

    def _is_answered(self, q_idx: int) -> bool:
        """检查问题是否已回答"""
        ans = self.answers.get(q_idx)
        if isinstance(ans, set):
            return len(ans) > 0
        elif isinstance(ans, int):
            return ans >= 0
        return False

    def _is_option_checked(self, q_idx: int, opt_idx: int) -> bool:
        """检查选项是否被选中"""
        ans = self.answers.get(q_idx)
        if isinstance(ans, set):
            return opt_idx in ans
        elif isinstance(ans, int):
            return ans == opt_idx
        return False

    def _is_custom_selected(self, q_idx: int) -> bool:
        """检查自定义输入是否被选中"""
        ans = self.answers.get(q_idx)
        custom_idx = len(self.questions[q_idx].options)
        if isinstance(ans, set):
            return custom_idx in ans
        elif isinstance(ans, int):
            return ans == custom_idx
        return False

    def action_prev_question(self) -> None:
        """切换到上一个问题"""
        if self.typing_mode:
            return
        if self.current_question > 0:
            self.current_question -= 1
            self.current_option = 0
            self.refresh()

    def action_next_question(self) -> None:
        """切换到下一个问题"""
        if self.typing_mode:
            return
        if self.current_question < len(self.questions) - 1:
            self.current_question += 1
            self.current_option = 0
            self.refresh()

    def action_prev_option(self) -> None:
        """切换到上一个选项"""
        if self.typing_mode:
            return
        if self.current_option > 0:
            self.current_option -= 1
            self.refresh()

    def action_next_option(self) -> None:
        """切换到下一个选项"""
        if self.typing_mode:
            return
        q = self.questions[self.current_question]
        max_option = len(q.options)  # 包括自定义输入
        if self.current_option < max_option:
            self.current_option += 1
            self.refresh()

    def action_select_option(self) -> None:
        """选择当前选项"""
        if self.typing_mode:
            # 确认输入
            self._confirm_typing()
            return

        q = self.questions[self.current_question]
        custom_idx = len(q.options)

        if self.current_option == custom_idx:
            # 进入输入模式
            self.typing_mode = True
            self.typing_buffer = self.custom_inputs.get(self.current_question, "")
            self.refresh()
        else:
            # 普通选项
            if q.multi_select:
                # 多选：切换选中状态
                ans = self.answers[self.current_question]
                if isinstance(ans, set):
                    if self.current_option in ans:
                        ans.remove(self.current_option)
                    else:
                        ans.add(self.current_option)
            else:
                # 单选：设置选中
                self.answers[self.current_question] = self.current_option

            self.refresh()

    def _confirm_typing(self) -> None:
        """确认输入"""
        q = self.questions[self.current_question]
        custom_idx = len(q.options)
        value = self.typing_buffer.strip()

        self.custom_inputs[self.current_question] = value
        self.typing_mode = False

        if value:
            # 有输入时，标记为选中自定义
            if q.multi_select:
                ans = self.answers[self.current_question]
                if isinstance(ans, set):
                    ans.add(custom_idx)
            else:
                self.answers[self.current_question] = custom_idx
        else:
            # 输入为空时，取消选中自定义
            if q.multi_select:
                ans = self.answers[self.current_question]
                if isinstance(ans, set):
                    ans.discard(custom_idx)
            else:
                if self.answers[self.current_question] == custom_idx:
                    self.answers[self.current_question] = -1

        self.refresh()

    def action_cancel(self) -> None:
        """取消操作"""
        if self.typing_mode:
            # 取消输入
            self.typing_mode = False
            self.typing_buffer = ""
            self.refresh()
        else:
            self.post_message(self.Cancelled())

    def on_key(self, event) -> None:
        """处理按键"""
        key = event.key

        if self.typing_mode:
            # 输入模式
            if key == "backspace":
                self.typing_buffer = self.typing_buffer[:-1]
                self.refresh()
                event.stop()
            elif key == "enter":
                self._confirm_typing()
                event.stop()
            elif key == "escape":
                self.typing_mode = False
                self.typing_buffer = ""
                self.refresh()
                event.stop()
            elif len(key) == 1 and key.isprintable():
                self.typing_buffer += key
                self.refresh()
                event.stop()
        else:
            # 普通模式
            if key.isdigit():
                num = int(key)
                q = self.questions[self.current_question]
                max_option = len(q.options) + 1
                if 1 <= num <= max_option:
                    self.current_option = num - 1
                    self.action_select_option()
                    event.stop()
            elif key == "s" or key == "S":
                # S 键提交
                all_answered = all(self._is_answered(i) for i in range(len(self.questions)))
                if all_answered:
                    self._submit()
                    event.stop()

    def _submit(self) -> None:
        """提交答案"""
        answers = self._collect_answers()
        self.post_message(self.Submitted(answers))

    def _collect_answers(self) -> dict[str, str | list[str]]:
        """收集所有答案"""
        result: dict[str, str | list[str]] = {}

        for i, q in enumerate(self.questions):
            ans = self.answers.get(i)
            custom_idx = len(q.options)

            if q.multi_select:
                selected = []
                if isinstance(ans, set):
                    for idx in sorted(ans):
                        if idx == custom_idx:
                            custom_text = self.custom_inputs.get(i, "")
                            if custom_text:
                                selected.append(custom_text)
                        elif 0 <= idx < len(q.options):
                            selected.append(q.options[idx].label)
                result[q.header] = selected
            else:
                if isinstance(ans, int):
                    if ans == custom_idx:
                        result[q.header] = self.custom_inputs.get(i, "")
                    elif 0 <= ans < len(q.options):
                        result[q.header] = q.options[ans].label
                    else:
                        result[q.header] = ""
                else:
                    result[q.header] = ""

        return result
