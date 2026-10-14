"""Registers: append-only lists of upward reports or open issues.

A register is a Markdown table declared in ``[[registers]]``. Its first column holds IDs
``{prefix}-{n}``; the next ID is one more than the highest ID **in that column**, so an ID quoted in a
title can never shift numbering. A missing register file is an error, never silently created: a
wrong path must not restart numbering at 1.

Status values are the fixed tokens ``open`` and ``closed`` so any language reads them the same way.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from pathlib import Path

from . import mdtable
from .manifest import Manifest, Register
from .messages import text

COLUMNS = ("id", "date", "status", "title", "source", "resolution")
OPEN, CLOSED = "open", "closed"


class RegisterError(Exception):
    def __init__(self, key: str, **params: object):
        self.key = key
        self.params = params
        super().__init__(key)


@dataclass(frozen=True)
class Entry:
    id: str
    date: str
    status: str
    title: str
    source: str
    resolution: str
    line: int  # 0-based line index in the file


def find(m: Manifest, register_id: str) -> Register:
    reg = next((r for r in m.registers if r.id == register_id), None)
    if reg is None:
        raise RegisterError("register.unknown", register=register_id,
                            known=", ".join(r.id for r in m.registers) or "-")
    return reg


def header(lang: str, reg: Register) -> str:
    labels = [text(f"register.column.{c}", lang) for c in COLUMNS]
    return (f"# {text('register.title', lang, register=reg.id)}\n\n"
            f"{mdtable.render(labels)}\n{mdtable.separator(len(COLUMNS))}\n")


def _path(m: Manifest, reg: Register) -> Path:
    return m.root / reg.path


def entries(m: Manifest, reg: Register) -> list[Entry]:
    path = _path(m, reg)
    if not path.is_file():
        raise RegisterError("register.missing_file", register=reg.id, path=reg.path)
    id_re = re.compile(rf"^{re.escape(reg.prefix)}-(\d+)$")
    out = []
    for i, line in enumerate(path.read_text("utf-8").splitlines()):
        cells = mdtable.split(line)
        if cells is None or len(cells) < len(COLUMNS) or not id_re.match(cells[0]):
            continue
        out.append(Entry(*cells[: len(COLUMNS)], line=i))
    return out


def next_id(m: Manifest, reg: Register) -> str:
    id_re = re.compile(rf"^{re.escape(reg.prefix)}-(\d+)$")
    highest = max((int(id_re.match(e.id).group(1)) for e in entries(m, reg)), default=0)
    return f"{reg.prefix}-{highest + 1}"


def add(m: Manifest, register_id: str, title: str, source: str = "", today: dt.date | None = None) -> Entry:
    if not title.strip():
        raise RegisterError("register.empty_title")
    reg = find(m, register_id)
    new_id = next_id(m, reg)
    day = (today or dt.date.today()).isoformat()
    path = _path(m, reg)
    body = path.read_text("utf-8")
    row = mdtable.render([new_id, day, OPEN, title, source, ""])
    with path.open("a", encoding="utf-8") as f:
        if body and not body.endswith("\n"):
            f.write("\n")
        f.write(row + "\n")
    return Entry(new_id, day, OPEN, title, source, "", line=-1)


def close(m: Manifest, entry_id: str, resolution: str) -> Entry:
    """Mark one open entry closed and fill its resolution cell. Only that line changes."""
    if not resolution.strip():
        raise RegisterError("register.empty_resolution")
    reg = next((r for r in m.registers if entry_id.startswith(r.prefix + "-")), None)
    if reg is None:
        raise RegisterError("register.unknown_id", id=entry_id)
    found = next((e for e in entries(m, reg) if e.id == entry_id), None)
    if found is None:
        raise RegisterError("register.no_such_id", id=entry_id, register=reg.id)
    if found.status != OPEN:
        raise RegisterError("register.not_open", id=entry_id, status=found.status)
    path = _path(m, reg)
    lines = path.read_text("utf-8").splitlines(keepends=True)
    ending = "\n" if lines[found.line].endswith("\n") else ""
    closed = Entry(found.id, found.date, CLOSED, found.title, found.source, resolution, found.line)
    lines[found.line] = mdtable.render([closed.id, closed.date, closed.status, closed.title, closed.source,
                                        closed.resolution]) + ending
    path.write_text("".join(lines), "utf-8")
    return closed
