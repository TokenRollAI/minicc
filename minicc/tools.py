"""
MiniCC 工具函数实现

定义所有可供 Agent 调用的工具，使用 pydantic-ai 的工具注册模式。
对标 Claude Code 工具系统，使用高性能第三方库实现。

工具分类:
- 文件操作: read_file, write_file, edit_file
- 搜索: glob_files, grep_search
- 命令行: bash, bash_output, kill_shell
- 任务管理: task, todo_write
- Notebook: notebook_edit
"""

from __future__ import annotations

import asyncio
import difflib
import json
import re
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from pydantic_ai import RunContext

from .schemas import (AgentTask, BackgroundShell, DiffLine, MiniCCDeps,
                      TodoItem, ToolResult)

# ============ 常量配置 ============

DEFAULT_READ_LIMIT = 2000  # 默认读取行数
MAX_OUTPUT_CHARS = 30000   # 输出截断阈值
DEFAULT_BASH_TIMEOUT_MS = 120000  # 默认超时 2 分钟


# ============ 文件操作工具 ============


async def read_file(
    ctx: RunContext[MiniCCDeps],
    file_path: str,
    offset: int | None = None,
    limit: int | None = None,
) -> ToolResult:
    """
    读取指定路径的文件内容，使用 cat -n 格式输出（行号从1开始）

    使用 Agent-Gear 的高性能文件读取，支持大文件的分段读取。

    Args:
        file_path: 文件的绝对或相对路径
        offset: 起始行号（1-indexed，默认为1）
        limit: 读取行数（默认2000行）

    Returns:
        带行号的文件内容，若文件不存在则返回错误
    """
    fs = ctx.deps.fs
    try:
        resolved = _resolve_path(ctx.deps.cwd, file_path)
        rel_path = str(resolved.relative_to(ctx.deps.cwd)) if resolved.is_absolute() else file_path

        # 使用 agent-gear 的 read_lines 进行分段读取
        start_line = (offset or 1) - 1  # 转为 0-indexed
        count = limit or DEFAULT_READ_LIMIT

        lines = fs.read_lines(rel_path, start_line=start_line, count=count)

        if not lines:
            # 检查文件是否存在
            try:
                fs.read_file(rel_path)
                # 文件存在但为空或偏移超出范围
                return _finalize(
                    ctx, "read_file", {"file_path": file_path, "offset": offset, "limit": limit},
                    ToolResult(success=True, output="（文件为空或偏移超出范围）")
                )
            except Exception:
                return _finalize(
                    ctx, "read_file", {"file_path": file_path},
                    ToolResult(success=False, output="", error=f"文件不存在: {file_path}")
                )

        # 格式化为 cat -n 风格（行号 + tab + 内容）
        formatted = []
        for i, line in enumerate(lines, start=start_line + 1):
            # 截断过长的行
            if len(line) > 2000:
                line = line[:2000] + "..."
            formatted.append(f"{i:6}\t{line}")

        output = "\n".join(formatted)

        # 添加截断提示（如果读取到了请求的行数，可能还有更多）
        if len(lines) >= count:
            output += f"\n\n... 可能还有更多行未显示"

        return _finalize(
            ctx, "read_file", {"file_path": file_path, "offset": offset, "limit": limit},
            ToolResult(success=True, output=output)
        )

    except Exception as e:
        error_msg = str(e)
        if "binary" in error_msg.lower() or "decode" in error_msg.lower():
            error_msg = "无法读取文件：可能是二进制文件"
        return _finalize(
            ctx, "read_file", {"file_path": file_path},
            ToolResult(success=False, output="", error=error_msg)
        )


async def write_file(
    ctx: RunContext[MiniCCDeps],
    file_path: str,
    content: str,
) -> ToolResult:
    """
    创建或覆盖写入文件（原子写入）

    使用 Agent-Gear 的原子写入（temp-fsync-rename 模式），保证数据完整性。
    会自动创建不存在的父目录。

    Args:
        file_path: 目标文件的绝对或相对路径
        content: 要写入的完整内容

    Returns:
        写入成功/失败信息
    """
    fs = ctx.deps.fs
    try:
        resolved = _resolve_path(ctx.deps.cwd, file_path)

        # 创建父目录（agent-gear 不自动创建）
        resolved.parent.mkdir(parents=True, exist_ok=True)

        rel_path = str(resolved.relative_to(ctx.deps.cwd)) if resolved.is_absolute() else file_path

        # 使用 agent-gear 的原子写入
        success = fs.write_file(rel_path, content)

        if success:
            return _finalize(
                ctx, "write_file", {"file_path": file_path, "content": f"<{len(content)} chars>"},
                ToolResult(success=True, output=f"已写入文件: {file_path} ({len(content)} 字符)")
            )
        else:
            return _finalize(
                ctx, "write_file", {"file_path": file_path},
                ToolResult(success=False, output="", error="写入失败")
            )

    except Exception as e:
        return _finalize(
            ctx, "write_file", {"file_path": file_path},
            ToolResult(success=False, output="", error=str(e))
        )


