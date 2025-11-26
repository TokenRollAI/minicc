"""
MiniCC 工具函数实现

定义所有可供 Agent 调用的工具，使用 pydantic-ai 的工具注册模式。
每个工具函数的 docstring 会被自动提取作为 LLM 的工具描述。
"""

import asyncio
import difflib
import re
from typing import Any
from pathlib import Path
from uuid import uuid4

from pydantic_ai import RunContext

from .schemas import AgentTask, DiffLine, MiniCCDeps, ToolResult


# ============ 文件操作工具 ============


async def read_file(ctx: RunContext[MiniCCDeps], path: str) -> ToolResult:
    """
    读取指定路径的文件内容

    Args:
        path: 文件的绝对或相对路径（相对于当前工作目录）

    Returns:
        文件内容，若文件不存在则返回错误
    """
    try:
        file_path = _resolve_path(ctx.deps.cwd, path)

        if not file_path.exists():
            return _finalize_tool_call(
                ctx,
                read_file.__name__,
                {"path": path},
                ToolResult(
                    success=False,
                    output="",
                    error=f"文件不存在: {path}"
                )
            )

        if not file_path.is_file():
            return _finalize_tool_call(
                ctx,
                read_file.__name__,
                {"path": path},
                ToolResult(
                    success=False,
                    output="",
                    error=f"路径不是文件: {path}"
                )
            )

        content = file_path.read_text(encoding="utf-8")
        return _finalize_tool_call(
            ctx,
            read_file.__name__,
            {"path": path},
            ToolResult(success=True, output=content)
        )

    except Exception as e:
        return _finalize_tool_call(
            ctx,
            read_file.__name__,
            {"path": path},
            ToolResult(success=False, output="", error=str(e))
        )


async def write_file(
    ctx: RunContext[MiniCCDeps],
    path: str,
    content: str
) -> ToolResult:
    """
    创建或覆盖写入文件

    会自动创建不存在的父目录。

    Args:
        path: 目标文件路径
        content: 要写入的完整内容

    Returns:
        写入成功/失败信息
    """
    try:
        file_path = _resolve_path(ctx.deps.cwd, path)

        # 创建父目录
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_text(content, encoding="utf-8")
        return _finalize_tool_call(
            ctx,
            write_file.__name__,
            {"path": path, "content": content},
            ToolResult(
                success=True,
                output=f"已写入文件: {path} ({len(content)} 字符)"
            )
        )

    except Exception as e:
        return _finalize_tool_call(
            ctx,
            write_file.__name__,
            {"path": path, "content": content},
            ToolResult(success=False, output="", error=str(e))
        )


async def update_file(
    ctx: RunContext[MiniCCDeps],
    path: str,
    old_content: str,
    new_content: str
) -> ToolResult:
    """
    更新文件中的指定内容（精确字符串替换）

    在文件中查找 old_content 并替换为 new_content。
    要求 old_content 在文件中唯一存在。

    Args:
        path: 文件路径
        old_content: 要被替换的原内容（必须精确匹配）
        new_content: 替换后的新内容

    Returns:
        更新结果和 diff 预览
    """
    try:
        file_path = _resolve_path(ctx.deps.cwd, path)

        if not file_path.exists():
            return _finalize_tool_call(
                ctx,
                update_file.__name__,
                {"path": path, "old_content": old_content, "new_content": new_content},
                ToolResult(
                    success=False,
                    output="",
                    error=f"文件不存在: {path}"
                )
            )

        current_content = file_path.read_text(encoding="utf-8")

        # 检查 old_content 出现次数
        count = current_content.count(old_content)
        if count == 0:
            return _finalize_tool_call(
                ctx,
                update_file.__name__,
                {"path": path, "old_content": old_content, "new_content": new_content},
                ToolResult(
                    success=False,
                    output="",
                    error="未找到要替换的内容，请确保 old_content 精确匹配"
                )
            )
        if count > 1:
            return _finalize_tool_call(
                ctx,
                update_file.__name__,
                {"path": path, "old_content": old_content, "new_content": new_content},
                ToolResult(
                    success=False,
                    output="",
                    error=f"old_content 在文件中出现了 {count} 次，请提供更精确的内容以确保唯一性"
                )
            )

        # 执行替换
        new_file_content = current_content.replace(old_content, new_content, 1)
        file_path.write_text(new_file_content, encoding="utf-8")

        # 生成 diff
        diff_lines = generate_diff(old_content, new_content)
        diff_output = format_diff(diff_lines)

        return _finalize_tool_call(
            ctx,
            update_file.__name__,
            {"path": path, "old_content": old_content, "new_content": new_content},
            ToolResult(
                success=True,
                output=f"已更新文件: {path}\n\n{diff_output}"
            )
        )

    except Exception as e:
        return _finalize_tool_call(
            ctx,
            update_file.__name__,
            {"path": path, "old_content": old_content, "new_content": new_content},
            ToolResult(success=False, output="", error=str(e))
        )


