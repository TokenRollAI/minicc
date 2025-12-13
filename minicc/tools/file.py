from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic_ai import RunContext

from minicc.core.models import MiniCCDeps, ToolResult
from minicc.tools.common import (
    DEFAULT_READ_LIMIT,
    find_whitespace_tolerant,
    generate_unified_diff,
    normalize_whitespace,
    resolve_path,
)


async def read_file(
    ctx: RunContext[MiniCCDeps],
    file_path: str,
    offset: int | None = None,
    limit: int | None = None,
) -> ToolResult:
    fs = ctx.deps.fs
    resolved = resolve_path(ctx.deps.cwd, file_path)

    try:
        if not resolved.exists():
            return ToolResult(success=False, output="", error=f"文件不存在: {file_path}")
        if resolved.is_dir():
            return ToolResult(success=False, output="", error=f"不是文件: {file_path}")

        start_line = (offset or 1) - 1
        count = limit or DEFAULT_READ_LIMIT

        if fs is not None:
            rel_path = (
                str(resolved.relative_to(ctx.deps.cwd))
                if resolved.is_absolute()
                else file_path
            )
            lines = fs.read_lines(rel_path, start_line=start_line, count=count)
        else:
            text = resolved.read_text(encoding="utf-8")
            all_lines = text.splitlines()
            lines = all_lines[start_line : start_line + count]

        if not lines:
            return ToolResult(success=True, output="（文件为空或偏移超出范围）")

        formatted: list[str] = []
        for i, line in enumerate(lines, start=start_line + 1):
            if len(line) > 2000:
                line = line[:2000] + "..."
            formatted.append(f"{i:6}\t{line}")

        output = "\n".join(formatted)
        if len(lines) >= count:
            output += "\n\n... 可能还有更多行未显示"
        return ToolResult(success=True, output=output)

    except UnicodeDecodeError:
        return ToolResult(success=False, output="", error="无法读取文件：可能是二进制文件")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def write_file(
    ctx: RunContext[MiniCCDeps],
    file_path: str,
    content: str,
) -> ToolResult:
    fs = ctx.deps.fs
    resolved = resolve_path(ctx.deps.cwd, file_path)

    try:
        resolved.parent.mkdir(parents=True, exist_ok=True)

        if fs is not None:
            rel_path = (
                str(resolved.relative_to(ctx.deps.cwd))
                if resolved.is_absolute()
                else file_path
            )
            ok = fs.write_file(rel_path, content)
            if not ok:
                return ToolResult(success=False, output="", error="写入失败")
        else:
            resolved.write_text(content, encoding="utf-8")

        return ToolResult(success=True, output=f"已写入文件: {file_path} ({len(content)} 字符)")
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def edit_file(
    ctx: RunContext[MiniCCDeps],
    file_path: str,
    old_string: str,
    new_string: str,
    replace_all: bool = False,
) -> ToolResult:
    fs = ctx.deps.fs
    resolved = resolve_path(ctx.deps.cwd, file_path)

    try:
        if not resolved.exists():
            return ToolResult(success=False, output="", error=f"文件不存在: {file_path}")
        if resolved.is_dir():
            return ToolResult(success=False, output="", error=f"不是文件: {file_path}")
        if old_string == new_string:
            return ToolResult(success=False, output="", error="new_string 必须与 old_string 不同")

        if fs is not None:
            rel_path = (
                str(resolved.relative_to(ctx.deps.cwd))
                if resolved.is_absolute()
                else file_path
            )
            current = fs.read_file(rel_path)
        else:
            current = resolved.read_text(encoding="utf-8")

        exact_count = current.count(old_string)
        actual_old = old_string

        if exact_count == 0:
            normalized_old = normalize_whitespace(old_string)
            match = find_whitespace_tolerant(current, normalized_old)
            if match is None:
                return ToolResult(
                    success=False,
                    output="",
                    error="未找到要替换的内容，请确保 old_string 精确匹配文件内容",
                )
            actual_old = match
            exact_count = 1

        if exact_count > 1 and not replace_all:
            return ToolResult(
                success=False,
                output="",
                error=f"old_string 在文件中出现了 {exact_count} 次，请设置 replace_all=True 或提供更精确的 old_string",
            )

        if replace_all:
            updated = current.replace(actual_old, new_string)
        else:
            updated = current.replace(actual_old, new_string, 1)

        if fs is not None:
            rel_path = (
                str(resolved.relative_to(ctx.deps.cwd))
                if resolved.is_absolute()
                else file_path
            )
            ok = fs.write_file(rel_path, updated)
            if not ok:
                return ToolResult(success=False, output="", error="写入失败")
        else:
            resolved.write_text(updated, encoding="utf-8")

        diff = generate_unified_diff(current, updated, filename=str(resolved))
        return ToolResult(success=True, output=diff or "OK")

    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))

