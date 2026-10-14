"""The ``strata`` command line.

Exit codes: 0 success · 1 problems found (validate) or a refused operation · 2 usage or manifest error.
Every user-facing line comes from the message catalog in the project's language.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from . import __version__, records, registers, scaffold, status, validate
from .manifest import Manifest, ManifestError, load
from .messages import DEFAULT_LANG, text
from .paths import find_root

EXIT_OK, EXIT_PROBLEMS, EXIT_USAGE = 0, 1, 2


class CliError(Exception):
    def __init__(self, key: str, code: int = EXIT_USAGE, lang: str = DEFAULT_LANG, **params: object):
        self.key, self.code, self.lang, self.params = key, code, lang, params
        super().__init__(key)


def _out(line: str = "") -> None:
    print(line)


def _project(args) -> Manifest:
    start = Path(args.root).resolve() if args.root else Path(os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    root = start if (start / ".strata" / "strata.toml").is_file() else find_root(start)
    if root is None:
        raise CliError("cli.no_manifest", path=str(start))
    try:
        return load(root)
    except ManifestError as e:
        raise CliError("cli.manifest_invalid", problems="\n  ".join(e.problems)) from e


def _actor(args) -> str:
    return getattr(args, "actor", None) or os.environ.get("STRATA_ACTOR") or "-"


# ── init ─────────────────────────────────────────────────────────────────────────────────────────────
def cmd_init(args) -> int:
    root = Path(args.root or os.getcwd()).resolve()
    lang = args.lang or DEFAULT_LANG
    name = args.name or scaffold.default_name(root)
    try:
        created = scaffold.init(root, lang, name, actor=_actor(args))
    except scaffold.ScaffoldError as e:
        raise CliError(e.key, lang=lang, **e.params) from e
    if args.format == "json":
        _out(json.dumps({"root": str(root), "name": name, "language": lang,
                         "created": [p.as_posix() for p in created]}, ensure_ascii=False, indent=2))
        return EXIT_OK
    _out(text("init.created", lang, count=len(created), name=name, language=lang, root=str(root)))
    for p in created:
        _out(f"  {p.as_posix()}")
    _out(text("init.next", lang))
    return EXIT_OK


# ── validate ─────────────────────────────────────────────────────────────────────────────────────────
def cmd_validate(args) -> int:
    m = _project(args)
    lang = m.project.language
    targets = [Path(p).resolve() for p in args.paths] or None
    count, problems = validate.check_project(m, targets)
    errors = [p for p in problems if p.severity == validate.ERROR]
    if args.format == "json":
        _out(json.dumps({"files": count, "problems": [
            {"path": p.path, "line": p.line, "severity": p.severity, "code": p.key,
             "message": text(p.key, lang, **p.param_dict())} for p in problems]}, ensure_ascii=False, indent=2))
    else:
        for p in problems:
            where = f"{p.path}:{p.line}" if p.line else p.path
            _out(f"{where}: {text('validate.severity.' + p.severity, lang)}: {text(p.key, lang, **p.param_dict())}")
        if problems:
            _out(text("validate.summary", lang, files=count, errors=len(errors), warnings=len(problems) - len(errors)))
        else:
            _out(text("validate.clean", lang, files=count))
    return EXIT_PROBLEMS if errors else EXIT_OK


# ── status ───────────────────────────────────────────────────────────────────────────────────────────
def cmd_status(args) -> int:
    m = _project(args)
    s = status.summary(m)
    if args.format == "json":
        _out(json.dumps(s, ensure_ascii=False, indent=2))
        return EXIT_OK
    lang = m.project.language
    _out(text("status.header", lang, project=s["project"], language=s["language"]))
    tracks = " · ".join(text("status.track_open" if t["open"] else "status.track_closed", lang, id=t["id"])
                        for t in s["tracks"])
    _out(text("status.tracks", lang, tracks=tracks or "-"))
    _out(text("status.layers", lang))
    for x in s["layers"]:
        _out("  " + text("status.layer_line", lang, id=x["id"], mode=x["mode"], files=x["files"]))
    docs = " · ".join(f"{k} {v}" for k, v in s["documents"].items()) or "-"
    _out(text("status.documents", lang, documents=docs, untyped=s["untyped_markdown"]))
    for d in sorted(set(s["documents"]) - set(s["declared_types"])):
        _out("  " + text("status.undeclared_type", lang, type=d))
    _out(text("status.registers", lang))
    for r in s["registers"]:
        key = "status.register_missing" if r["missing"] else "status.register_line"
        _out("  " + text(key, lang, id=r["id"], open=r["open"], total=r["total"], path=r["path"]))
    if s["recent_records"]:
        _out(text("status.records", lang))
        for r in s["recent_records"]:
            _out("  " + text("status.record_line", lang, **r))
    else:
        _out(text("status.no_records", lang))
    return EXIT_OK


# ── record ───────────────────────────────────────────────────────────────────────────────────────────
def cmd_record_add(args) -> int:
    m = _project(args)
    lang = m.project.language
    try:
        path, rec = records.append(m.root, lang, args.kind, args.target, _actor(args), args.result,
                                   args.evidence or "", args.note or "")
    except records.RecordError as e:
        raise CliError(e.key, EXIT_PROBLEMS, lang, **e.params) from e
    _out(text("record.added", lang, path=path.relative_to(m.root).as_posix(), time=rec.time))
    return EXIT_OK


def cmd_record_list(args) -> int:
    m = _project(args)
    rows = records.recent(m.root, args.limit)
    if args.format == "json":
        _out(json.dumps([r.__dict__ for r in rows], ensure_ascii=False, indent=2))
    elif not rows:
        _out(text("record.none", m.project.language))
    else:
        for r in rows:
            _out(text("status.record_line", m.project.language, **r.__dict__))
    return EXIT_OK


# ── register ─────────────────────────────────────────────────────────────────────────────────────────
def cmd_register_add(args) -> int:
    m = _project(args)
    lang = m.project.language
    try:
        e = registers.add(m, args.register, args.title, args.source or "")
    except registers.RegisterError as err:
        raise CliError(err.key, EXIT_PROBLEMS, lang, **err.params) from err
    _out(text("register.added", lang, id=e.id, register=args.register))
    return EXIT_OK


def cmd_register_close(args) -> int:
    m = _project(args)
    lang = m.project.language
    try:
        e = registers.close(m, args.id, args.resolution)
    except registers.RegisterError as err:
        raise CliError(err.key, EXIT_PROBLEMS, lang, **err.params) from err
    _out(text("register.closed", lang, id=e.id))
    return EXIT_OK


def cmd_register_list(args) -> int:
    m = _project(args)
    lang = m.project.language
    regs = [registers.find(m, args.register)] if args.register else list(m.registers)
    out = []
    try:
        for reg in regs:
            for e in registers.entries(m, reg):
                if args.open and e.status != registers.OPEN:
                    continue
                out.append({"register": reg.id, **{k: v for k, v in e.__dict__.items() if k != "line"}})
    except registers.RegisterError as err:
        raise CliError(err.key, EXIT_PROBLEMS, lang, **err.params) from err
    if args.format == "json":
        _out(json.dumps(out, ensure_ascii=False, indent=2))
    elif not out:
        _out(text("register.none", lang))
    else:
        for e in out:
            _out(text("register.line", lang, **e))
    return EXIT_OK


# ── parser ───────────────────────────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", help="project root (default: nearest folder with .strata/strata.toml)")
    common.add_argument("--format", choices=("text", "json"), default="text")

    ap = argparse.ArgumentParser(prog="strata", description="strata — layered, approved documents.")
    ap.add_argument("--version", action="version", version=f"strata {__version__}")
    sub = ap.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", parents=[common], help="create a project skeleton")
    p.add_argument("--lang", choices=scaffold.languages() or None, help="template language (default: en)")
    p.add_argument("--name", help="project id (default: derived from the folder name)")
    p.add_argument("--actor")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("validate", parents=[common], help="check documents against the manifest")
    p.add_argument("paths", nargs="*", help="files or folders (default: the whole project)")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("status", parents=[common], help="summarise tracks, layers, documents, registers")
    p.set_defaults(func=cmd_status)

    rec = sub.add_parser("record", help="append-only run records").add_subparsers(dest="action", required=True)
    p = rec.add_parser("add", parents=[common], help="append one record")
    p.add_argument("--kind", required=True)
    p.add_argument("--target", required=True)
    p.add_argument("--result", required=True)
    p.add_argument("--actor")
    p.add_argument("--evidence")
    p.add_argument("--note")
    p.set_defaults(func=cmd_record_add)
    p = rec.add_parser("list", parents=[common], help="show recent records")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_record_list)

    reg = sub.add_parser("register", help="registers of upward reports and issues").add_subparsers(
        dest="action", required=True)
    p = reg.add_parser("add", parents=[common], help="add an entry with the next free ID")
    p.add_argument("--register", required=True)
    p.add_argument("--title", required=True)
    p.add_argument("--source")
    p.set_defaults(func=cmd_register_add)
    p = reg.add_parser("close", parents=[common], help="close an open entry")
    p.add_argument("--id", required=True)
    p.add_argument("--resolution", required=True)
    p.set_defaults(func=cmd_register_close)
    p = reg.add_parser("list", parents=[common], help="list entries")
    p.add_argument("--register")
    p.add_argument("--open", action="store_true", help="only open entries")
    p.set_defaults(func=cmd_register_list)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except CliError as e:
        print(text(e.key, e.lang, **e.params), file=sys.stderr)
        return e.code