async def edit_file(
    ctx: RunContext[MiniCCDeps],
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> ToolResult:
    """
    精确字符串替换（严格模式）

    使用 Agent-Gear 进行高性能文件编辑，支持原子写入。
    在文件中查找 old_string 并替换为 new_string。
    仅允许空白/缩进差异容错（tabs vs spaces）。

    Args:
        file_path: 文件路径
        old_string: 要被替换的原内容（必须精确匹配）
        new_string: 替换后的新内容（必须与 old_string 不同）
        replace_all: 是否替换所有出现（默认 False，要求唯一）

    Returns:
        更新结果和 diff 预览
    """
    fs = ctx.deps.fs
    try:
        resolved = _resolve_path(ctx.deps.cwd, file_path)
        rel_path = str(resolved.relative_to(ctx.deps.cwd)) if resolved.is_absolute() else file_path

        # 读取当前内容
        try:
            current_content = fs.read_file(rel_path)
        except Exception:
            return _finalize(
                ctx, "edit_file", {"file_path": file_path},
                ToolResult(success=False, output="", error=f"文件不存在: {file_path}")
            )

        # 检查是否需要空白容错
        exact_count = current_content.count(old_string)

        if exact_count == 0:
            # 尝试空白容错匹配
            normalized_old = _normalize_whitespace(old_string)
            match_result = _find_whitespace_tolerant(current_content, normalized_old)

            if match_result is None:
                return _finalize(
                    ctx, "edit_file", {"file_path": file_path},
                    ToolResult(
                        success=False, output="",
                        error="未找到要替换的内容，请确保 old_string 精确匹配文件内容"
                    )
                )

            # 使用找到的实际内容进行替换
            actual_old = match_result
            exact_count = 1  # 空白容错模式下视为单次匹配

        else:
            actual_old = old_string

        if not replace_all and exact_count > 1:
            return _finalize(
                ctx, "edit_file", {"file_path": file_path},
                ToolResult(
                    success=False, output="",
                    error=f"old_string 在文件中出现了 {exact_count} 次，"
                          f"请提供更精确的内容或使用 replace_all=True"
                )
            )

        if old_string == new_string:
            return _finalize(
                ctx, "edit_file", {"file_path": file_path},
                ToolResult(
                    success=False, output="",
                    error="new_string 必须与 old_string 不同"
                )
            )

        # 执行替换
        if replace_all:
            new_content = current_content.replace(actual_old, new_string)
            replaced_count = exact_count
        else:
            new_content = current_content.replace(actual_old, new_string, 1)
            replaced_count = 1

        # 使用 agent-gear 的原子写入
        fs.write_file(rel_path, new_content)

        # 生成 diff
        diff_output = _generate_unified_diff(actual_old, new_string, file_path)

        return _finalize(
            ctx, "edit_file",
            {"file_path": file_path, "old_string": old_string[:50], "new_string": new_string[:50]},
            ToolResult(
                success=True,
                output=f"已更新文件: {file_path} ({replaced_count} 处替换)\n\n{diff_output}"
            )
        )

    except Exception as e:
        return _finalize(
            ctx, "edit_file", {"file_path": file_path},
            ToolResult(success=False, output="", error=str(e))
        )


# ============ 搜索工具 ============


async def glob_files(
    ctx: RunContext[MiniCCDeps],
    pattern: str,
    path: str | None = None,
) -> ToolResult:
    """
    高级文件模式匹配

    使用 Agent-Gear 的内存索引和 LRU 缓存，提供 2-3x 加速。
    支持扩展 glob 语法：
    - **/*.py: 递归匹配所有 Python 文件
    - {src,test}/*.ts: 花括号扩展
    - **/*.{js,ts}: 多扩展名

    自动忽略 .gitignore 中的文件，按修改时间排序。

    Args:
        pattern: glob 模式
        path: 搜索起始路径（默认为当前目录）

    Returns:
        匹配的文件列表
    """
    fs = ctx.deps.fs
    try:
        # Agent-Gear 的 glob 方法使用内存索引，性能更好
        # 如果指定了 path，需要构造完整模式
        if path:
            full_pattern = f"{path}/{pattern}"
        else:
            full_pattern = pattern

        matches = fs.glob(full_pattern)

        if not matches:
            return _finalize(
                ctx, "glob_files", {"pattern": pattern, "path": path},
                ToolResult(success=True, output=f"未找到匹配 '{pattern}' 的文件")
            )

        # 结果已经是相对路径列表
        output = "\n".join(matches)

        return _finalize(
            ctx, "glob_files", {"pattern": pattern, "path": path},
            ToolResult(success=True, output=output)
        )

    except Exception as e:
        return _finalize(
            ctx, "glob_files", {"pattern": pattern, "path": path},
            ToolResult(success=False, output="", error=str(e))
        )


async def grep_search(
    ctx: RunContext[MiniCCDeps],
    pattern: str,
    path: str | None = None,
    glob: str | None = None,
    output_mode: Literal["content", "files_with_matches", "count"] = "files_with_matches",
    context_before: int | None = None,
    context_after: int | None = None,
    context: int | None = None,
    case_insensitive: bool = False,
    head_limit: int | None = None,
    file_type: str | None = None,
) -> ToolResult:
    """
    使用 Agent-Gear 进行高性能代码搜索

    基于 ripgrep 核心库，支持并行处理和内存映射 I/O。
    自动尊重 .gitignore，支持正则表达式。

    Args:
        pattern: 正则表达式模式
        path: 搜索路径（默认当前目录）
        glob: 文件过滤模式（如 "*.py", "*.{ts,tsx}"）
        output_mode: 输出模式
            - "content": 显示匹配行内容
            - "files_with_matches": 仅显示文件路径（默认）
            - "count": 显示匹配计数
        context_before: 显示匹配前 N 行（-B）
        context_after: 显示匹配后 N 行（-A）
        context: 显示匹配前后各 N 行（-C）
        case_insensitive: 忽略大小写（-i）
        head_limit: 限制结果数量
        file_type: 文件类型过滤（如 "py", "js", "rust"）

    Returns:
        搜索结果
    """
    fs = ctx.deps.fs

    # Agent-Gear 支持基本的 grep 功能，但对于需要上下文行或 file_type 过滤的情况，使用 ripgrepy
    need_context = context or context_before or context_after
    if need_context or file_type:
        return await _grep_ripgrepy(
            ctx, pattern, path, glob, output_mode,
            context_before, context_after, context,
            case_insensitive, head_limit, file_type
        )

    try:
        # 构建 glob 模式
        glob_pattern = glob or "**/*"
        if path:
            glob_pattern = f"{path}/{glob_pattern}"

        # 使用 Agent-Gear 的高性能 grep
        results = fs.grep(
            pattern,
            glob_pattern,
            case_sensitive=not case_insensitive,
            max_results=head_limit
        )

        if not results:
            return _finalize(
                ctx, "grep_search", {"pattern": pattern, "path": path},
                ToolResult(success=True, output=f"未找到匹配 '{pattern}' 的内容")
            )

        # 根据输出模式格式化结果
        if output_mode == "files_with_matches":
            # 只显示文件路径（去重）
            files = list(dict.fromkeys(r.file for r in results))
            output = "\n".join(files)
        elif output_mode == "count":
            # 统计每个文件的匹配数
            file_counts: dict[str, int] = {}
            for r in results:
                file_counts[r.file] = file_counts.get(r.file, 0) + 1
            output = "\n".join(f"{f}:{c}" for f, c in file_counts.items())
        else:
            # 显示完整内容
            output_lines = []
            for r in results:
                content = r.content.strip() if hasattr(r, 'content') else ""
                line_no = r.line_number if hasattr(r, 'line_number') else 0
                output_lines.append(f"{r.file}:{line_no}:{content}")
            output = "\n".join(output_lines)

        # 截断过长输出
        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n... 输出已截断"

        return _finalize(
            ctx, "grep_search", {"pattern": pattern, "path": path, "output_mode": output_mode},
            ToolResult(success=True, output=output)
        )

    except Exception as e:
        return _finalize(
            ctx, "grep_search", {"pattern": pattern, "path": path},
            ToolResult(success=False, output="", error=str(e))
        )


# ============ 命令行工具 ============


async def bash(
    ctx: RunContext[MiniCCDeps],
    command: str,
    timeout: int = DEFAULT_BASH_TIMEOUT_MS,
    description: str | None = None,
    run_in_background: bool = False,
) -> ToolResult:
    """
    执行 bash 命令

    在当前工作目录下执行 shell 命令。

    Args:
        command: 要执行的命令
        timeout: 超时毫秒数（默认 120000ms = 2分钟，最大 600000ms = 10分钟）
        description: 命令的简短描述（5-10词）
        run_in_background: 是否在后台运行

    Returns:
        命令输出（stdout + stderr）
    """
    # 限制超时范围
    timeout = min(max(timeout, 1000), 600000)
    timeout_sec = timeout / 1000

    if run_in_background:
        return await _bash_background(ctx, command, description or command[:30])

    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=ctx.deps.cwd,
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout_sec
            )

            stdout_str = stdout.decode("utf-8", errors="replace")
            stderr_str = stderr.decode("utf-8", errors="replace")

            # 合并输出
            output = stdout_str
            if stderr_str:
                output += f"\n[stderr]\n{stderr_str}" if output else stderr_str

            # 截断过长输出
            if len(output) > MAX_OUTPUT_CHARS:
                output = output[:MAX_OUTPUT_CHARS] + "\n... 输出已截断"

            success = process.returncode == 0
            error = None if success else f"退出码: {process.returncode}"

            return _finalize(
                ctx, "bash", {"command": command, "description": description},
                ToolResult(success=success, output=output, error=error)
            )

        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            return _finalize(
                ctx, "bash", {"command": command},
                ToolResult(
                    success=False, output="",
                    error=f"命令执行超时（{timeout_sec:.1f}秒）"
                )
            )

    except Exception as e:
        return _finalize(
            ctx, "bash", {"command": command},
            ToolResult(success=False, output="", error=str(e))
        )


