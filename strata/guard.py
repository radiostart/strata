"""Layer and track decisions for a single tool call.

The rules are in ``docs/en/design.md`` § 5. This module only decides; the hook entry point turns a
decision into an exit code and a message.
"""

from __future__ import annotations

import json
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import BYPASS_ENV, MANIFEST_DIR, MANIFEST_REL, RECORDS_REL, bashwrites, frontmatter
from .manifest import Layer, Manifest, ManifestError, load
from .paths import any_match, case_blind, find_root, normalize, pattern_prefix, rel_to

# Operations after resolving whether the target exists.
CREATE = "create"
EDIT = "edit"
OVERWRITE = "overwrite"
DELETE = "delete"

TREE_FILE_LIMIT = 5000
WRITE_TOOLS_PATH_KEY = {"Write": "file_path", "Edit": "file_path", "MultiEdit": "file_path",
                        "NotebookEdit": "notebook_path"}


@dataclass
class Block:
    key: str
    lang: str = "en"
    params: dict[str, object] = field(default_factory=dict)


@dataclass
class _Ctx:
    """Per-call cache: manifests by root."""

    manifests: dict[Path, Manifest | ManifestError] = field(default_factory=dict)

    def manifest(self, root: Path) -> Manifest | ManifestError:
        if root not in self.manifests:
            try:
                self.manifests[root] = load(root)
            except ManifestError as e:
                self.manifests[root] = e
            except OSError as e:
                self.manifests[root] = ManifestError(root / MANIFEST_REL, [f"cannot read: {e}"])
        return self.manifests[root]


def _language_hint(root: Path) -> str:
    """Best-effort message language when the manifest is invalid."""
    try:
        data = tomllib.loads((root / MANIFEST_REL).read_text(encoding="utf-8"))
        lang = data.get("project", {}).get("language")
        return lang if lang in ("en", "ko") else "en"
    except Exception:  # noqa: BLE001 — any failure means "use English"
        return "en"


def _under(rel: str, prefix: str, fold: bool) -> bool:
    if fold:
        rel, prefix = rel.lower(), prefix.lower()
    return rel == prefix or rel.startswith(prefix + "/")


RECORDS_LAYER = Layer("strata-records", "append-only", (f"{RECORDS_REL}/**",))


def _layer_for(m: Manifest, rel: str, fold: bool) -> Layer | None:
    if any_match(RECORDS_LAYER.paths, rel, fold=fold):
        return RECORDS_LAYER
    for layer in m.layers:
        if any_match(layer.paths, rel, fold=fold):
            return layer
    return None


def _judge_file(m: Manifest, abs_path: Path, rel: str, op: str, fold: bool) -> Block | None:
    """Decide one resolved operation on one path inside a valid manifest's project."""
    lang = m.project.language
    for track in m.tracks:
        if not track.open and _under(rel, track.path, fold):
            return Block("guard.closed_track", lang, {"path": rel, "track": track.id})
    layer = _layer_for(m, rel, fold)
    if layer is None:
        return None
    params = {"path": rel, "layer": layer.id}
    mode = layer.mode
    if mode == "scratch":
        return None
    if mode == "immutable":
        return Block("guard.immutable", lang, params)
    if mode == "frozen":
        return None if op == CREATE else Block("guard.frozen", lang, params)
    if mode == "append-only":
        if op == OVERWRITE:
            return Block("guard.append_only_overwrite", lang, params)
        if op == DELETE:
            return Block("guard.append_only_delete", lang, params)
        return None
    if mode == "living" and op in (OVERWRITE, DELETE) and abs_path.is_file():
        status = frontmatter.status(abs_path)
        if status and status in m.frozen_statuses:
            return Block("guard.living_frozen_status", lang, {**params, "status": status})
    return None


def _resolve_op(raw_op: str, abs_path: Path) -> str:
    exists = abs_path.exists()
    if raw_op == bashwrites.OVERWRITE:
        return OVERWRITE if exists else CREATE
    if raw_op == bashwrites.CREATE_OR_EDIT:
        return EDIT if exists else CREATE
    return DELETE


def _judge_path(ctx: _Ctx, abs_path: Path, raw_op: str) -> Block | None:
    root = find_root(abs_path)
    if root is None:
        return None  # not inside a strata project
    rel = rel_to(abs_path, root)
    if rel is None:
        return None
    fold = case_blind(str(root))
    if _under(rel, MANIFEST_REL, fold):
        return None  # the way out is never locked
    m = ctx.manifest(root)
    if isinstance(m, ManifestError):
        if _under(rel, MANIFEST_DIR, fold):
            return None
        return Block("guard.manifest_invalid", _language_hint(root), {"problems": "; ".join(m.problems[:5])})
    return _judge_file(m, abs_path, rel, _resolve_op(raw_op, abs_path), fold)


