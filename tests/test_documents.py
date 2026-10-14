"""Validation, records and registers, run against every fixture."""

from __future__ import annotations

import datetime as dt
import re
import unittest

from helpers import Project
from test_guard import FixtureCase, per_fixture

from strata import guard, mdtable, records, registers, validate
from strata.manifest import load


def decision_text(m, *, drop_section: str | None = None, drop_key: str | None = None, tag_line: str = "") -> str:
    dtype = next(d for d in m.document_types if d.id == "decision")
    fm = {"type": "decision", "id": "D-001", "title": "t", "date": "2026-10-15", "status": "draft"}
    lines = ["---"] + [f"{k}: {v}" for k, v in fm.items() if k != drop_key] + ["---", "", "# title", ""]
    for i, s in enumerate(dtype.sections, 1):
        if s != drop_section:
            lines += [f"## {i}. {s}", "", "text", ""]
    if tag_line:
        lines += [tag_line, ""]
    return "\n".join(lines)


class Validation(FixtureCase):
    @per_fixture
    def test_valid_document(self, p):
        m = load(p.root)
        self.assertEqual(validate.check_text(m, "d.md", decision_text(m)), [])

    @per_fixture
    def test_missing_section_and_key(self, p):
        m = load(p.root)
        section = next(d for d in m.document_types if d.id == "decision").sections[0]
        keys = [x.key for x in validate.check_text(m, "d.md", decision_text(m, drop_section=section))]
        self.assertEqual(keys, ["validate.missing_section"])
        keys = [x.key for x in validate.check_text(m, "d.md", decision_text(m, drop_key="status"))]
        self.assertEqual(keys, ["validate.missing_key"])

    @per_fixture
    def test_heading_number_and_case_are_ignored(self, p):
        m = load(p.root)
        section = next(d for d in m.document_types if d.id == "decision").sections[0]
        text = decision_text(m).replace(f"## 1. {section}", f"## 1) {section.upper()}")
        self.assertEqual(validate.check_text(m, "d.md", text), [])

    @per_fixture
    def test_evidence_tag_needs_reference_on_same_line(self, p):
        m = load(p.root)
        tag = next(t for t in m.evidence_tags if t.reference)
        bad = validate.check_text(m, "d.md", decision_text(m, tag_line=f"Orders grew {tag.label}"))
        self.assertEqual([x.key for x in bad], ["validate.tag_without_reference"])
        good = validate.check_text(m, "d.md", decision_text(m, tag_line=f"Orders grew {tag.label} P-12"))
        self.assertEqual(good, [])

    @per_fixture
    def test_code_fences_are_ignored(self, p):
        m = load(p.root)
        tag = next(t for t in m.evidence_tags if t.reference)
        text = decision_text(m, tag_line=f"```\n{tag.label} no reference here\n## Fake\n```")
        self.assertEqual(validate.check_text(m, "d.md", text), [])

    @per_fixture
    def test_untyped_and_unknown_types(self, p):
        m = load(p.root)
        self.assertEqual(validate.check_text(m, "n.md", "# just notes\n"), [])
        self.assertEqual(validate.check_text(m, "n.md", "---\ntitle: x\n---\n"), [])
        w = validate.check_text(m, "n.md", "---\ntype: mystery\n---\n")
        self.assertEqual([(x.key, x.severity) for x in w], [("validate.unknown_type", validate.WARNING)])
        e = validate.check_text(m, "n.md", "---\ntype: decision\n")
        self.assertEqual([x.key for x in e], ["validate.frontmatter_unterminated"])

    @per_fixture
    def test_project_walk_skips_hidden_folders(self, p):
        m = load(p.root)
        p.write("append_only", decision_text(m))
        (p.root / ".hidden").mkdir()
        (p.root / ".hidden" / "x.md").write_text("---\ntype: mystery\n---\n", "utf-8")
        count, problems = validate.check_project(m)
        self.assertEqual(problems, [])
        self.assertGreaterEqual(count, 1)