async def bash_output(
    ctx: RunContext[MiniCCDeps],
    bash_id: str,
    filter_pattern: str | None = None,
) -> ToolResult:
    """
    获取后台命令的输出

    Args:
        bash_id: 后台命令的 ID
        filter_pattern: 可选的正则过滤模式

    Returns:
        命令输出（新增部分）
    """
    shell_data = ctx.deps.background_shells.get(bash_id)

    if not shell_data:
        return _finalize(
            ctx, "bash_output", {"bash_id": bash_id},
            ToolResult(success=False, output="", error=f"未找到后台任务: {bash_id}")
        )

    process, shell_info = shell_data

    # 检查进程状态
    if process.returncode is not None:
        shell_info.is_running = False

    output = shell_info.output_buffer

    # 应用过滤
    if filter_pattern and output:
        try:
            regex = re.compile(filter_pattern)
            lines = output.split("\n")
            output = "\n".join(line for line in lines if regex.search(line))
        except re.error:
            pass  # 忽略无效正则

    status = "运行中" if shell_info.is_running else "已完成"

    return _finalize(
        ctx, "bash_output", {"bash_id": bash_id},
        ToolResult(success=True, output=f"[{status}]\n{output}")
    )


async def kill_shell(
    ctx: RunContext[MiniCCDeps],
    shell_id: str,
) -> ToolResult:
    """
    终止后台命令

    Args:
        shell_id: 要终止的后台命令 ID

    Returns:
        终止结果
    """
    shell_data = ctx.deps.background_shells.get(shell_id)

    if not shell_data:
        return _finalize(
            ctx, "kill_shell", {"shell_id": shell_id},
            ToolResult(success=False, output="", error=f"未找到后台任务: {shell_id}")
        )

    process, shell_info = shell_data

    if shell_info.is_running:
        try:
            process.kill()
            await process.wait()
            shell_info.is_running = False
        except Exception as e:
            return _finalize(
                ctx, "kill_shell", {"shell_id": shell_id},
                ToolResult(success=False, output="", error=str(e))
            )

    # 清理
    del ctx.deps.background_shells[shell_id]

    return _finalize(
        ctx, "kill_shell", {"shell_id": shell_id},
        ToolResult(success=True, output=f"已终止后台任务: {shell_id}")
    )


