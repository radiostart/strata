"""Repository conventions that keep strata generic (design § 8 and § 9)."""

from __future__ import annotations

import ast
import json
import re
import unittest

from helpers import FIXTURE_NAMES, FIXTURES, REPO

from strata import manifest as schema
from strata.manifest import load
from strata.messages import I18N_DIR, catalog
from strata.paths import glob_match, pattern_prefix

CODE_DIRS = ("strata", "hooks", "scripts")
CODE_SUFFIXES = {".py", ".sh", ".json"}


def reserved_words() -> set[str]:
    """strata's own schema vocabulary. A fixture word that collides with these cannot be tested."""
    words = set(schema._TOP) | set(schema.LAYER_MODES) | set(schema.LANGUAGES)
    for table in (schema._PROJECT, schema._TRACK, schema._LAYER, schema._DOCTYPE, schema._TAG, schema._CYCLE,
                  schema._ROLE, schema._REGISTER):
        words |= set(table)
    return words


def behavioural_strings(path) -> str:
    """String literals that can change behaviour: Python constants except docstrings, JSON values."""
    text = path.read_text("utf-8")
    if path.suffix == ".json":
        out: list[str] = []

        def walk(node, key=None):
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, k)
            elif isinstance(node, list):
                for v in node:
                    walk(v, key)
            elif isinstance(node, str) and key != "description":
                out.append(node)

        walk(json.loads(text))
        return "\n".join(out)
    if path.suffix == ".py":
        tree = ast.parse(text)
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
                first = node.body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                    docstrings.add(id(first.value))
        return "\n".join(n.value for n in ast.walk(tree)
                         if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings)
    # Shell: quoted strings on non-comment lines (keywords such as `done` are not vocabulary).
    lines = [line for line in text.splitlines() if not line.lstrip().startswith("#")]
    return "\n".join(re.findall(r'"[^"]*"|\'[^\']*\'', "\n".join(lines)))


def code_files():
    for d in CODE_DIRS:
        for p in sorted((REPO / d).rglob("*")):
            if p.is_file() and p.suffix in CODE_SUFFIXES and "__pycache__" not in p.parts:
                yield p


def fixture_vocabulary() -> set[str]:
    """Project-specific words a generic implementation must never contain."""
    words: set[str] = set()
    for name in FIXTURE_NAMES:
        m = load(FIXTURES / name)
        words.add(m.project.name)
        for t in m.tracks:
            words.add(t.id)
            words.update(seg for seg in t.path.split("/") if seg)
        for layer in m.layers:
            for p in layer.paths:
                words.update(seg for seg in pattern_prefix(p).split("/") if seg)
                words.update(seg for seg in p.split("/") if seg and not any(c in seg for c in "*?["))
        words.update(m.frozen_statuses)
        for c in m.cycles:
            words.add(c.prefix)
            words.update(c.steps)
        for d in m.document_types:
            words.update(d.sections)
    return {w for w in words if len(w) >= 2} - reserved_words()


class NoVocabularyInCode(unittest.TestCase):
    def test_fixture_words_do_not_appear_in_code(self):
        vocab = fixture_vocabulary()
        hits = []
        for f in code_files():
            text = behavioural_strings(f)
            for w in vocab:
                if re.search(rf"(?<![\w-]){re.escape(w)}(?![\w-])", text):
                    hits.append(f"{f.relative_to(REPO)}: '{w}'")
        self.assertEqual(hits, [], "project vocabulary leaked into code:\n" + "\n".join(hits))


class MessageCatalogs(unittest.TestCase):
    def test_every_language_has_the_same_keys(self):
        langs = sorted(p.stem for p in I18N_DIR.glob("*.toml"))
        self.assertIn("en", langs)
        en = set(catalog("en"))
        for lang in langs:
            with self.subTest(lang=lang):
                self.assertEqual(set(catalog(lang)), en)

    def test_placeholders_match(self):
        en = catalog("en")
        for lang in (p.stem for p in I18N_DIR.glob("*.toml")):
            for key, text in catalog(lang).items():
                with self.subTest(lang=lang, key=key):
                    self.assertEqual(set(re.findall(r"{(\w+)}", text)), set(re.findall(r"{(\w+)}", en[key])))

    def test_code_uses_only_known_keys(self):
        en = set(catalog("en"))
        used = set()
        for f in code_files():
            used.update(re.findall(r'["\'](guard\.[a-z_]+)["\']', f.read_text("utf-8")))
        self.assertEqual(used - en, set())


class Globs(unittest.TestCase):
    def test_glob_semantics(self):
        cases = [
            ("docs/**", "docs", True),
            ("docs/**", "docs/a/b.md", True),
            ("docs/**", "docsx/a.md", False),
            ("t/*/plan/**", "t/a/plan/x.md", True),
            ("t/*/plan/**", "t/a/b/plan/x.md", False),
            ("**/keep/*.md", "keep/x.md", True),
            ("**/keep/*.md", "a/b/keep/x.md", True),
            ("a/?.md", "a/b.md", True),
            ("a/?.md", "a/bc.md", False),
            ("원문/**", "원문/발표.md", True),
        ]
        for pattern, rel, expected in cases:
            with self.subTest(pattern=pattern, rel=rel):
                self.assertIs(glob_match(pattern, rel), expected)

    def test_fold(self):
        self.assertTrue(glob_match("docs/**", "DOCS/A.md", fold=True))
        self.assertFalse(glob_match("docs/**", "DOCS/A.md", fold=False))


if __name__ == "__main__":
    unittest.main()