class Records(FixtureCase):
    @per_fixture
    def test_append_creates_month_file_with_header(self, p):
        when = dt.datetime(2026, 10, 15, 9, 30, tzinfo=dt.timezone.utc)
        path, rec = records.append(p.root, load(p.root).project.language, "check", "a|b", "me", "ok",
                                   note="multi\nline", now=when)
        self.assertEqual(path.name, "2026-10.md")
        records.append(p.root, "en", "check", "t2", "me", "ok", now=when)
        rows = records.read_month(path)
        self.assertEqual([r.target for r in rows], ["a|b", "t2"])
        self.assertEqual(rows[0].note, "multi line")
        self.assertEqual(path.read_text("utf-8").count("\n# "), 0)  # one header only

    @per_fixture
    def test_limits(self, p):
        with self.assertRaises(records.RecordError) as cm:
            records.append(p.root, "en", "", "t", "me", "ok")
        self.assertEqual(cm.exception.key, "record.empty")
        with self.assertRaises(records.RecordError) as cm:
            records.append(p.root, "en", "k", "t", "me", "ok", note="x" * (records.MAX_CELL + 1))
        self.assertEqual(cm.exception.key, "record.too_long")

    @per_fixture
    def test_records_folder_is_append_only_for_the_guard(self, p):
        path, _ = records.append(p.root, "en", "k", "t", "me", "ok")
        rel = path.relative_to(p.root).as_posix()
        self.assertEqual(guard.judge("Write", {"file_path": str(path)}, p.root, {}).key,
                         "guard.append_only_overwrite")
        self.assertIsNone(guard.judge("Bash", {"command": f"echo row >> {rel}"}, p.root, {}))
        self.assertEqual(guard.judge("Bash", {"command": f"rm {rel}"}, p.root, {}).key, "guard.append_only_delete")


class Registers(FixtureCase):
    def make(self, p: Project):
        m = load(p.root)
        reg = m.registers[0]
        path = p.root / reg.path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(registers.header(m.project.language, reg), "utf-8")
        return m, reg, path

    @per_fixture
    def test_ids_come_from_the_first_column_only(self, p):
        m, reg, path = self.make(p)
        first = registers.add(m, reg.id, f"mentions {reg.prefix}-99 in the title")
        self.assertEqual(first.id, f"{reg.prefix}-1")
        with path.open("a", encoding="utf-8") as f:
            f.write(mdtable.render([f"{reg.prefix}-7", "2026-01-01", "open", "imported", "", ""]) + "\n")
        self.assertEqual(registers.add(m, reg.id, "next").id, f"{reg.prefix}-8")

    @per_fixture
    def test_missing_file_is_an_error_not_a_restart(self, p):
        m = load(p.root)
        with self.assertRaises(registers.RegisterError) as cm:
            registers.add(m, m.registers[0].id, "x")
        self.assertEqual(cm.exception.key, "register.missing_file")

    @per_fixture
    def test_close_changes_only_that_line(self, p):
        m, reg, path = self.make(p)
        a = registers.add(m, reg.id, "first")
        registers.add(m, reg.id, "second")
        before = path.read_text("utf-8").splitlines()
        registers.close(m, a.id, "done in a new decision")
        after = path.read_text("utf-8").splitlines()
        changed = [i for i, (x, y) in enumerate(zip(before, after)) if x != y]
        self.assertEqual(len(changed), 1)
        self.assertIn(registers.CLOSED, after[changed[0]])
        with self.assertRaises(registers.RegisterError) as cm:
            registers.close(m, a.id, "again")
        self.assertEqual(cm.exception.key, "register.not_open")

    @per_fixture
    def test_unknown_register_and_id(self, p):
        m, reg, _ = self.make(p)
        with self.assertRaises(registers.RegisterError) as cm:
            registers.add(m, "nope", "x")
        self.assertEqual(cm.exception.key, "register.unknown")
        with self.assertRaises(registers.RegisterError) as cm:
            registers.close(m, f"{reg.prefix}-42", "x")
        self.assertEqual(cm.exception.key, "register.no_such_id")
        with self.assertRaises(registers.RegisterError) as cm:
            registers.close(m, "ZZ-1", "x")
        self.assertEqual(cm.exception.key, "register.unknown_id")


class Tables(unittest.TestCase):
    def test_round_trip(self):
        row = mdtable.render(["a|b", " spaced  out ", "c\\|d"])
        self.assertEqual(mdtable.split(row), ["a|b", "spaced out", "c|d"])
        self.assertIsNone(mdtable.split("| --- | :---: |"))
        self.assertIsNone(mdtable.split("not a row"))
        self.assertTrue(re.fullmatch(r"\| .* \|", row))


if __name__ == "__main__":
    unittest.main()
