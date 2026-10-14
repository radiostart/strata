"""Shared test helpers: build a temporary project from a fixture."""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import tomllib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(REPO))

FIXTURE_NAMES = sorted(p.name for p in FIXTURES.iterdir() if (p / ".strata" / "strata.toml").is_file())


class Project:
    """A throw-away copy of a fixture under the system temp directory."""

    def __init__(self, fixture: str):
        self.fixture = fixture
        self._tmp = tempfile.TemporaryDirectory(prefix=f"strata-{fixture}-")
        # realpath: macOS puts temp dirs behind the /var -> /private/var symlink
        self.root = Path(os.path.realpath(self._tmp.name)) / "project"
        shutil.copytree(FIXTURES / fixture, self.root, ignore=shutil.ignore_patterns("paths.toml"))
        self.paths: dict[str, str] = tomllib.loads((FIXTURES / fixture / "paths.toml").read_text("utf-8"))

    def path(self, key: str) -> Path:
        return self.root / self.paths[key]

    def write(self, key_or_rel: str, body: str = "x\n", status: str | None = None) -> Path:
        rel = self.paths.get(key_or_rel, key_or_rel)
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        text = body if status is None else f"---\ntitle: t\nstatus: {status}\n---\n\n{body}"
        p.write_text(text, encoding="utf-8")
        return p

    def close(self) -> None:
        self._tmp.cleanup()
