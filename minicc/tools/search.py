from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

from pydantic_ai import RunContext

from minicc.core.models import MiniCCDeps, ToolResult
from minicc.tools.common import MAX_OUTPUT_CHARS, resolve_path


async def glob_files(
    ctx: RunContext[MiniCCDeps],
    pattern: str,
    path: str | None = None,
) -> ToolResult:
    base = resolve_path(ctx.deps.cwd, path or ".")
    if not base.exists():
        return ToolResult(success=False, output="", error=f"路径不存在: {path or '.'}")

    fs = ctx.deps.fs
    try:
        if fs is not None:
            full_pattern = f"{path}/{pattern}" if path else pattern
            matches = fs.glob(full_pattern)
            if not matches:
                return ToolResult(success=True, output=f"未找到匹配 '{pattern}' 的文件")
            return ToolResult(success=True, output="\n".join(matches))

        from wcmatch import glob as wcglob

        flags = wcglob.GLOBSTAR | wcglob.BRACE | wcglob.EXTGLOB
        matches = wcglob.glob(pattern, root_dir=str(base), flags=flags)
        if not matches:
            return ToolResult(success=True, output=f"未找到匹配 '{pattern}' 的文件")
        rels = [os.path.relpath(m, start=str(base)) for m in matches]
        return ToolResult(success=True, output="\n".join(rels))
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


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
    search_path = resolve_path(ctx.deps.cwd, path or ".")
    if not search_path.exists():
        return ToolResult(success=False, output="", error=f"路径不存在: {path or '.'}")

    try:
        from ripgrepy import Ripgrepy

        rg = Ripgrepy(pattern, str(search_path))
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

        result = rg.run()
        output = result.as_string if hasattr(result, "as_string") else str(result)
        if not output.strip():
            return ToolResult(success=True, output=f"未找到匹配 '{pattern}' 的内容")

        lines = output.strip().split("\n")
        if head_limit and len(lines) > head_limit:
            lines = lines[:head_limit]
            output = "\n".join(lines) + "\n... 还有更多结果"
        else:
            output = "\n".join(lines)

        if len(output) > MAX_OUTPUT_CHARS:
            output = output[:MAX_OUTPUT_CHARS] + "\n... 输出已截断"
        return ToolResult(success=True, output=output)

    except ImportError:
        return await _grep_fallback(
            ctx,
            pattern=pattern,
            search_path=search_path,
            glob=glob,
            output_mode=output_mode,
            case_insensitive=case_insensitive,
            head_limit=head_limit,
        )
    except Exception as e:
        return ToolResult(success=False, output="", error=str(e))


async def _grep_fallback(
    ctx: RunContext[MiniCCDeps],
    *,
    pattern: str,
    search_path: Path,
    glob: str | None,
    output_mode: str,
    case_insensitive: bool,
    head_limit: int | None,
) -> ToolResult:
    flags = re.IGNORECASE if case_insensitive else 0
    try:
        regex = re.compile(pattern, flags=flags)
    except re.error as e:
        return ToolResult(success=False, output="", error=f"无效正则: {e}")

    matched_files: list[str] = []
    matched_lines: list[str] = []
    file_counts: dict[str, int] = {}

    for p in search_path.rglob("*"):
        if not p.is_file():
            continue
        if glob and not p.match(glob):
            continue
        try:
            text = p.read_text(encoding="utf-8")
        except Exception:
            continue
        hits = 0
        for i, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                hits += 1
                if output_mode == "content":
                    matched_lines.append(f"{p}:{i}:{line}")
        if hits:
            matched_files.append(str(p))
            file_counts[str(p)] = hits

    if output_mode == "files_with_matches":
        output = "\n".join(matched_files)
    elif output_mode == "count":
        output = "\n".join(f"{f}:{c}" for f, c in file_counts.items())
    else:
        output = "\n".join(matched_lines)

    if not output.strip():
        return ToolResult(success=True, output=f"未找到匹配 '{pattern}' 的内容")

    if head_limit:
        lines = output.split("\n")
        if len(lines) > head_limit:
            output = "\n".join(lines[:head_limit]) + "\n... 还有更多结果"

    if len(output) > MAX_OUTPUT_CHARS:
        output = output[:MAX_OUTPUT_CHARS] + "\n... 输出已截断"

    return ToolResult(success=True, output=output)

