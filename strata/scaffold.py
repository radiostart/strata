"""``strata init``: create a project skeleton from ``templates/<language>/``.

A template folder is copied file by file into the project. ``manifest.toml`` becomes
``.strata/strata.toml`` (kept under another name so the template folder is not itself a strata project).
``{{project}}`` and ``{{date}}`` in file contents are replaced by the project name and today's date. Files named ``.keep`` create their
folder and are not copied. Register files declared by the manifest are then created with their header,
and an ``init`` record is appended. The command never overwrites: if any destination exists, nothing is
written.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path

from . import MANIFEST_REL, records, registers
from .manifest import ID_RE, load

TEMPLATES = Path(__file__).resolve().parents[1] / "templates"
PLACEHOLDER = "{{project}}"
DATE_PLACEHOLDER = "{{date}}"
KEEP = ".keep"
TEMPLATE_MANIFEST = "manifest.toml"


class ScaffoldError(Exception):
    def __init__(self, key: str, **params: object):
        self.key = key
        self.params = params
        super().__init__(key)


def languages() -> list[str]:
    if not TEMPLATES.is_dir():
        return []
    return sorted(p.name for p in TEMPLATES.iterdir() if (p / TEMPLATE_MANIFEST).is_file())


def plan(root: Path, lang: str, name: str) -> list[tuple[Path, Path | None]]:
    """(destination, source) pairs; ``source`` is ``None`` for a folder to create."""
    if lang not in languages():
        raise ScaffoldError("init.unknown_language", language=lang, known=", ".join(languages()))
    if not ID_RE.match(name):
        raise ScaffoldError("init.bad_name", name=name)
    src_root = TEMPLATES / lang
    out: list[tuple[Path, Path | None]] = []
    for src in sorted(src_root.rglob("*")):
        if not src.is_file():
            continue
        rel = src.relative_to(src_root)
        if rel.as_posix() == TEMPLATE_MANIFEST:
            rel = Path(MANIFEST_REL)
        if rel.name == KEEP:
            out.append((root / rel.parent, None))
        else:
            out.append((root / rel, src))
    return out


def init(root: Path, lang: str, name: str, actor: str = "strata") -> list[Path]:
    """Create the skeleton. Returns created files and folders, relative to ``root``."""
    steps = plan(root, lang, name)
    existing = [d for d, s in steps if s is not None and d.exists()]
    if (root / MANIFEST_REL).exists():
        existing.insert(0, root / MANIFEST_REL)
    if existing:
        raise ScaffoldError("init.exists", path=existing[0].relative_to(root).as_posix())
    created: list[Path] = []
    for dest, src in steps:
        if src is None:
            if not dest.exists():
                dest.mkdir(parents=True)
                created.append(dest.relative_to(root))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        body = src.read_text("utf-8").replace(PLACEHOLDER, name).replace(DATE_PLACEHOLDER, dt.date.today().isoformat())
        dest.write_text(body, "utf-8")
        created.append(dest.relative_to(root))
    m = load(root)
    for reg in m.registers:
        path = root / reg.path
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(registers.header(m.project.language, reg), "utf-8")
            created.append(path.relative_to(root))
    rec_path, _ = records.append(root, m.project.language, kind="init", target=".", actor=actor, result="ok",
                                 note=f"{lang} template")
    created.append(rec_path.relative_to(root))
    return created


def default_name(root: Path) -> str:
    """A valid project id derived from the folder name."""
    slug = re.sub(r"[^a-z0-9-]+", "-", root.resolve().name.lower()).strip("-")
    if not slug or not slug[0].isalpha():
        slug = "project" if not slug else f"p-{slug}"
    return slug