def _judge_tree(ctx: _Ctx, abs_path: Path, cwd: Path) -> Block | None:
    """A recursive delete or a move of ``abs_path``."""
    if not abs_path.exists() and not abs_path.is_symlink():
        return None
    if abs_path.is_symlink() or abs_path.is_file():
        return _judge_path(ctx, abs_path, bashwrites.DELETE)
    # Deleting a directory that holds a project root deletes the manifest and everything it protects.
    cwd_root = find_root(cwd)
    if cwd_root is not None and (cwd_root == abs_path or abs_path in cwd_root.parents):
        m = ctx.manifest(cwd_root)
        lang = m.project.language if isinstance(m, Manifest) else _language_hint(cwd_root)
        return Block("guard.tree_holds_protected", lang, {"path": str(abs_path), "example": MANIFEST_REL})
    own = _judge_path(ctx, abs_path, bashwrites.DELETE)
    if own is not None:
        return own
    count = 0
    for dirpath, dirnames, filenames in os.walk(abs_path):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for name in filenames:
            count += 1
            if count > TREE_FILE_LIMIT:
                return _too_large(ctx, abs_path)
            f = Path(dirpath) / name
            b = _judge_path(ctx, f, bashwrites.DELETE)
            if b is not None:
                root = find_root(f)
                example = rel_to(f, root) if root else str(f)
                return Block("guard.tree_holds_protected", b.lang, {"path": str(abs_path), "example": example})
    return None


def _too_large(ctx: _Ctx, abs_path: Path) -> Block | None:
    root = find_root(abs_path)
    if root is None:
        return None
    m = ctx.manifest(root)
    if isinstance(m, ManifestError):
        return Block("guard.manifest_invalid", _language_hint(root), {"problems": "; ".join(m.problems[:5])})
    rel = rel_to(abs_path, root) or "."
    fold = case_blind(str(root))
    for zone in _zones(m):
        if rel == "." or _under(zone, rel, fold) or _under(rel, zone, fold):
            return Block("guard.tree_too_large", m.project.language, {"path": rel})
    return None


def _zones(m: Manifest) -> list[str]:
    """Literal path prefixes that hold something protected."""
    zones = [pattern_prefix(p) for layer in m.layers if layer.mode != "scratch" for p in layer.paths]
    zones += [t.path for t in m.tracks if not t.open]
    return sorted({z for z in zones if z})


def judge_unparsable(text: str, cwd: Path) -> Block | None:
    """Fallback when a command cannot be understood: block only if it names a protected zone."""
    root = find_root(cwd)
    if root is None:
        return None
    try:
        m = load(root)
    except (ManifestError, OSError):
        return Block("guard.manifest_invalid", _language_hint(root), {"problems": "unreadable"})
    fold = case_blind(str(root))
    hay = text.lower() if fold else text
    for zone in _zones(m):
        if (zone.lower() if fold else zone) in hay:
            return Block("guard.unparsable", m.project.language, {"zone": zone})
    return None


def judge(tool_name: str, tool_input: dict, cwd: str | os.PathLike[str], env: dict[str, str] | None = None) -> Block | None:
    """Return a :class:`Block` when the call must be refused, otherwise ``None``."""
    env = os.environ if env is None else env
    if env.get(BYPASS_ENV) == "1":
        return None
    ctx = _Ctx()
    cwd_path = Path(cwd)

    key = WRITE_TOOLS_PATH_KEY.get(tool_name)
    if key is not None:
        raw = tool_input.get(key)
        if not isinstance(raw, str) or not raw:
            return None
        op = bashwrites.OVERWRITE if tool_name == "Write" else bashwrites.CREATE_OR_EDIT
        return _judge_path(ctx, normalize(raw, cwd_path), op)

    if tool_name == "Bash":
        command = tool_input.get("command")
        if not isinstance(command, str) or not command.strip():
            return None
        try:
            found = bashwrites.targets(command, str(cwd_path))
        except bashwrites.Unparsable:
            return judge_unparsable(command, cwd_path)
        for t in found:
            abs_path = normalize(t.path, t.cwd)
            if t.op == bashwrites.DELETE_TREE:
                b = _judge_tree(ctx, abs_path, cwd_path)
            elif t.op == bashwrites.OVERWRITE and t.sources and abs_path.is_dir():
                b = None
                for src in t.sources:
                    b = _judge_path(ctx, abs_path / Path(src).name, t.op)
                    if b:
                        break
            else:
                b = _judge_path(ctx, abs_path, t.op)
            if b is not None:
                return b
        return None

    return None


def judge_payload(payload: dict, env: dict[str, str] | None = None) -> Block | None:
    """Entry for a PreToolUse hook payload (already parsed JSON)."""
    if (os.environ if env is None else env).get(BYPASS_ENV) == "1":
        return None
    tool = payload.get("tool_name")
    tool_input = payload.get("tool_input")
    cwd = payload.get("cwd")
    if not isinstance(tool, str) or not isinstance(tool_input, dict):
        return None
    if not isinstance(cwd, str) or not cwd:
        cwd = (env or os.environ).get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        return judge(tool, tool_input, cwd, env)
    except Exception:  # noqa: BLE001 — a judging failure falls back to the zone check, never to "allow all"
        return judge_unparsable(json.dumps(tool_input, ensure_ascii=False), Path(cwd))