# ============ 任务管理工具 ============


async def task(
    ctx: RunContext[MiniCCDeps],
    prompt: str,
    description: str,
    subagent_type: str = "general-purpose",
) -> ToolResult:
    """
    启动子代理执行任务

    子代理会独立运行，可以并行处理多个任务。

    Args:
        prompt: 详细的任务描述/提示词
        description: 3-5 词简短描述
        subagent_type: 代理类型（预留扩展）

    Returns:
        任务 ID 和状态
    """
    task_id = uuid4().hex[:8]

    task_obj = AgentTask(
        task_id=task_id,
        description=description,
        prompt=prompt,
        subagent_type=subagent_type,
        status="pending",
    )

    ctx.deps.sub_agents[task_id] = task_obj

    # 异步启动子任务
    task_handle = asyncio.create_task(_run_sub_agent(ctx.deps, task_obj))
    ctx.deps.sub_agent_tasks[task_id] = task_handle

    return _finalize(
        ctx, "task", {"description": description, "subagent_type": subagent_type},
        ToolResult(
            success=True,
            output=f"已创建子任务 [{task_id}]: {description}"
        )
    )


async def todo_write(
    ctx: RunContext[MiniCCDeps],
    todos: list[dict[str, str]],
) -> ToolResult:
    """
    更新任务列表

    用于追踪当前会话的任务进度。

    Args:
        todos: 任务列表，每项包含:
            - content: 任务描述（祈使句，如 "Run tests"）
            - status: 状态（pending/in_progress/completed）
            - activeForm: 进行时描述（如 "Running tests"）

    Returns:
        更新确认
    """
    try:
        # 转换为 TodoItem 对象
        new_todos = []
        for item in todos:
            todo = TodoItem(
                content=item.get("content", ""),
                status=item.get("status", "pending"),
                active_form=item.get("activeForm", item.get("active_form", "")),
            )
            new_todos.append(todo)

        ctx.deps.todos = new_todos

        # 触发回调
        if ctx.deps.on_todo_update:
            ctx.deps.on_todo_update(new_todos)

        # 格式化输出
        summary_lines = []
        for todo in new_todos:
            status_icon = {"pending": "⏳", "in_progress": "🔄", "completed": "✅"}.get(
                todo.status, "?"
            )
            summary_lines.append(f"{status_icon} {todo.content}")

        return _finalize(
            ctx, "todo_write", {"count": len(todos)},
            ToolResult(
                success=True,
                output=f"已更新 {len(new_todos)} 个任务\n" + "\n".join(summary_lines)
            )
        )

    except Exception as e:
        return _finalize(
            ctx, "todo_write", {},
            ToolResult(success=False, output="", error=str(e))
        )


