from __future__ import annotations

import asyncio
import os
import re
import signal
from uuid import uuid4

from pydantic_ai import RunContext

from minicc.core.models import BackgroundShell, MiniCCDeps, ToolResult
from minicc.tools.common import DEFAULT_BASH_TIMEOUT_MS, MAX_OUTPUT_CHARS


async def bash(
    ctx: RunContext[MiniCCDeps],
    command: str,
    timeout: int = DEFAULT_BASH_TIMEOUT_MS,
    description: str | None = None,
    run_in_background: bool = False,
) -> ToolResult:
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
            preexec_fn=os.setsid if os.name == "posix" else None,
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_sec)
        except asyncio.TimeoutError:
            _kill_process_tree(process)
            return ToolResult(success=False, output="", error=f"命令执行超时（{timeout_sec:.1f}秒）")

        stdout_str = (stdout or b"").decode("utf-8", errors="replace")
        stderr_str = (stderr or b"").decode("utf-8", errors="replace")
        output = stdout_str
        if stderr_str:
            output = f"{output}\n[stderr]\n{stderr_str}" if output else stderr_str

        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n... 输出已截断"

        success = process.returncode == 0
        error = None if success else f"退出码: {process.returncode}"
        return ToolResult(success=success, output=output, error=error)

    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def bash_output(
    ctx: RunContext[MiniCCDeps],
    bash_id: str,
    filter_pattern: str | None = None,
) -> ToolResult:
    shell_data = ctx.deps.background_shells.get(bash_id)
    if not shell_data:
        return ToolResult(success=False, output="", error=f"未找到后台任务: {bash_id}")

    process, shell_info = shell_data
    if process.returncode is not None:
        shell_info.is_running = False

    output = shell_info.output_buffer
    if filter_pattern and output:
        try:
            regex = re.compile(filter_pattern)
            output = "\n".join(line for line in output.split("\n") if regex.search(line))
        except re.error:
            pass

    status = "运行中" if shell_info.is_running else "已完成"
    return ToolResult(success=True, output=f"[{status}]\n{output}")


async def kill_shell(ctx: RunContext[MiniCCDeps], shell_id: str) -> ToolResult:
    shell_data = ctx.deps.background_shells.get(shell_id)
    if not shell_data:
        return ToolResult(success=False, output="", error=f"未找到后台任务: {shell_id}")

    process, shell_info = shell_data
    if shell_info.is_running:
        try:
            _kill_process_tree(process)
            shell_info.is_running = False
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    del ctx.deps.background_shells[shell_id]
    return ToolResult(success=True, output=f"已终止后台任务: {shell_id}")


def _kill_process_tree(process: asyncio.subprocess.Process) -> None:
    if os.name == "posix" and process.pid:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    else:
        process.kill()


async def _bash_background(ctx: RunContext[MiniCCDeps], command: str, description: str) -> ToolResult:
    shell_id = uuid4().hex[:8]

    process = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=ctx.deps.cwd,
        preexec_fn=os.setsid if os.name == "posix" else None,
    )

    shell_info = BackgroundShell(shell_id=shell_id, command=command, description=description, is_running=True)
    ctx.deps.background_shells[shell_id] = (process, shell_info)

    asyncio.create_task(_collect_shell_output(process, shell_info))
    return ToolResult(success=True, output=f"已在后台启动命令 [ID: {shell_id}]: {description}")


async def _collect_shell_output(process: asyncio.subprocess.Process, shell_info: BackgroundShell) -> None:
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