# ============ 搜索工具 ============


async def search_files(
    ctx: RunContext[MiniCCDeps],
    pattern: str,
    path: str = "."
) -> ToolResult:
    """
    使用 glob 模式搜索文件

    支持 ** 递归匹配，如 "**/*.py" 匹配所有 Python 文件。

    Args:
        pattern: glob 模式，如 "**/*.py", "src/*.js"
        path: 搜索起始路径（默认为当前目录）

    Returns:
        匹配的文件列表（每行一个路径）
    """
    try:
        search_path = _resolve_path(ctx.deps.cwd, path)

        if not search_path.exists():
            return _finalize_tool_call(
                ctx,
                search_files.__name__,
                {"pattern": pattern, "path": path},
                ToolResult(
                    success=False,
                    output="",
                    error=f"路径不存在: {path}"
                )
            )

        matches = list(search_path.glob(pattern))

        if not matches:
            return _finalize_tool_call(
                ctx,
                search_files.__name__,
                {"pattern": pattern, "path": path},
                ToolResult(
                    success=True,
                    output=f"未找到匹配 '{pattern}' 的文件"
                )
            )

        # 转换为相对路径
        relative_paths = [
            str(m.relative_to(ctx.deps.cwd))
            for m in matches
            if m.is_file()
        ]

        return _finalize_tool_call(
            ctx,
            search_files.__name__,
            {"pattern": pattern, "path": path},
            ToolResult(
                success=True,
                output="\n".join(sorted(relative_paths))
            )
        )

    except Exception as e:
        return _finalize_tool_call(
            ctx,
            search_files.__name__,
            {"pattern": pattern, "path": path},
            ToolResult(success=False, output="", error=str(e))
        )


async def grep(
    ctx: RunContext[MiniCCDeps],
    pattern: str,
    path: str = ".",
    include: str = "*"
) -> ToolResult:
    """
    在文件内容中搜索正则表达式

    Args:
        pattern: 正则表达式模式
        path: 搜索路径（文件或目录）
        include: 文件过滤 glob 模式，如 "*.py"

    Returns:
        匹配结果，格式: 文件:行号:匹配内容
    """
    try:
        search_path = _resolve_path(ctx.deps.cwd, path)
        regex = re.compile(pattern)
        results = []

        if search_path.is_file():
            files = [search_path]
        else:
            files = list(search_path.glob(f"**/{include}"))

        for file_path in files:
            if not file_path.is_file():
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                for line_no, line in enumerate(content.splitlines(), 1):
                    if regex.search(line):
                        rel_path = file_path.relative_to(ctx.deps.cwd)
                        results.append(f"{rel_path}:{line_no}:{line.strip()}")
            except (UnicodeDecodeError, PermissionError):
                continue  # 跳过二进制文件和无权限文件

        if not results:
            return _finalize_tool_call(
                ctx,
                grep.__name__,
                {"pattern": pattern, "path": path, "include": include},
                ToolResult(
                    success=True,
                    output=f"未找到匹配 '{pattern}' 的内容"
                )
            )

        # 限制结果数量
        max_results = 100
        output = "\n".join(results[:max_results])
        if len(results) > max_results:
            output += f"\n... 还有 {len(results) - max_results} 个匹配项"

        return _finalize_tool_call(
            ctx,
            grep.__name__,
            {"pattern": pattern, "path": path, "include": include},
            ToolResult(success=True, output=output)
        )

    except re.error as e:
        return _finalize_tool_call(
            ctx,
            grep.__name__,
            {"pattern": pattern, "path": path, "include": include},
            ToolResult(
                success=False,
                output="",
                error=f"无效的正则表达式: {e}"
            )
        )
    except Exception as e:
        return _finalize_tool_call(
            ctx,
            grep.__name__,
            {"pattern": pattern, "path": path, "include": include},
            ToolResult(success=False, output="", error=str(e))
        )


# ============ 命令行工具 ============


