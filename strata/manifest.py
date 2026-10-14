"""Load and validate ``.strata/strata.toml``.

Every key has a schema entry. Unknown keys are errors, so the manifest never drifts into prose that
no tool reads.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import MANIFEST_REL

SCHEMA_VERSION = 1
LANGUAGES = ("en", "ko")
LAYER_MODES = ("immutable", "frozen", "append-only", "living", "scratch")
ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
PREFIX_RE = re.compile(r"^[A-Z][A-Z0-9]*$")


class ManifestError(Exception):
    """The manifest exists but is invalid. ``problems`` lists every problem found."""

    def __init__(self, path: Path, problems: list[str]):
        self.path = path
        self.problems = problems
        super().__init__(f"{path}: " + "; ".join(problems))


@dataclass(frozen=True)
class Project:
    name: str
    language: str
    schema: int


@dataclass(frozen=True)
class Track:
    id: str
    path: str
    open: bool


@dataclass(frozen=True)
class Layer:
    id: str
    mode: str
    paths: tuple[str, ...]


@dataclass(frozen=True)
class DocumentType:
    id: str
    frontmatter: tuple[str, ...]
    sections: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceTag:
    tag: str
    label: str
    reference: str | None


@dataclass(frozen=True)
class Cycle:
    id: str
    prefix: str
    track: str
    folder: str
    steps: tuple[str, ...]
    max_rounds: int
    asks_per_round: int
    asks_total: int
    retry_to: tuple[str, ...]
    approver: str


@dataclass(frozen=True)
class Role:
    id: str
    writes: tuple[str, ...]
    gates: tuple[str, ...]


@dataclass(frozen=True)
class Register:
    id: str
    prefix: str
    path: str


@dataclass(frozen=True)
class Manifest:
    root: Path
    project: Project
    tracks: tuple[Track, ...] = ()
    layers: tuple[Layer, ...] = ()
    frozen_statuses: tuple[str, ...] = ()
    document_types: tuple[DocumentType, ...] = ()
    evidence_tags: tuple[EvidenceTag, ...] = ()
    cycles: tuple[Cycle, ...] = ()
    roles: tuple[Role, ...] = ()
    registers: tuple[Register, ...] = ()

    def track(self, track_id: str) -> Track | None:
        return next((t for t in self.tracks if t.id == track_id), None)


# ── schema ──────────────────────────────────────────────────────────────────────────────────────────
# Each entry: key -> (type, required, default). Types: str, int, bool, "strs" (list of str).

_PROJECT = {"name": (str, True, None), "language": (str, False, "en"), "schema": (int, True, None)}
_TRACK = {"id": (str, True, None), "path": (str, True, None), "open": (bool, False, False)}
_LAYER = {"id": (str, True, None), "mode": (str, True, None), "paths": ("strs", True, None)}
_DOCTYPE = {"id": (str, True, None), "frontmatter": ("strs", False, []), "sections": ("strs", False, [])}
_TAG = {"tag": (str, True, None), "label": (str, True, None), "reference": (str, False, None)}
_CYCLE = {
    "id": (str, True, None),
    "prefix": (str, True, None),
    "track": (str, True, None),
    "folder": (str, True, None),
    "steps": ("strs", True, None),
    "max_rounds": (int, False, 3),
    "asks_per_round": (int, False, 1),
    "asks_total": (int, False, 2),
    "retry_to": ("strs", False, []),
    "approver": (str, True, None),
}
_ROLE = {"id": (str, True, None), "writes": ("strs", False, []), "gates": ("strs", False, [])}
_REGISTER = {"id": (str, True, None), "prefix": (str, True, None), "path": (str, True, None)}
_TOP = {"project", "tracks", "layers", "documents", "evidence", "cycles", "roles", "registers"}


def _check_table(where: str, raw: Any, schema: dict, problems: list[str]) -> dict[str, Any]:
    if not isinstance(raw, dict):
        problems.append(f"{where}: expected a table")
        return {}
    out: dict[str, Any] = {}
    for key in raw:
        if key not in schema:
            problems.append(f"{where}: unknown key '{key}'")
    for key, (typ, required, default) in schema.items():
        if key not in raw:
            if required:
                problems.append(f"{where}: missing required key '{key}'")
            out[key] = default
            continue
        val = raw[key]
        if typ == "strs":
            if not isinstance(val, list) or not all(isinstance(v, str) for v in val):
                problems.append(f"{where}.{key}: expected a list of strings")
                val = default
        elif typ is int:
            if not isinstance(val, int) or isinstance(val, bool):
                problems.append(f"{where}.{key}: expected an integer")
                val = default
        elif not isinstance(val, typ):
            problems.append(f"{where}.{key}: expected {typ.__name__}")
            val = default
        out[key] = val
    return out


def _array(where: str, raw: Any, schema: dict, problems: list[str]) -> list[dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        problems.append(f"{where}: expected an array of tables ([[{where}]])")
        return []
    return [_check_table(f"{where}[{i}]", item, schema, problems) for i, item in enumerate(raw)]


def _unique(where: str, items: list[dict[str, Any]], key: str, problems: list[str]) -> None:
    seen: set[str] = set()
    for item in items:
        v = item.get(key)
        if v is None:
            continue
        if v in seen:
            problems.append(f"{where}: duplicate {key} '{v}'")
        seen.add(v)


def _relpath_ok(p: str) -> bool:
    return bool(p) and not p.startswith("/") and ".." not in p.split("/") and "\\" not in p


def parse(data: dict[str, Any], root: Path, source: Path) -> Manifest:
    """Validate parsed TOML and build a :class:`Manifest`. Raises :class:`ManifestError`."""
    problems: list[str] = []
    for key in data:
        if key not in _TOP:
            problems.append(f"unknown top-level key '{key}'")

    if "project" not in data:
        problems.append("missing [project] table")
    project = _check_table("project", data.get("project", {}), _PROJECT, problems)
    if project.get("schema") not in (None, SCHEMA_VERSION):
        problems.append(f"project.schema: unsupported version {project.get('schema')} (supported: {SCHEMA_VERSION})")
    if project.get("language") not in LANGUAGES:
        problems.append(f"project.language: must be one of {', '.join(LANGUAGES)}")

    tracks = _array("tracks", data.get("tracks"), _TRACK, problems)
    layers = _array("layers", data.get("layers"), _LAYER, problems)
    cycles = _array("cycles", data.get("cycles"), _CYCLE, problems)
    roles = _array("roles", data.get("roles"), _ROLE, problems)
    registers = _array("registers", data.get("registers"), _REGISTER, problems)

    documents = data.get("documents", {})
    if not isinstance(documents, dict):
        problems.append("documents: expected a table")
        documents = {}
    for key in documents:
        if key not in ("frozen_statuses", "types"):
            problems.append(f"documents: unknown key '{key}'")
    frozen = documents.get("frozen_statuses", [])
    if not isinstance(frozen, list) or not all(isinstance(s, str) for s in frozen):
        problems.append("documents.frozen_statuses: expected a list of strings")
        frozen = []
    doctypes = _array("documents.types", documents.get("types"), _DOCTYPE, problems)

    evidence = data.get("evidence", {})
    if not isinstance(evidence, dict):
        problems.append("evidence: expected a table")
        evidence = {}
    for key in evidence:
        if key != "tags":
            problems.append(f"evidence: unknown key '{key}'")
    tags = _array("evidence.tags", evidence.get("tags"), _TAG, problems)

    for where, items in (("tracks", tracks), ("layers", layers), ("cycles", cycles), ("roles", roles),
                         ("registers", registers), ("documents.types", doctypes)):
        _unique(where, items, "id", problems)
        for i, item in enumerate(items):
            v = item.get("id")
            if isinstance(v, str) and not ID_RE.match(v):
                problems.append(f"{where}[{i}].id: '{v}' must be lowercase letters, digits and '-'")
    _unique("evidence.tags", tags, "tag", problems)
    _unique("cycles", cycles, "prefix", problems)
    _unique("registers", registers, "prefix", problems)

    for i, t in enumerate(tracks):
        if isinstance(t.get("path"), str) and not _relpath_ok(t["path"]):
            problems.append(f"tracks[{i}].path: must be a relative path inside the project")
    for i, layer in enumerate(layers):
        if layer.get("mode") is not None and layer["mode"] not in LAYER_MODES:
            problems.append(f"layers[{i}].mode: must be one of {', '.join(LAYER_MODES)}")
        for p in layer.get("paths") or []:
            if not _relpath_ok(p):
                problems.append(f"layers[{i}].paths: '{p}' must be a relative glob inside the project")
    track_ids = {t["id"] for t in tracks if t.get("id")}
    role_ids = {r["id"] for r in roles if r.get("id")}
    for i, c in enumerate(cycles):
        if c.get("prefix") and not PREFIX_RE.match(c["prefix"]):
            problems.append(f"cycles[{i}].prefix: must be uppercase letters and digits")
        if c.get("track") and c["track"] not in track_ids:
            problems.append(f"cycles[{i}].track: unknown track '{c['track']}'")
        if c.get("approver") and roles and c["approver"] not in role_ids:
            problems.append(f"cycles[{i}].approver: unknown role '{c['approver']}'")
        steps = c.get("steps") or []
        for s in c.get("retry_to") or []:
            if s not in steps:
                problems.append(f"cycles[{i}].retry_to: '{s}' is not one of its steps")
        for key in ("max_rounds", "asks_per_round", "asks_total"):
            if isinstance(c.get(key), int) and c[key] < 0:
                problems.append(f"cycles[{i}].{key}: must not be negative")
    for i, r in enumerate(registers):
        if r.get("prefix") and not PREFIX_RE.match(r["prefix"]):
            problems.append(f"registers[{i}].prefix: must be uppercase letters and digits")

    if problems:
        raise ManifestError(source, problems)

    return Manifest(
        root=root,
        project=Project(name=project["name"], language=project["language"], schema=project["schema"]),
        tracks=tuple(Track(t["id"], t["path"].rstrip("/"), t["open"]) for t in tracks),
        layers=tuple(Layer(x["id"], x["mode"], tuple(x["paths"])) for x in layers),
        frozen_statuses=tuple(frozen),
        document_types=tuple(DocumentType(d["id"], tuple(d["frontmatter"]), tuple(d["sections"])) for d in doctypes),
        evidence_tags=tuple(EvidenceTag(t["tag"], t["label"], t["reference"]) for t in tags),
        cycles=tuple(
            Cycle(c["id"], c["prefix"], c["track"], c["folder"], tuple(c["steps"]), c["max_rounds"],
                  c["asks_per_round"], c["asks_total"], tuple(c["retry_to"]), c["approver"])
            for c in cycles
        ),
        roles=tuple(Role(r["id"], tuple(r["writes"]), tuple(r["gates"])) for r in roles),
        registers=tuple(Register(r["id"], r["prefix"], r["path"]) for r in registers),
    )


def load(root: Path) -> Manifest:
    """Load the manifest under ``root``. Raises :class:`FileNotFoundError` or :class:`ManifestError`."""
    source = root / MANIFEST_REL
    raw = source.read_bytes()
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError) as e:
        raise ManifestError(source, [f"not valid TOML: {e}"]) from e
    return parse(data, root, source)
