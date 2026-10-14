"""Guard decisions, run against every fixture (design § 5 and § 9)."""

from __future__ import annotations

import functools
import json
import os
import subprocess
import time
import unittest
from pathlib import Path

from helpers import FIXTURE_NAMES, REPO, Project

from strata import guard
from strata.manifest import load
from strata.paths import case_blind

NO_ENV: dict[str, str] = {}


def per_fixture(test):
    """Run ``test(self, project)`` once per fixture, each inside its own subTest."""

    @functools.wraps(test)
    def run(self):
        for name in FIXTURE_NAMES:
            proj = Project(name)
            try:
                with self.subTest(fixture=name):
                    test(self, proj)
            finally:
                proj.close()

    return run


class FixtureCase(unittest.TestCase):

    def write_call(self, proj: Project, path: Path, tool: str = "Write") -> guard.Block | None:
        key = "notebook_path" if tool == "NotebookEdit" else "file_path"
        return guard.judge(tool, {key: str(path)}, proj.root, NO_ENV)

    def bash(self, proj: Project, command: str, cwd: Path | None = None) -> guard.Block | None:
        return guard.judge("Bash", {"command": command}, cwd or proj.root, NO_ENV)


class LayerModes(FixtureCase):
    @per_fixture
    def test_immutable_blocks_everything(self, p):
        self.assertEqual(self.write_call(p, p.path("immutable")).key, "guard.immutable")
        p.write("immutable")
        self.assertEqual(self.write_call(p, p.path("immutable"), "Edit").key, "guard.immutable")
        self.assertEqual(self.bash(p, f"rm '{p.paths['immutable']}'").key, "guard.immutable")

    @per_fixture
    def test_frozen_allows_create_only(self, p):
        self.assertIsNone(self.write_call(p, p.path("frozen")))
        p.write("frozen")
        self.assertEqual(self.write_call(p, p.path("frozen")).key, "guard.frozen")
        self.assertEqual(self.write_call(p, p.path("frozen"), "Edit").key, "guard.frozen")
        self.assertEqual(self.bash(p, f"rm '{p.paths['frozen']}'").key, "guard.frozen")
        self.assertEqual(self.bash(p, f"echo more >> '{p.paths['frozen']}'").key, "guard.frozen")

    @per_fixture
    def test_append_only(self, p):
        self.assertIsNone(self.write_call(p, p.path("append_only")))
        p.write("append_only")
        self.assertIsNone(self.write_call(p, p.path("append_only"), "Edit"))
        self.assertIsNone(self.bash(p, f"echo row >> '{p.paths['append_only']}'"))
        self.assertEqual(self.write_call(p, p.path("append_only")).key, "guard.append_only_overwrite")
        self.assertEqual(self.bash(p, f"echo x > '{p.paths['append_only']}'").key, "guard.append_only_overwrite")
        self.assertEqual(self.bash(p, f"rm '{p.paths['append_only']}'").key, "guard.append_only_delete")

    @per_fixture
    def test_living_respects_frozen_status(self, p):
        p.write("living", status=p.paths["draft_status"])
        self.assertIsNone(self.write_call(p, p.path("living")))
        self.assertIsNone(self.bash(p, f"rm '{p.paths['living']}'"))
        p.write("living", status=p.paths["frozen_status"])
        self.assertIsNone(self.write_call(p, p.path("living"), "Edit"))
        self.assertEqual(self.write_call(p, p.path("living")).key, "guard.living_frozen_status")
        self.assertEqual(self.bash(p, f"rm '{p.paths['living']}'").key, "guard.living_frozen_status")

    @per_fixture
    def test_scratch_and_unmatched_are_free(self, p):
        for key in ("scratch", "free"):
            p.write(key)
            self.assertIsNone(self.write_call(p, p.path(key)))
            self.assertIsNone(self.bash(p, f"rm -rf '{p.paths[key]}'"))

    @per_fixture
    def test_first_matching_layer_wins(self, p):
        # Every fixture declares its scratch layer inside a frozen one; the scratch file must stay free.
        p.write("scratch")
        self.assertIsNone(self.write_call(p, p.path("scratch")))


