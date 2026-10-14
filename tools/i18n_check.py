#!/usr/bin/env python3
"""Check that every translation is up to date with its English source.

A translation starts with a marker line:

    <!-- i18n: source=docs/en/design.md sha=0123456789ab -->

``sha`` is the first 12 hex digits of the SHA-256 of the source file. When the source changes, the
marker no longer matches and this check fails until the translation is updated and re-stamped.

Pairs checked:
    README.md            -> README.ko.md
    docs/en/<path>.md    -> docs/<lang>/<path>.md   for every language folder under docs/

Usage:
    python3 tools/i18n_check.py                 # check; exit 1 on any problem
    python3 tools/i18n_check.py --stamp FILE    # after translating, record the current source hash in FILE
"""

from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MARKER_RE = re.compile(r"^<!-- i18n: source=(\S+) sha=([0-9a-f]{12}) -->\s*$")
SOURCE_LANG = "en"


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def pairs(repo: Path) -> list[tuple[Path, Path]]:
    out = []
    readme = repo / "README.md"
    if readme.is_file():
        for t in sorted(repo.glob("README.*.md")):
            out.append((readme, t))
    docs = repo / "docs"
    src_root = docs / SOURCE_LANG
    if src_root.is_dir():
        langs = [d for d in sorted(docs.iterdir()) if d.is_dir() and d.name != SOURCE_LANG]
        for src in sorted(src_root.rglob("*.md")):
            rel = src.relative_to(src_root)
            for lang_dir in langs:
                out.append((src, lang_dir / rel))
    return out


def check(repo: Path) -> list[str]:
    problems = []
    expected_targets = set()
    for src, target in pairs(repo):
        expected_targets.add(target)
        rel_t = target.relative_to(repo).as_posix()
        rel_s = src.relative_to(repo).as_posix()
        if not target.is_file():
            problems.append(f"{rel_t}: missing translation of {rel_s}")
            continue
        first = target.read_text("utf-8").splitlines()[:1]
        m = MARKER_RE.match(first[0]) if first else None
        if not m:
            problems.append(f"{rel_t}: first line must be <!-- i18n: source={rel_s} sha=... -->")
            continue
        if m.group(1) != rel_s:
            problems.append(f"{rel_t}: marker names source {m.group(1)}, expected {rel_s}")
        elif m.group(2) != source_hash(src):
            problems.append(f"{rel_t}: out of date — {rel_s} changed since it was translated "
                            f"(update the text, then run tools/i18n_check.py --stamp {rel_t})")
    docs = repo / "docs"
    if docs.is_dir():
        for lang_dir in (d for d in docs.iterdir() if d.is_dir() and d.name != SOURCE_LANG):
            for t in lang_dir.rglob("*.md"):
                if t not in expected_targets:
                    problems.append(f"{t.relative_to(repo).as_posix()}: translation without an English source")
    return problems


def stamp(repo: Path, target: Path) -> None:
    target = target.resolve()
    for src, t in pairs(repo):
        if t.resolve() == target:
            marker = f"<!-- i18n: source={src.relative_to(repo).as_posix()} sha={source_hash(src)} -->"
            lines = target.read_text("utf-8").splitlines(keepends=True)
            if lines and MARKER_RE.match(lines[0].rstrip("\n")):
                lines[0] = marker + "\n"
            else:
                lines.insert(0, marker + "\n")
            target.write_text("".join(lines), "utf-8")
            print(f"stamped {target.relative_to(repo)} -> {marker}")
            return
    raise SystemExit(f"{target} is not a known translation target")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--stamp", type=Path, help="record the current source hash in this translation")
    ap.add_argument("--root", type=Path, default=REPO)
    args = ap.parse_args(argv)
    repo = args.root.resolve()
    if args.stamp:
        stamp(repo, args.stamp if args.stamp.is_absolute() else Path.cwd() / args.stamp)
        return 0
    problems = check(repo)
    for p in problems:
        print(p)
    if not problems:
        print(f"i18n: {len(pairs(repo))} translation(s) up to date")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