# ============ 辅助函数 ============


def _finalize(
    ctx: RunContext[MiniCCDeps],
    tool_name: str,
    args: dict[str, Any],
    result: ToolResult,
) -> ToolResult:
    """触发工具调用回调（用于 UI 更新）"""
    callback = getattr(ctx.deps, "on_tool_call", None)
    if callback:
        try:
            callback(tool_name, args, result)
        except Exception:
            pass
    return result


def _resolve_path(cwd: str, path: str) -> Path:
    """解析路径，支持相对路径和绝对路径"""
    p = Path(path)
    if p.is_absolute():
        return p
    return Path(cwd) / p


def _normalize_whitespace(text: str) -> str:
    """标准化空白字符（用于容错匹配）"""
    # 将 tabs 转为 4 空格
    text = text.replace("\t", "    ")
    # 移除行尾空白
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines)


def _find_whitespace_tolerant(content: str, normalized_pattern: str) -> str | None:
    """在内容中查找空白容错的匹配"""
    # 简单实现：逐行比较
    content_lines = content.split("\n")
    pattern_lines = normalized_pattern.split("\n")
    pattern_len = len(pattern_lines)

    for i in range(len(content_lines) - pattern_len + 1):
        window = content_lines[i:i + pattern_len]
        normalized_window = [_normalize_whitespace(line) for line in window]

        if "\n".join(normalized_window) == normalized_pattern:
            # 返回原始内容
            return "\n".join(window)

    return None


def _generate_unified_diff(old: str, new: str, filename: str = "") -> str:
    """生成 unified diff 格式输出"""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    diff = difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filename}" if filename else "a",
        tofile=f"b/{filename}" if filename else "b",
    )

    return "".join(diff)


def generate_diff(old: str, new: str) -> list[DiffLine]:
    """生成 DiffLine 列表（兼容旧接口）"""
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    diff = difflib.unified_diff(old_lines, new_lines, lineterm="")
    result = []

    for line in diff:
        if line.startswith("+++") or line.startswith("---") or line.startswith("@@"):
            continue
        elif line.startswith("+"):
            result.append(DiffLine(type="add", content=line[1:].rstrip("\n")))
        elif line.startswith("-"):
            result.append(DiffLine(type="remove", content=line[1:].rstrip("\n")))
        else:
            result.append(DiffLine(type="context", content=line.rstrip("\n")))

    return result