async def bash(
    ctx: RunContext[MiniCCDeps],
    command: str,
    timeout: int = 30
) -> ToolResult:
    """
    执行 bash 命令

    在当前工作目录下执行 shell 命令。

    Args:
        command: 要执行的命令
        timeout: 超时秒数（默认 30 秒）

    Returns:
        命令输出（stdout + stderr 合并）
    """
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=ctx.deps.cwd
        )

        try:
            stdout, _ = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout
            )
            output = stdout.decode("utf-8", errors="replace")

            if process.returncode == 0:
                return _finalize_tool_call(
                    ctx,
                    bash.__name__,
                    {"command": command, "timeout": timeout},
                    ToolResult(success=True, output=output)
                )
            else:
                return _finalize_tool_call(
                    ctx,
                    bash.__name__,
                    {"command": command, "timeout": timeout},
                    ToolResult(
                        success=False,
                        output=output,
                        error=f"命令退出码: {process.returncode}"
                    )
                )

        except asyncio.TimeoutError:
            process.kill()
            return _finalize_tool_call(
                ctx,
                bash.__name__,
                {"command": command, "timeout": timeout},
                ToolResult(
                    success=False,
                    output="",
                    error=f"命令执行超时（{timeout}秒）"
                )
            )

    except Exception as e:
        return _finalize_tool_call(
            ctx,
            bash.__name__,
            {"command": command, "timeout": timeout},
            ToolResult(success=False, output="", error=str(e))
        )


# ============ SubAgent 工具 ============


async def spawn_agent(
    ctx: RunContext[MiniCCDeps],
    task: str,
    context: str = ""
) -> ToolResult:
    """
    创建一个子 Agent 执行特定任务

    子 Agent 会独立运行，可以并行处理多个任务。
    使用 get_agent_result 获取任务结果。

    Args:
        task: 任务描述
        context: 可选的额外上下文信息

    Returns:
        任务 ID，可用于后续查询结果
    """
    task_id = uuid4().hex[:8]

    prompt = task
    if context:
        prompt = f"{context}\n\n任务: {task}"

    task_obj = AgentTask(
        task_id=task_id,
        prompt=prompt,
        status="pending"
    )

    ctx.deps.sub_agents[task_id] = task_obj

    # 异步启动子任务（不阻塞当前执行）
    task_handle = asyncio.create_task(_run_sub_agent(ctx.deps, task_obj))
    ctx.deps.sub_agent_tasks[task_id] = task_handle

    return _finalize_tool_call(
        ctx,
        spawn_agent.__name__,
        {"task": task, "context": context},
        ToolResult(
            success=True,
            output=f"已创建子任务 [{task_id}]: {task[:50]}..."
        )
        )


async def get_agent_result(
    ctx: RunContext[MiniCCDeps],
    task_id: str
) -> ToolResult:
    """
    获取子 Agent 任务的结果

    Args:
        task_id: spawn_agent 返回的任务 ID

    Returns:
        任务状态和结果
    """
    task_obj = ctx.deps.sub_agents.get(task_id)

    if not task_obj:
        return _finalize_tool_call(
            ctx,
            get_agent_result.__name__,
            {"task_id": task_id},
            ToolResult(
                success=False,
                output="",
                error=f"未找到任务: {task_id}"
            )
        )

    if task_obj.status == "pending":
        return _finalize_tool_call(
            ctx,
            get_agent_result.__name__,
            {"task_id": task_id},
            ToolResult(
                success=True,
                output=f"任务 [{task_id}] 等待中..."
            )
        )
    elif task_obj.status == "running":
        return _finalize_tool_call(
            ctx,
            get_agent_result.__name__,
            {"task_id": task_id},
            ToolResult(
                success=True,
                output=f"任务 [{task_id}] 运行中..."
            )
        )
    elif task_obj.status == "completed":
        return _finalize_tool_call(
            ctx,
            get_agent_result.__name__,
            {"task_id": task_id},
            ToolResult(
                success=True,
                output=f"任务 [{task_id}] 已完成:\n{task_obj.result}"
            )
        )
    else:  # failed
        return _finalize_tool_call(
            ctx,
            get_agent_result.__name__,
            {"task_id": task_id},
            ToolResult(
                success=False,
                output="",
                error=f"任务 [{task_id}] 失败: {task_obj.result}"
            )
        )


