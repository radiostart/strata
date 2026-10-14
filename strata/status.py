"""``strata status``: a read-only summary of a project.

Counts come from the files on disk every time; nothing is cached.
"""

from __future__ import annotations

import os
from collections import Counter
from pathlib import Path

from . import frontmatter, records, registers
from .manifest import Manifest
from .paths import any_match, case_blind


def _files(root: Path) -> list[str]:
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        rel_dir = Path(dirpath).relative_to(root)
        out.extend((rel_dir / f).as_posix() for f in filenames if not f.startswith("."))
    return out


def summary(m: Manifest, recent: int = 3) -> dict:
    fold = case_blind(str(m.root))
    files = _files(m.root)

    layer_counts: Counter[str] = Counter()
    for rel in files:
        layer = next((x for x in m.layers if any_match(x.paths, rel, fold=fold)), None)
        if layer is not None:
            layer_counts[layer.id] += 1

    types: Counter[str] = Counter()
    for rel in files:
        if rel.endswith(".md"):
            fm = frontmatter.read(m.root / rel)
            t = fm.get("type") if fm else None
            types[t if isinstance(t, str) and t else ""] += 1

    regs = []
    for reg in m.registers:
        try:
            rows = registers.entries(m, reg)
            regs.append({"id": reg.id, "path": reg.path, "open": sum(r.status == registers.OPEN for r in rows),
                         "total": len(rows), "missing": False})
        except registers.RegisterError:
            regs.append({"id": reg.id, "path": reg.path, "open": 0, "total": 0, "missing": True})

    return {
        "project": m.project.name,
        "language": m.project.language,
        "tracks": [{"id": t.id, "path": t.path, "open": t.open} for t in m.tracks],
        "layers": [{"id": x.id, "mode": x.mode, "files": layer_counts[x.id]} for x in m.layers],
        "documents": {k: v for k, v in sorted(types.items()) if k},
        "untyped_markdown": types[""],
        "declared_types": [d.id for d in m.document_types],
        "registers": regs,
        "recent_records": [r.__dict__ for r in records.recent(m.root, recent)],
    }