def format_diff(diff_lines: list[DiffLine]) -> str:
    """格式化 DiffLine 列表为字符串"""
    lines = []
    for line in diff_lines:
        if line.type == "add":
            lines.append(f"+ {line.content}")
        elif line.type == "remove":
            lines.append(f"- {line.content}")
        else:
            lines.append(f"  {line.content}")
    return "\n".join(lines)


async def _bash_background(
    ctx: RunContext[MiniCCDeps],
    command: str,
    description: str,
) -> ToolResult:
    """在后台启动命令"""
    shell_id = uuid4().hex[:8]

    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=ctx.deps.cwd,
    )

    shell_info = BackgroundShell(
        shell_id=shell_id,
        command=command,
        description=description,
        is_running=True,
    )

    ctx.deps.background_shells[shell_id] = (process, shell_info)

    # 启动输出收集任务
    asyncio.create_task(_collect_shell_output(process, shell_info))

    return _finalize(
        ctx, "bash", {"command": command, "run_in_background": True},
        ToolResult(
            success=True,
            output=f"已在后台启动命令 [ID: {shell_id}]: {description}"
        )
    )


async def _collect_shell_output(process: asyncio.subprocess.Process, shell_info: BackgroundShell):
    """收集后台进程输出"""
    try:
        while True:
            if process.stdout is None:
                break
            line = await process.stdout.readline()
            if not line:
                break
            shell_info.output_buffer += line.decode("utf-8", errors="replace")
    except Exception:
        pass
    finally:
        shell_info.is_running = False


async def _run_sub_agent(deps: MiniCCDeps, task_obj: AgentTask) -> None:
    """运行子代理任务"""
    from .agent import create_agent

    task_obj.status = "running"

    try:
        sub_agent = create_agent(deps.config)
        result = await sub_agent.run(task_obj.prompt, deps=deps)
        task_obj.status = "completed"
        task_obj.result = getattr(result, "output", str(result))
    except Exception as e:
        task_obj.status = "failed"
        task_obj.result = str(e)
    finally:
        deps.sub_agent_tasks.pop(task_obj.task_id, None)


# ============ Ripgrepy 扩展功能 ============


async def _grep_ripgrepy(
    ctx: RunContext[MiniCCDeps],
    pattern: str,
    path: str | None,
    glob: str | None,
    output_mode: str,
    context_before: int | None,
    context_after: int | None,
    context: int | None,
    case_insensitive: bool,
    head_limit: int | None,
    file_type: str | None,
) -> ToolResult:
    """使用 ripgrepy 的 grep 实现（支持上下文行等高级功能）"""
    try:
        from ripgrepy import Ripgrepy

        search_path = str(_resolve_path(ctx.deps.cwd, path or "."))
        rg = Ripgrepy(pattern, search_path)

        if case_insensitive:
            rg = rg.i()

        if glob:
            rg = rg.glob(glob)

        if file_type:
            rg = rg.type(file_type)

        if context:
            rg = rg.context(context)
        else:
            if context_before:
                rg = rg.before_context(context_before)
            if context_after:
                rg = rg.after_context(context_after)

        if output_mode == "files_with_matches":
            rg = rg.files_with_matches()
        elif output_mode == "count":
            rg = rg.count()
        else:
            rg = rg.with_filename().line_number()

        try:
            result = rg.run()
            output = result.as_string if hasattr(result, 'as_string') else str(result)
        except Exception:
            output = ""

        if not output.strip():
            return _finalize(
                ctx, "grep_search", {"pattern": pattern, "path": path},
                ToolResult(success=True, output=f"未找到匹配 '{pattern}' 的内容")
            )

        lines = output.strip().split("\n")

        if head_limit and len(lines) > head_limit:
            lines = lines[:head_limit]
            output = "\n".join(lines) + f"\n... 还有更多结果"
        else:
            output = "\n".join(lines)

        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n... 输出已截断"

        return _finalize(
            ctx, "grep_search", {"pattern": pattern, "path": path, "output_mode": output_mode},
            ToolResult(success=True, output=output)
        )

    except ImportError:
        return _finalize(
            ctx, "grep_search", {"pattern": pattern, "path": path},
            ToolResult(success=False, output="", error="ripgrepy 未安装，无法使用上下文行功能")
        )
    except Exception as e:
        return _finalize(
            ctx, "grep_search", {"pattern": pattern, "path": path},
            ToolResult(success=False, output="", error=str(e))
        )