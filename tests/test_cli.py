"""The command line, end to end, in every template language."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import REPO

from strata import scaffold
from strata.manifest import load

CLI = REPO / "scripts" / "strata"


def run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_PROJECT_DIR", "STRATA_ACTOR")}
    return subprocess.run([sys.executable, str(CLI), *args], cwd=cwd, capture_output=True, text=True,
                          env=env, timeout=60)


class Templates(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="strata-cli-")
        self.base = Path(os.path.realpath(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_every_template_initialises_validates_and_reports(self):
        langs = scaffold.languages()
        self.assertGreaterEqual(set(langs), {"en", "ko"})
        for lang in langs:
            with self.subTest(lang=lang):
                root = self.base / f"proj-{lang}"
                root.mkdir()
                r = run(root, "init", "--lang", lang, "--format", "json")
                self.assertEqual(r.returncode, 0, r.stderr)
                created = json.loads(r.stdout)["created"]
                self.assertIn(".strata/strata.toml", created)
                m = load(root)
                self.assertEqual(m.project.language, lang)
                for reg in m.registers:
                    self.assertTrue((root / reg.path).is_file())

                r = run(root, "validate")
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

                r = run(root, "status", "--format", "json")
                s = json.loads(r.stdout)
                self.assertEqual(s["project"], f"proj-{lang}")
                self.assertEqual(s["recent_records"][0]["kind"], "init")
                self.assertFalse(any(x["missing"] for x in s["registers"]))

                # human output is in the project's language and never shows a raw key
                for args in (("status",), ("validate",), ("register", "list")):
                    out = run(root, *args).stdout
                    self.assertNotRegex(out, r"\b(status|validate|register|record|init|cli)\.[a-z_]+\b")

    def test_init_never_overwrites(self):
        root = self.base / "twice"
        root.mkdir()
        self.assertEqual(run(root, "init").returncode, 0)
        before = (root / ".strata" / "strata.toml").read_text("utf-8")
        r = run(root, "init")
        self.assertEqual(r.returncode, 2)
        self.assertEqual((root / ".strata" / "strata.toml").read_text("utf-8"), before)

    def test_init_rejects_bad_name(self):
        root = self.base / "bad"
        root.mkdir()
        r = run(root, "init", "--name", "Bad Name")
        self.assertEqual(r.returncode, 2)
        self.assertFalse((root / ".strata").exists())

    def test_template_folders_are_not_strata_projects(self):
        # A template must not look like a project, or the guard would judge maintainers' edits to it.
        for lang in scaffold.languages():
            self.assertFalse((scaffold.TEMPLATES / lang / ".strata").exists())


class Commands(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="strata-cmd-")
        self.root = Path(os.path.realpath(self._tmp.name)) / "proj"
        self.root.mkdir()
        assert run(self.root, "init", "--lang", "en").returncode == 0
        self.reg = load(self.root).registers[0]

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_project(self):
        empty = self.root.parent / "empty"
        empty.mkdir()
        r = run(empty, "status")
        self.assertEqual(r.returncode, 2)
        self.assertIn("strata init", r.stderr)

    def test_validate_exit_codes(self):
        bad = self.root / "bad.md"
        bad.write_text("---\ntype: decision\nid: D-9\ntitle: x\ndate: 2026-10-15\nstatus: draft\n---\n", "utf-8")
        r = run(self.root, "validate", "--format", "json")
        self.assertEqual(r.returncode, 1)
        codes = {p["code"] for p in json.loads(r.stdout)["problems"]}
        self.assertEqual(codes, {"validate.missing_section"})
        self.assertEqual(run(self.root, "validate", "--format", "json", str(self.root / "work")).returncode, 0)

    def test_register_and_record_flow(self):
        r = run(self.root, "register", "add", "--register", self.reg.id, "--title", "first")
        self.assertEqual(r.returncode, 0, r.stderr)
        r = run(self.root, "register", "close", "--id", f"{self.reg.prefix}-1", "--resolution", "decided")
        self.assertEqual(r.returncode, 0, r.stderr)
        listed = json.loads(run(self.root, "register", "list", "--open", "--format", "json").stdout)
        self.assertEqual(listed, [])
        r = run(self.root, "record", "add", "--kind", "check", "--target", "work", "--result", "ok",
                "--actor", "tester")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = json.loads(run(self.root, "record", "list", "--format", "json").stdout)
        self.assertEqual([x["kind"] for x in rows], ["init", "check"])

    def test_invalid_manifest_is_reported(self):
        manifest = self.root / ".strata" / "strata.toml"
        manifest.write_text(manifest.read_text("utf-8") + "\nsurprise = 1\n", "utf-8")
        r = run(self.root, "status")
        self.assertEqual(r.returncode, 2)
        self.assertIn("surprise", r.stderr)


if __name__ == "__main__":
    unittest.main()
