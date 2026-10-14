"""Manifest schema: every fixture loads, and each kind of mistake is reported."""

from __future__ import annotations

import tomllib
import unittest
from pathlib import Path

from helpers import FIXTURE_NAMES, FIXTURES

from strata.manifest import ManifestError, load, parse


def base() -> dict:
    return {
        "project": {"name": "t", "language": "en", "schema": 1},
        "tracks": [{"id": "one", "path": "t/one", "open": True}],
        "layers": [{"id": "keep", "mode": "frozen", "paths": ["t/*/keep/**"]}],
        "roles": [{"id": "owner"}],
        "cycles": [{"id": "c", "prefix": "C", "track": "one", "folder": "cy", "steps": ["a", "b"],
                    "retry_to": ["a"], "approver": "owner"}],
    }


class Fixtures(unittest.TestCase):
    def test_every_fixture_loads(self):
        for name in FIXTURE_NAMES:
            with self.subTest(fixture=name):
                m = load(FIXTURES / name)
                self.assertEqual(m.project.name, name)
                self.assertTrue(m.tracks and m.layers)


class Problems(unittest.TestCase):
    def problems(self, data: dict) -> list[str]:
        with self.assertRaises(ManifestError) as cm:
            parse(data, Path("/x"), Path("/x/.strata/strata.toml"))
        return cm.exception.problems

    def assertProblem(self, data: dict, fragment: str) -> None:
        found = self.problems(data)
        self.assertTrue(any(fragment in p for p in found), f"{fragment!r} not in {found}")

    def test_valid_base(self):
        m = parse(base(), Path("/x"), Path("/x/.strata/strata.toml"))
        self.assertEqual(m.cycles[0].max_rounds, 3)  # default
        self.assertFalse(parse({**base(), "tracks": [{"id": "one", "path": "t/one"}]}, Path("/x"), Path("/x/m")).tracks[0].open)

    def test_unknown_keys(self):
        d = base(); d["surprise"] = 1
        self.assertProblem(d, "unknown top-level key 'surprise'")
        d = base(); d["layers"][0]["note"] = "prose"
        self.assertProblem(d, "unknown key 'note'")

    def test_missing_and_wrong_types(self):
        d = base(); del d["project"]["name"]
        self.assertProblem(d, "missing required key 'name'")
        d = base(); d["tracks"][0]["open"] = "yes"
        self.assertProblem(d, "tracks[0].open: expected bool")
        d = base(); d["layers"][0]["paths"] = "t/**"
        self.assertProblem(d, "expected a list of strings")

    def test_enums_and_ids(self):
        d = base(); d["layers"][0]["mode"] = "readonly"
        self.assertProblem(d, "layers[0].mode")
        d = base(); d["project"]["language"] = "fr"
        self.assertProblem(d, "project.language")
        d = base(); d["tracks"][0]["id"] = "One Track"
        self.assertProblem(d, "must be lowercase")
        d = base(); d["cycles"][0]["prefix"] = "rf"
        self.assertProblem(d, "prefix")

    def test_references(self):
        d = base(); d["cycles"][0]["track"] = "nope"
        self.assertProblem(d, "unknown track 'nope'")
        d = base(); d["cycles"][0]["approver"] = "nobody"
        self.assertProblem(d, "unknown role 'nobody'")
        d = base(); d["cycles"][0]["retry_to"] = ["z"]
        self.assertProblem(d, "'z' is not one of its steps")

    def test_duplicates_and_paths(self):
        d = base(); d["tracks"].append({"id": "one", "path": "t/two"})
        self.assertProblem(d, "duplicate id 'one'")
        d = base(); d["tracks"][0]["path"] = "../escape"
        self.assertProblem(d, "relative path inside the project")
        d = base(); d["layers"][0]["paths"] = ["/abs/**"]
        self.assertProblem(d, "relative glob")

    def test_schema_version(self):
        d = base(); d["project"]["schema"] = 99
        self.assertProblem(d, "unsupported version 99")

    def test_invalid_toml(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".strata").mkdir()
            (root / ".strata" / "strata.toml").write_text("[project\n", "utf-8")
            with self.assertRaises(ManifestError) as cm:
                load(root)
            self.assertIn("not valid TOML", cm.exception.problems[0])


class AllProblemsAtOnce(unittest.TestCase):
    def test_reports_every_problem(self):
        d = base()
        d["surprise"] = 1
        d["layers"][0]["mode"] = "bad"
        d["cycles"][0]["track"] = "nope"
        with self.assertRaises(ManifestError) as cm:
            parse(d, Path("/x"), Path("/x/m"))
        self.assertGreaterEqual(len(cm.exception.problems), 3)


if __name__ == "__main__":
    unittest.main()
