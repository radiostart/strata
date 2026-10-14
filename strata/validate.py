"""Document validation: front matter, required sections and evidence-tag references.

Rules (``docs/en/cli.md`` § validate):

- A Markdown file is checked when its front matter has a ``type`` that the manifest declares. Files
  without front matter, or without ``type``, are not documents strata manages and are skipped.
- An undeclared ``type`` is a warning, not an error.
- Every key in the type's ``frontmatter`` list must be present and non-empty.
- Every heading in the type's ``sections`` list must appear as a level-2 heading. A leading number
  (``1.``, ``2.3``, ``4)``) and letter case are ignored when comparing.
- An evidence tag with a ``reference`` pattern must have a match for that pattern on the same line.
- Text inside fenced code blocks is ignored for headings and tags.

The checks take text, not files, so a proposed document can be validated before it is written.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter
from .manifest import Manifest

ERROR = "error"
WARNING = "warning"
NUMBER_PREFIX_RE = re.compile(r"^\d+(?:\.\d+)*[.)]?\s+")
FENCE_RE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class Problem:
    path: str
    line: int          # 1-based; 0 when the problem is about the whole file
    severity: str      # ERROR | WARNING
    key: str           # message key in the catalog
    params: tuple[tuple[str, str], ...] = ()

    def param_dict(self) -> dict[str, str]:
        return dict(self.params)


def _norm_heading(text: str) -> str:
    text = text.strip().rstrip("#").strip()
    return NUMBER_PREFIX_RE.sub("", text).casefold()


def _body_lines(text: str) -> list[tuple[int, str]]:
    """(line number, line) pairs after the front matter, with fenced code blocks removed."""
    lines = text.splitlines()
    start = 0
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() in ("---", "..."):
                start = i + 1
                break
    out, fence = [], None
    for i in range(start, len(lines)):
        line = lines[i]
        m = FENCE_RE.match(line)
        if m:
            fence = None if fence == m.group(1) else (fence or m.group(1))
            continue
        if fence is None:
            out.append((i + 1, line))
    return out


def check_text(m: Manifest, rel: str, text: str) -> list[Problem]:
    """Problems in one document's text. ``rel`` is used for reporting only."""
    fm = frontmatter.parse(text)
    if fm is None:
        if text.lstrip().startswith("---"):
            return [Problem(rel, 1, ERROR, "validate.frontmatter_unterminated")]
        return []
    doc_type = fm.get("type")
    if not isinstance(doc_type, str) or not doc_type:
        return []
    dtype = next((d for d in m.document_types if d.id == doc_type), None)
    if dtype is None:
        return [Problem(rel, 1, WARNING, "validate.unknown_type", (("type", doc_type),))]

    problems: list[Problem] = []
    for key in dtype.frontmatter:
        val = fm.get(key)
        if val is None or val == "" or val == []:
            problems.append(Problem(rel, 1, ERROR, "validate.missing_key", (("key", key), ("type", doc_type))))

    body = _body_lines(text)
    headings = {_norm_heading(line[3:]) for _, line in body if line.startswith("## ")}
    for section in dtype.sections:
        if _norm_heading(section) not in headings:
            problems.append(Problem(rel, 0, ERROR, "validate.missing_section", (("section", section), ("type", doc_type))))

    tags = [(t, re.compile(t.reference)) for t in m.evidence_tags if t.reference]
    for lineno, line in body:
        for tag, ref in tags:
            if tag.label in line and not ref.search(line):
                problems.append(Problem(rel, lineno, ERROR, "validate.tag_without_reference",
                                        (("label", tag.label), ("pattern", tag.reference or ""))))
    return problems


def check_file(m: Manifest, path: Path) -> list[Problem]:
    rel = path.relative_to(m.root).as_posix() if path.is_relative_to(m.root) else str(path)
    try:
        text = path.read_text("utf-8")
    except UnicodeDecodeError:
        return [Problem(rel, 0, ERROR, "validate.not_utf8")]
    except OSError as e:
        return [Problem(rel, 0, ERROR, "validate.unreadable", (("error", str(e)),))]
    return check_text(m, rel, text)


def markdown_files(root: Path) -> list[Path]:
    """Every ``*.md`` under ``root``, skipping hidden directories (``.git``, ``.strata`` …)."""
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not d.startswith("."))
        out.extend(Path(dirpath) / f for f in sorted(filenames) if f.endswith(".md"))
    return out


def check_project(m: Manifest, paths: list[Path] | None = None) -> tuple[int, list[Problem]]:
    """(number of files examined, problems). ``paths`` may mix files and directories."""
    files: list[Path] = []
    for p in paths or [m.root]:
        files.extend(markdown_files(p) if p.is_dir() else [p])
    problems: list[Problem] = []
    for f in files:
        problems.extend(check_file(m, f))
    return len(files), problems
