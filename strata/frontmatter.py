"""Minimal front-matter reader.

Reads the ``---`` block at the top of a Markdown file. Supports ``key: value`` scalars and simple
lists (``key: [a, b]`` or indented ``- item`` lines). This is enough for strata's needs and keeps the
package free of third-party YAML parsers.
"""

from __future__ import annotations

from pathlib import Path

MAX_BYTES = 64 * 1024


def _scalar(raw: str) -> str:
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "'\"":
        v = v[1:-1]
    return v


def parse(text: str) -> dict[str, object] | None:
    """Front matter as a dict, or ``None`` when the text has none."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    out: dict[str, object] = {}
    current: str | None = None
    for line in lines[1:]:
        if line.strip() in ("---", "..."):
            return out
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line[:1] in (" ", "\t"):
            item = line.strip()
            if current is not None and item.startswith("- "):
                lst = out.setdefault(current, [])
                if isinstance(lst, list):
                    lst.append(_scalar(item[2:]))
            continue
        key, sep, val = line.partition(":")
        if not sep:
            continue
        key = key.strip()
        val = val.strip()
        current = key
        if val.startswith("[") and val.endswith("]"):
            out[key] = [_scalar(v) for v in val[1:-1].split(",") if v.strip()]
        elif val == "":
            out[key] = []
        else:
            out[key] = _scalar(val)
    return None  # unterminated block is not front matter


def read(path: Path) -> dict[str, object] | None:
    try:
        with path.open("rb") as f:
            head = f.read(MAX_BYTES)
    except OSError:
        return None
    return parse(head.decode("utf-8", errors="replace"))


def status(path: Path) -> str | None:
    fm = read(path)
    if not fm:
        return None
    v = fm.get("status")
    return v if isinstance(v, str) else None