class Tracks(FixtureCase):
    @per_fixture
    def test_closed_track_blocks(self, p):
        b = self.write_call(p, p.path("closed_track"))
        self.assertEqual(b.key, "guard.closed_track")
        self.assertEqual(self.bash(p, f"touch '{p.paths['closed_track']}'").key, "guard.closed_track")


class TreeOperations(FixtureCase):
    @per_fixture
    def test_recursive_delete_of_dir_holding_frozen_file(self, p):
        p.write("frozen")
        # The track folder is in no layer, so the guard must look inside it.
        b = self.bash(p, f"rm -rf '{p.paths['track_dir']}'")
        self.assertEqual(b.key, "guard.tree_holds_protected")
        self.assertEqual(self.bash(p, f"mv '{p.paths['track_dir']}' /tmp/elsewhere").key,
                         "guard.tree_holds_protected")
        # The frozen folder itself matches its layer and is blocked by that layer.
        self.assertEqual(self.bash(p, f"rm -rf '{p.paths['frozen_dir']}'").key, "guard.frozen")

    @per_fixture
    def test_deleting_the_project_root(self, p):
        sub = p.root / "deep" / "er"
        sub.mkdir(parents=True)
        self.assertEqual(self.bash(p, "rm -rf ../..", cwd=sub).key, "guard.tree_holds_protected")

    @per_fixture
    def test_copy_into_frozen_directory(self, p):
        existing = p.write("frozen")
        p.write("free")
        dest_dir = os.path.relpath(existing.parent, p.root)
        src = p.paths["free"]
        # A new name inside a frozen directory is a create: allowed.
        self.assertIsNone(self.bash(p, f"cp '{src}' '{dest_dir}/'"))
        # The same name as an existing frozen file is an overwrite: blocked.
        (p.root / src).rename(p.root / Path(src).with_name(existing.name))
        renamed = str(Path(src).with_name(existing.name))
        self.assertEqual(self.bash(p, f"cp '{renamed}' '{dest_dir}/'").key, "guard.frozen")


class Resolution(FixtureCase):
    @per_fixture
    def test_relative_paths_follow_cd(self, p):
        p.write("frozen")
        parent, name = str(Path(p.paths["frozen"]).parent), Path(p.paths["frozen"]).name
        self.assertEqual(self.bash(p, f"cd '{parent}' && rm '{name}'").key, "guard.frozen")
        self.assertEqual(self.write_call(p, Path(p.paths["frozen"])).key, "guard.frozen")

    @per_fixture
    def test_heredoc_body_is_not_a_command(self, p):
        p.write("frozen")
        cmd = f"cat > notes.md <<'EOF'\nrm '{p.paths['frozen']}'\nEOF"
        self.assertIsNone(self.bash(p, cmd))

    @per_fixture
    def test_outside_project_passes(self, p):
        outside = p.root.parent / "outside.md"
        self.assertIsNone(self.write_call(p, outside))
        self.assertIsNone(self.bash(p, f"rm -rf '{p.root.parent / 'other'}'"))

    @per_fixture
    def test_case_insensitive_file_system(self, p):
        if not case_blind(str(p.root)):
            self.skipTest("file system is case-sensitive")
        p.write("frozen")
        shouting = p.root / p.paths["frozen"].upper()
        self.assertEqual(self.write_call(p, shouting).key, "guard.frozen")


