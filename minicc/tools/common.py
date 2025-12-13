from __future__ import annotations

import difflib
from pathlib import Path

from minicc.core.models import DiffLine

DEFAULT_READ_LIMIT = 2000
MAX_OUTPUT_CHARS = 30000
DEFAULT_BASH_TIMEOUT_MS = 120000


def resolve_path(cwd: str, path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return Path(cwd) / p


def normalize_whitespace(text: str) -> str:
    text = text.replace("\t", "    ")
    lines = [line.rstrip() for line in text.split("\n")]
    return "\n".join(lines)


def find_whitespace_tolerant(content: str, normalized_pattern: str) -> str | None:
    content_lines = content.split("\n")
    pattern_lines = normalized_pattern.split("\n")
    pattern_len = len(pattern_lines)

    for i in range(len(content_lines) - pattern_len + 1):
        window = content_lines[i : i + pattern_len]
        normalized_window = [normalize_whitespace(line) for line in window]
        if "\n".join(normalized_window) == normalized_pattern:
            return "\n".join(window)
    return None


def generate_unified_diff(old: str, new: str, filename: str = "") -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(
        old_lines,
        new_lines,
        fromfile=f"a/{filename}" if filename else "a",
        tofile=f"b/{filename}" if filename else "b",
    )
    return "".join(diff)


def generate_diff_lines(old: str, new: str) -> list[DiffLine]:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, lineterm="")
    result: list[DiffLine] = []

    for line in diff:
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith("+"):
            result.append(DiffLine(type="add", content=line[1:].rstrip("\n")))
        elif line.startswith("-"):
            result.append(DiffLine(type="remove", content=line[1:].rstrip("\n")))
        else:
            result.append(DiffLine(type="context", content=line.rstrip("\n")))
    return result


def format_diff_lines(diff_lines: list[DiffLine]) -> str:
    lines: list[str] = []
    for line in diff_lines:
        prefix = {"add": "+", "remove": "-", "context": " "}.get(line.type, " ")
        lines.append(f"{prefix}{line.content}")
    return "\n".join(lines)

