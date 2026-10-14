"""User-facing message catalog.

Messages live in ``strata/i18n/<lang>.toml`` as ``key = "text with {placeholders}"``. A key missing in
the selected language falls back to English. A key missing everywhere returns the key itself, so a
typo is visible instead of silent.
"""

from __future__ import annotations

import tomllib
from functools import lru_cache
from pathlib import Path

I18N_DIR = Path(__file__).resolve().parent / "i18n"
DEFAULT_LANG = "en"


@lru_cache(maxsize=8)
def catalog(lang: str) -> dict[str, str]:
    path = I18N_DIR / f"{lang}.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    flat: dict[str, str] = {}

    def walk(prefix: str, node: object) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                walk(f"{prefix}.{k}" if prefix else k, v)
        elif isinstance(node, str):
            flat[prefix] = node

    walk("", data)
    return flat


def text(key: str, lang: str = DEFAULT_LANG, **params: object) -> str:
    template = catalog(lang).get(key) or catalog(DEFAULT_LANG).get(key) or key
    try:
        return template.format(**params)
    except (KeyError, IndexError, ValueError):
        return template
