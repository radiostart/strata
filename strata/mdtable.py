"""Markdown pipe tables: escaping, splitting and rendering rows.

Cells escape ``|`` as ``\\|`` and never contain newlines, so one row is always one line.
"""

from __future__ import annotations

import re

_SPLIT_RE = re.compile(r"(?<!\\)\|")


def escape(cell: str) -> str:
    return " ".join(cell.replace("\\|", "|").replace("|", "\\|").split())


def unescape(cell: str) -> str:
    return cell.replace("\\|", "|").strip()


def render(cells: list[str]) -> str:
    return "| " + " | ".join(escape(c) for c in cells) + " |"


def separator(n: int) -> str:
    return "| " + " | ".join("---" for _ in range(n)) + " |"


def split(line: str) -> list[str] | None:
    """Cells of a table row, or ``None`` when ``line`` is not a row (or is the separator row)."""
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")) or len(s) < 2:
        return None
    cells = [unescape(c) for c in _SPLIT_RE.split(s[1:-1])]
    if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
        return None
    return cells
