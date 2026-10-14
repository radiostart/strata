"""Append-only run records: ``.strata/records/YYYY-MM.md``.

One Markdown table per month. A row is appended under an exclusive file lock where the platform has
one. Rows are never rewritten; the guard treats the folder as append-only whatever the manifest says.
"""

from __future__ import annotations

import datetime as dt
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from . import RECORDS_REL, mdtable
from .messages import text

try:  # POSIX only; on other platforms appends are not locked
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

COLUMNS = ("time", "kind", "target", "actor", "result", "evidence", "note")
MAX_CELL = 300


class RecordError(Exception):
    def __init__(self, key: str, **params: object):
        self.key = key
        self.params = params
        super().__init__(key)


@dataclass(frozen=True)
class Record:
    time: str
    kind: str
    target: str
    actor: str
    result: str
    evidence: str = ""
    note: str = ""

    def cells(self) -> list[str]:
        return [self.time, self.kind, self.target, self.actor, self.result, self.evidence, self.note]


def month_file(root: Path, when: dt.datetime) -> Path:
    return root / RECORDS_REL / f"{when:%Y-%m}.md"


@contextmanager
def _locked_append(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        if fcntl is not None:
            fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield f
        finally:
            if fcntl is not None:
                fcntl.flock(f, fcntl.LOCK_UN)


def _header(lang: str, when: dt.datetime) -> str:
    title = text("record.title", lang, month=f"{when:%Y-%m}")
    labels = [text(f"record.column.{c}", lang) for c in COLUMNS]
    return f"# {title}\n\n{mdtable.render(labels)}\n{mdtable.separator(len(COLUMNS))}\n"


def append(root: Path, lang: str, kind: str, target: str, actor: str, result: str,
           evidence: str = "", note: str = "", now: dt.datetime | None = None) -> tuple[Path, Record]:
    for name, value in (("kind", kind), ("target", target), ("actor", actor), ("result", result)):
        if not value or not value.strip():
            raise RecordError("record.empty", field=name)
    for name, value in (("kind", kind), ("target", target), ("actor", actor), ("result", result),
                        ("evidence", evidence), ("note", note)):
        if len(value) > MAX_CELL:
            raise RecordError("record.too_long", field=name, limit=MAX_CELL)
    when = (now or dt.datetime.now().astimezone()).replace(microsecond=0)
    rec = Record(when.isoformat(), kind, target, actor, result, evidence, note)
    path = month_file(root, when)
    with _locked_append(path) as f:
        if f.tell() == 0:
            f.write(_header(lang, when))
        f.write(mdtable.render(rec.cells()) + "\n")
    return path, rec


def read_month(path: Path) -> list[Record]:
    if not path.is_file():
        return []
    rows: list[Record] = []
    seen_header = False
    for line in path.read_text("utf-8").splitlines():
        cells = mdtable.split(line)
        if cells is None or len(cells) != len(COLUMNS):
            continue
        if not seen_header:
            seen_header = True  # first row of the table is the header
            continue
        rows.append(Record(*cells))
    return rows


def recent(root: Path, limit: int = 10) -> list[Record]:
    folder = root / RECORDS_REL
    if not folder.is_dir():
        return []
    rows: list[Record] = []
    for f in sorted(folder.glob("????-??.md"), reverse=True):
        rows = read_month(f) + rows
        if len(rows) >= limit:
            break
    return rows[-limit:]
