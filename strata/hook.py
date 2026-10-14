"""Hook entry points. ``python3 scripts/hook.py <name>`` reads the hook payload from stdin.

Exit codes follow Claude Code's PreToolUse contract: 0 lets the call through, 2 blocks it and shows
stderr to Claude.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import BYPASS_ENV, guard
from .messages import text

MAX_PAYLOAD = 1024 * 1024
HOOKS = ("layer-guard",)


def render(block: guard.Block) -> str:
    lang = block.lang
    lines = [f"{text('guard.prefix', lang)}: {text(block.key, lang, **block.params)}"]
    if block.key == "guard.manifest_invalid" and block.params.get("problems"):
        lines.append(text("guard.manifest_problems", lang, problems=block.params["problems"]))
    lines.append(text("guard.bypass", lang, env=BYPASS_ENV))
    return "\n".join(lines)


def layer_guard(raw: str, env: dict[str, str]) -> guard.Block | None:
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("payload is not an object")
    except ValueError:
        if env.get(BYPASS_ENV) == "1":
            return None
        cwd = Path(env.get("CLAUDE_PROJECT_DIR") or os.getcwd())
        return guard.judge_unparsable(raw, cwd)
    return guard.judge_payload(payload, env)


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in HOOKS:
        print(f"strata hook: expected one of {', '.join(HOOKS)}", file=sys.stderr)
        return 1
    raw = sys.stdin.read(MAX_PAYLOAD + 1)
    env = dict(os.environ)
    if len(raw) > MAX_PAYLOAD:
        block = guard.judge_unparsable(raw[:MAX_PAYLOAD], Path(env.get("CLAUDE_PROJECT_DIR") or os.getcwd()))
    else:
        block = layer_guard(raw, env)
    if block is None:
        return 0
    print(render(block), file=sys.stderr)
    return 2