async def wait_sub_agents(
    ctx: RunContext[MiniCCDeps],
    task_ids: list[str] | None = None,
    timeout: int = 300
) -> ToolResult:
    """
    等待一个或多个子 Agent 完成

    若 task_ids 为空，则等待所有仍在运行的子任务，直到全部完成或超时。

    Args:
        task_ids: 要等待的任务 ID 列表，为空则等待全部
        timeout: 最长等待秒数（默认 300 秒）

    Returns:
        等待结果汇总，全部完成则 success=True；超时仍未完成则 success=False
    """
    selected_ids = task_ids or list(ctx.deps.sub_agent_tasks.keys())

    # 处理不存在的任务
    missing = [tid for tid in selected_ids if tid not in ctx.deps.sub_agents]
    if missing:
        return _finalize_tool_call(
            ctx,
            wait_sub_agents.__name__,
            {"task_ids": task_ids, "timeout": timeout},
            ToolResult(
                success=False,
                output="",
                error=f"未找到任务: {', '.join(missing)}"
            )
        )

    # 如果没有需要等待的任务
    active_ids = [tid for tid in selected_ids if tid in ctx.deps.sub_agent_tasks]
    if not active_ids:
        summary = _format_sub_agent_summary(ctx, selected_ids)
        return _finalize_tool_call(
            ctx,
            wait_sub_agents.__name__,
            {"task_ids": task_ids, "timeout": timeout},
            ToolResult(
                success=True,
                output=f"没有正在运行的子任务。\n{summary}".strip()
            )
        )

    # 阻塞等待所选任务完成或超时
    handle_map = {tid: ctx.deps.sub_agent_tasks[tid] for tid in active_ids}
    pending_ids = set(active_ids)
    deadline = asyncio.get_event_loop().time() + timeout

    while pending_ids:
        remaining = deadline - asyncio.get_event_loop().time()
        if remaining <= 0:
            break

        wait_set = {handle_map[tid] for tid in pending_ids}
        done, pending = await asyncio.wait(wait_set, timeout=remaining)

        # 标记完成的任务
        for tid, handle in handle_map.items():
            if handle in done:
                pending_ids.discard(tid)

        # 如果都完成提前退出
        if not pending_ids:
            break

    success = not pending_ids
    summary = _format_sub_agent_summary(ctx, selected_ids)
    status_line = (
        "所有子任务已完成。"
        if success
        else f"{len(pending_ids)} 个子任务未完成，已等待 {timeout} 秒。"
    )

    return _finalize_tool_call(
        ctx,
        wait_sub_agents.__name__,
        {"task_ids": task_ids, "timeout": timeout},
        ToolResult(
            success=success,
            output=f"{status_line}\n{summary}".strip(),
            error=None if success else status_line
        )
    )


# ============ 辅助函数 ============


def _finalize_tool_call(
    ctx: RunContext[MiniCCDeps],
    tool_name: str,
    args: dict[str, Any],
    result: ToolResult
) -> ToolResult:
    """Trigger on_tool_call callback for UI updates without breaking tool execution."""
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


def generate_diff(old: str, new: str) -> list[DiffLine]:
    """
    生成简单的文本 diff

    Args:
        old: 原内容
        new: 新内容

    Returns:
        DiffLine 列表
    """
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)

    diff = difflib.unified_diff(old_lines, new_lines, lineterm="")
    result = []

    for line in diff:
        if line.startswith("+++") or line.startswith("---"):
            continue
        elif line.startswith("@@"):
            continue
        elif line.startswith("+"):
            result.append(DiffLine(type="add", content=line[1:].rstrip("\n")))
        elif line.startswith("-"):
            result.append(DiffLine(type="remove", content=line[1:].rstrip("\n")))
        else:
            result.append(DiffLine(type="context", content=line.rstrip("\n")))

    return result


def format_diff(diff_lines: list[DiffLine]) -> str:
    """格式化 diff 输出为字符串"""
    lines = []
    for line in diff_lines:
        if line.type == "add":
            lines.append(f"+ {line.content}")
        elif line.type == "remove":
            lines.append(f"- {line.content}")
        else:
            lines.append(f"  {line.content}")
    return "\n".join(lines)


async def _run_sub_agent(deps: MiniCCDeps, task: AgentTask) -> None:
    """
    运行子 Agent 任务

    此函数由 spawn_agent 异步调用，不阻塞主 Agent 执行。
    """
    # 避免循环导入
    from .agent import create_agent

    task.status = "running"

    try:
        sub_agent = create_agent(deps.config)
        result = await sub_agent.run(task.prompt, deps=deps)
        task.status = "completed"
        # pydantic-ai >=1.0 使用 output 字段
        task.result = getattr(result, "output", None)
    except Exception as e:
        task.status = "failed"
        task.result = str(e)
    finally:
        deps.sub_agent_tasks.pop(task.task_id, None)


def _format_sub_agent_summary(ctx: RunContext[MiniCCDeps], task_ids: list[str]) -> str:
    """格式化子任务状态摘要"""
    lines = []
    for tid in task_ids:
        task = ctx.deps.sub_agents.get(tid)
        if not task:
            lines.append(f"[{tid}] 未找到")
            continue
        result_preview = ""
        if task.result:
            trimmed = task.result
            if len(trimmed) > 200:
                trimmed = trimmed[:200] + "..."
            result_preview = f" | result: {trimmed}"
        lines.append(f"[{tid}] {task.status}{result_preview}")
    return "\n".join(lines)
