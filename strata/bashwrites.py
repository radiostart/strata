"""Conservative extraction of write targets from a Bash command.

What is understood:

- command separators ``;`` ``&&`` ``||`` ``|`` ``&`` and newlines
- ``cd DIR`` with a literal directory, which moves the working directory for later commands
- redirections ``>`` ``>>`` ``>|`` ``&>`` ``N>`` ``N>>``
- ``rm`` ``rmdir`` ``unlink`` ``mv`` ``cp`` ``tee`` ``sed -i`` ``truncate`` ``touch`` ``dd of=``
  ``ln`` (destination), ``git rm``, ``git mv``, ``find PATH ... -delete`` / ``-exec rm``
- here-document bodies are skipped, so their text is never read as commands

What is **not** understood, by design: code passed to interpreters (``python3 -c``, ``node -e``),
``eval``, ``sh -c '...'``, command substitution, variables whose value is unknown. A word containing
``$`` or a backtick is not treated as a path. Guards prevent accidents; they are not a security
boundary.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

# Operations, from weakest to strongest.
CREATE_OR_EDIT = "write"      # create if missing, partial change if present (append, sed -i, touch)
OVERWRITE = "overwrite"       # create if missing, full replacement if present
DELETE = "delete"
DELETE_TREE = "delete-tree"   # recursive removal of whatever the path holds

SEPARATORS = {";", ";;", "&&", "||", "|", "&", "|&", "(", ")", "{", "}"}
REDIRECT_RE = re.compile(r"^(\d*|&)(>>|>\||>)$")
FD_DUP_RE = re.compile(r"^\d*(?:>&|<&|>&-|<&-)$")
HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1")
PREFIX_WORDS = {"sudo", "command", "exec", "time", "nice", "nohup", "env", "builtin", "then", "do", "else", "!"}
ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
MAX_INPUT = 64 * 1024


@dataclass(frozen=True)
class Target:
    path: str
    op: str
    cwd: str  # working directory the path is relative to
    sources: tuple[str, ...] = ()  # for cp/mv/ln: when the destination is a directory, files land as dest/<name>


class Unparsable(Exception):
    """The command could not be tokenised safely."""


def _strip_heredocs(cmd: str) -> str:
    """Remove here-document bodies, keeping the command lines that introduce them."""
    lines = cmd.split("\n")
    out: list[str] = []
    pending: list[str] = []
    for line in lines:
        if pending:
            if line.strip() == pending[0]:
                pending.pop(0)
            continue
        out.append(line)
        pending.extend(m.group(2) for m in HEREDOC_RE.finditer(line))
    return "\n".join(out)


def _newlines_to_separators(cmd: str) -> str:
    """Replace newlines outside quotes with ``;`` (backslash-newline continues the line)."""
    out: list[str] = []
    quote = ""
    i = 0
    while i < len(cmd):
        c = cmd[i]
        if quote:
            if c == "\\" and quote == '"' and i + 1 < len(cmd):
                out.append(cmd[i : i + 2])
                i += 2
                continue
            if c == quote:
                quote = ""
        elif c in "'\"":
            quote = c
        elif c == "\\" and i + 1 < len(cmd):
            if cmd[i + 1] == "\n":
                i += 2
                continue
            out.append(cmd[i : i + 2])
            i += 2
            continue
        elif c == "\n":
            out.append(" ; ")
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out)


def _tokens(cmd: str) -> list[str]:
    lex = shlex.shlex(_newlines_to_separators(cmd), posix=True, punctuation_chars=";&|<>()")
    lex.whitespace_split = True
    lex.commenters = "#"
    out: list[str] = []
    try:
        for tok in lex:
            out.append(tok)
    except ValueError as e:  # unbalanced quotes
        raise Unparsable(str(e)) from e
    return out


def _literal(word: str) -> bool:
    return bool(word) and "$" not in word and "`" not in word and not word.startswith("-")


def _split_commands(tokens: list[str]) -> list[list[str]]:
    cmds: list[list[str]] = [[]]
    for tok in tokens:
        if tok in SEPARATORS or (set(tok) <= set(";&|()") and tok):
            cmds.append([])
        else:
            cmds[-1].append(tok)
    return [c for c in cmds if c]


def _merge_redirects(words: list[str]) -> list[str]:
    """Join tokens that shlex split apart: ``2`` ``>`` -> ``2>``, ``&`` ``>`` -> ``&>``."""
    out: list[str] = []
    for w in words:
        if out and w in (">", ">>", ">|", ">&", "<&") and (out[-1].isdigit() or out[-1] == "&"):
            out[-1] = out[-1] + w
        elif out and w == "|" and out[-1] == ">":
            out[-1] = ">|"
        else:
            out.append(w)
    return out


def _operands(args: list[str]) -> list[str]:
    """Non-option arguments, honouring ``--``."""
    out, opts_done = [], False
    for a in args:
        if not opts_done and a == "--":
            opts_done = True
            continue
        if not opts_done and a.startswith("-") and a != "-":
            continue
        out.append(a)
    return out


def _command_targets(words: list[str], cwd: str) -> list[Target]:
    found: list[Target] = []
    rest: list[str] = []
    i = 0
    while i < len(words):
        w = words[i]
        if FD_DUP_RE.match(w):
            i += 2
            continue
        m = REDIRECT_RE.match(w)
        if m:
            target = words[i + 1] if i + 1 < len(words) else ""
            i += 2
            if target.startswith("&") or target in ("/dev/null", "/dev/stdout", "/dev/stderr", "/dev/tty"):
                continue
            if _literal(target):
                found.append(Target(target, CREATE_OR_EDIT if m.group(2) == ">>" else OVERWRITE, cwd))
            continue
        if w in ("<", "<<", "<<<", "<<-") or w.startswith("<"):
            i += 2
            continue
        rest.append(w)
        i += 1

    # strip assignments and harmless prefixes
    while rest and (ASSIGN_RE.match(rest[0]) or rest[0] in PREFIX_WORDS):
        rest.pop(0)
    if not rest:
        return found
    name, args = rest[0].rsplit("/", 1)[-1], rest[1:]

    def add(paths: list[str], op: str, sources: list[str] | None = None) -> None:
        src = tuple(x for x in (sources or []) if _literal(x))
        found.extend(Target(p, op, cwd, src) for p in paths if _literal(p))

    if name in ("rm", "unlink", "rmdir"):
        recursive = any(a.startswith("-") and not a.startswith("--") and ("r" in a or "R" in a) for a in args) \
            or "--recursive" in args
        add(_operands(args), DELETE_TREE if recursive or name == "rmdir" else DELETE)
    elif name == "mv":
        ops = _operands(args)
        if len(ops) >= 2:
            add(ops[:-1], DELETE_TREE)
            add(ops[-1:], OVERWRITE, ops[:-1])
    elif name in ("cp", "ln", "install"):
        ops = _operands(args)
        if len(ops) >= 2:
            add(ops[-1:], OVERWRITE, ops[:-1])
    elif name == "tee":
        append = any(a in ("-a", "--append") for a in args)
        add(_operands(args), CREATE_OR_EDIT if append else OVERWRITE)
    elif name == "sed":
        if any(a == "-i" or a.startswith("-i") or a == "--in-place" or a.startswith("--in-place=") for a in args):
            ops = _operands(args)
            has_script_opt = any(a in ("-e", "-f") or a.startswith("--expression") for a in args)
            add(ops if has_script_opt else ops[1:], CREATE_OR_EDIT)
    elif name == "truncate":
        ops, skip = [], False
        for a in args:
            if skip:
                skip = False
                continue
            if a in ("-s", "--size", "-r", "--reference"):
                skip = True
                continue
            if not a.startswith("-"):
                ops.append(a)
        add(ops, OVERWRITE)
    elif name == "touch":
        add(_operands(args), CREATE_OR_EDIT)
    elif name == "dd":
        add([a[3:] for a in args if a.startswith("of=")], OVERWRITE)
    elif name == "git" and args:
        sub, sub_args = args[0], args[1:]
        if sub == "rm":
            recursive = "-r" in sub_args
            add(_operands(sub_args), DELETE_TREE if recursive else DELETE)
        elif sub == "mv":
            ops = _operands(sub_args)
            if len(ops) >= 2:
                add(ops[:-1], DELETE_TREE)
                add(ops[-1:], OVERWRITE, ops[:-1])
    elif name == "find" and ("-delete" in args or ("-exec" in args and "rm" in args)):
        roots = []
        for a in args:
            if a.startswith("-") or a in ("(", ")", "!"):
                break
            roots.append(a)
        add(roots or ["."], DELETE_TREE)
    return found


def targets(command: str, cwd: str) -> list[Target]:
    """Write targets of ``command`` with the working directory each one is relative to.

    Raises :class:`Unparsable` when the command is too large or cannot be tokenised.
    """
    if len(command) > MAX_INPUT:
        raise Unparsable("command too large")
    tokens = _tokens(_strip_heredocs(command))
    out: list[Target] = []
    for words in _split_commands(tokens):
        words = _merge_redirects(words)
        head = [w for w in words if not ASSIGN_RE.match(w)]
        if head and head[0] in ("cd", "pushd"):
            dest = head[1] if len(head) > 1 else "~"
            if _literal(dest) or dest == "~":
                cwd = _join(cwd, dest)
            continue
        out.extend(_command_targets(words, cwd))
    return out


def _join(cwd: str, dest: str) -> str:
    import os

    dest = os.path.expanduser(dest)
    return os.path.normpath(dest if os.path.isabs(dest) else os.path.join(cwd, dest))