class FailClosed(FixtureCase):
    @per_fixture
    def test_no_manifest_is_inert(self, p):
        (p.root / ".strata" / "strata.toml").unlink()
        self.assertIsNone(self.write_call(p, p.path("immutable")))
        self.assertIsNone(self.bash(p, "rm -rf ."))

    @per_fixture
    def test_broken_manifest_blocks_but_keeps_the_way_out(self, p):
        manifest = p.root / ".strata" / "strata.toml"
        manifest.write_text(manifest.read_text("utf-8") + "\n[surprise]\nkey = 1\n", "utf-8")
        self.assertEqual(self.write_call(p, p.path("free")).key, "guard.manifest_invalid")
        self.assertIsNone(self.write_call(p, manifest))
        self.assertIsNone(self.write_call(p, p.root / ".strata" / "notes.md"))

    @per_fixture
    def test_manifest_itself_is_always_writable(self, p):
        self.assertIsNone(self.write_call(p, p.root / ".strata" / "strata.toml"))

    @per_fixture
    def test_bypass(self, p):
        env = {"STRATA_GUARD_BYPASS": "1"}
        self.assertIsNone(guard.judge("Write", {"file_path": str(p.path("immutable"))}, p.root, env))

    @per_fixture
    def test_unparsable_command_blocks_only_protected_zones(self, p):
        zone = p.paths["immutable"]
        self.assertIsNotNone(self.bash(p, f"echo 'unbalanced {zone}"))
        self.assertIsNone(self.bash(p, "echo 'unbalanced elsewhere"))


class Latency(FixtureCase):
    BUDGET = 0.2  # seconds per decision

    @per_fixture
    def test_decisions_are_fast(self, p):
        p.write("frozen")
        for _ in range(200):
            p.write(f"bulk/f{_}.md")
        start = time.perf_counter()
        self.bash(p, "rm -rf bulk && echo done > out.md")
        self.write_call(p, p.path("frozen"))
        self.assertLess(time.perf_counter() - start, self.BUDGET * 2)


class HookEndToEnd(FixtureCase):
    def run_hook(self, proj: Project, payload: dict, env_extra: dict[str, str] | None = None):
        env = {k: v for k, v in os.environ.items() if k != "STRATA_GUARD_BYPASS"}
        env.update({"CLAUDE_PROJECT_DIR": str(proj.root), "CLAUDE_PLUGIN_ROOT": str(REPO)})
        env.update(env_extra or {})
        return subprocess.run(["sh", str(REPO / "hooks" / "run.sh"), "layer-guard"], input=json.dumps(payload),
                              capture_output=True, text=True, env=env, timeout=20)

    EXPECTED_PREFIX = {"en": "strata blocked this write", "ko": "strata 가 이 쓰기를 막았습니다"}

    @per_fixture
    def test_block_exit_code_and_language(self, p):
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(p.path("immutable"))},
                   "cwd": str(p.root), "hook_event_name": "PreToolUse"}
        r = self.run_hook(p, payload)
        self.assertEqual(r.returncode, 2, r.stderr)
        lang = load(p.root).project.language
        self.assertIn(self.EXPECTED_PREFIX[lang], r.stderr)
        self.assertIn("STRATA_GUARD_BYPASS=1", r.stderr)

    @per_fixture
    def test_allow_is_silent(self, p):
        payload = {"tool_name": "Write", "tool_input": {"file_path": str(p.path("free"))}, "cwd": str(p.root)}
        r = self.run_hook(p, payload)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    @per_fixture
    def test_garbage_payload_does_not_open_protected_zones(self, p):
        r = self.run_hook(p, {"tool_name": "Write"} | {"x": "y"})
        self.assertEqual(r.returncode, 0)
        raw_env = {"CLAUDE_PROJECT_DIR": str(p.root), "CLAUDE_PLUGIN_ROOT": str(REPO), "PATH": os.environ["PATH"]}
        r = subprocess.run(["sh", str(REPO / "hooks" / "run.sh"), "layer-guard"],
                           input='{"tool_name": "Bash", "tool_input": {"command": "rm ' + p.paths["immutable"],
                           capture_output=True, text=True, env=raw_env, cwd=p.root, timeout=20)
        self.assertEqual(r.returncode, 2, r.stderr)


if __name__ == "__main__":
    unittest.main()
