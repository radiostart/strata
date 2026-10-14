"""Path helpers: glob matching, case folding and project-root discovery.

All matching is done on POSIX-style paths relative to a project root.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from pathlib import Path

from . import MANIFEST_DIR, MANIFEST_FILE


@lru_cache(maxsize=512)
def _compile(pattern: str, fold: bool) -> re.Pattern[str]:
    """Translate a glob into a regex.

    ``**`` matches any number of path segments (including none), ``*`` matches within one segment,
    ``?`` matches one character within a segment. A trailing ``/**`` also matches the directory
    itself, so ``docs/**`` protects ``docs`` as a whole.
    """
    i, n, out = 0, len(pattern), []
    while i < n:
        c = pattern[i]
        if c == "*":
            if pattern[i : i + 2] == "**":
                i += 2
                if i < n and pattern[i] == "/":
                    i += 1
                    out.append("(?:.*/)?")
                else:
                    out.append(".*")
                continue
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    body = "".join(out)
    if pattern.endswith("/**"):
        # `a/**` -> `a(?:/.*)?` so the directory itself matches too.
        body = body[: -len("/.*")] + "(?:/.*)?" if body.endswith("/.*") else body
    return re.compile(f"^{body}$", re.IGNORECASE if fold else 0)


def glob_match(pattern: str, rel: str, *, fold: bool = False) -> bool:
    """True when ``rel`` (POSIX, relative) matches ``pattern``."""
    return bool(_compile(pattern, fold).match(rel))


def any_match(patterns: list[str] | tuple[str, ...], rel: str, *, fold: bool = False) -> bool:
    return any(glob_match(p, rel, fold=fold) for p in patterns)


def pattern_prefix(pattern: str) -> str:
    """The literal leading directory part of a glob (``tracks/*/x`` -> ``tracks``)."""
    parts = []
    for seg in pattern.split("/"):
        if any(ch in seg for ch in "*?["):
            break
        parts.append(seg)
    return "/".join(parts)


@lru_cache(maxsize=64)
def case_blind(root: str) -> bool:
    """True when the file system under ``root`` ignores letter case (default on macOS and Windows)."""
    p = Path(root)
    name = p.name
    swapped = name.swapcase()
    if swapped == name:
        # No letters to swap; probe with a sibling that certainly exists.
        probe = p / MANIFEST_DIR
        if not probe.exists():
            return os.name == "nt"
        return (p / MANIFEST_DIR.upper()).exists()
    return (p.parent / swapped).exists()


def normalize(path: str | os.PathLike[str], cwd: str | os.PathLike[str]) -> Path:
    """Absolute, normalised path. Relative paths resolve against ``cwd``.

    Symlinks in existing parents are resolved; the leaf may not exist yet.
    """
    p = Path(os.path.expanduser(str(path)))
    if not p.is_absolute():
        p = Path(cwd) / p
    p = Path(os.path.normpath(p))
    parent = p.parent
    try:
        parent = Path(os.path.realpath(parent))
    except OSError:
        pass
    return parent / p.name if p.name else parent


def find_root(path: Path) -> Path | None:
    """Nearest ancestor (or the path itself) that holds ``.strata/strata.toml``.

    Each git worktree carries its own manifest, so this naturally judges a path by the tree it
    belongs to.
    """
    cur = path if path.is_dir() else path.parent
    for cand in (cur, *cur.parents):
        if (cand / MANIFEST_DIR / MANIFEST_FILE).is_file():
            return cand
    return None


def rel_to(path: Path, root: Path) -> str | None:
    """POSIX path of ``path`` relative to ``root``; ``None`` when outside. Case-aware."""
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        pass
    if case_blind(str(root)):
        ps, rs = str(path), str(root)
        if ps.lower().startswith(rs.lower().rstrip(os.sep) + os.sep):
            return Path(ps[len(rs.rstrip(os.sep)) + 1 :]).as_posix()
        if ps.lower() == rs.lower():
            return "."
    return None
