# strata — design

> **Status: draft 0.1 · updated 2026-10-14.** This document is the source of truth for what strata is and how it is built.
> The Korean translation lives at [`docs/ko/design.md`](../ko/design.md) and is checked for staleness by
> `tools/i18n_check.py`.

## 1. What strata is

strata is a Claude Code plugin that turns a repository into an **operating system for layered,
approved documents produced by AI agents** — for example a business plan that constrains a product
spec, which in turn constrains a development plan.

It does four things:

1. **Protects layers by path.** Every document lives in a layer (current, history, evidence, …) and
   each layer has a write mode. Hooks block writes that would break a layer's mode.
2. **Runs bounded cycles.** A cycle is a multi-agent run (author → critic → arbiter, for example) that
   produces a *proposal* inside its own folder. Step order, round limits and question budgets are
   counted by a state machine, not by the agents.
3. **Keeps people at the gates.** A proposal leaves its cycle folder only after the person whose turn
   it is answers, and the verbatim answer is stored as a file. No answer file, no approval.
4. **Leaves an append-only record.** Decisions, run records and upward reports are append-only, so
   "why is it like this?" always has an answer.

### Non-goals

- **Not a security boundary.** Hooks prevent accidents. The lines that cannot be crossed are human
  acts: answering a gate, opening a conversation, merging a pull request.
- **Not a shared-working-tree coordinator.** strata assumes one worktree per conversation and
  pull-request merges. Coordination across conversations is a later, optional module (§ 10, M5).
- **No domain knowledge in code.** Track names, document types, section headings, roles and evidence
  tags are data in the project manifest. Code must never contain a project's vocabulary.
- **Not a code generator.** strata governs documents and plans. Implementation work can be tracked by
  a cycle, but strata does not write application code.

## 2. Origin and what changed

strata is a clean-room rewrite of the operating layer of **onway**, a document-first product
project that ran three tracks (business planning → product planning → development) with 15 skills,
17 agents and roughly 60k lines of tooling between 2026-09 and 2026-10.

The **principles** carried over unchanged (§ 3). The **code** did not, for reasons measured in onway
itself:

| Lesson from onway | strata rule |
| --- | --- |
| Track folder names were hard-coded in 23 tool files; renaming a track made 17 of 18 loader roles fail and an ID allocator return a silently wrong value. | All structure comes from the manifest. A lint test fails if a fixture's track names appear in code (§ 9). |
| The shared library looked up configuration by **Korean section headings** of a Markdown file. | The manifest is TOML with English keys. Human-language strings (headings, labels) are manifest *values*. |
| Only 14 of 32 configuration entries were actually read by tools; the rest was prose. | Every manifest key has a schema entry and a reader, or it is rejected as unknown. |
| Three cycle types (refine, spec, devplan) each had their own state machine with the same shape. | One cycle engine; cycle types are declared in the manifest (§ 6). |
| Lane and lock guards existed because several conversations shared one working tree; the project later moved to per-conversation worktrees. | Worktree + pull request is the assumed model. No lane or lock guards in the core. |
| Coordination tooling assumed one operator machine (launchd, local inbox). | Coordination is out of the core. If added, it uses Claude Code's native session features. |

## 3. Principles

These are the rules strata exists to enforce. Each one is a sentence first and an implementation
second.

- **P1 — Three layers, protected by path.** *Current* documents are living and edited through cycles.
  *History* (decisions) is append-only. *Evidence* (research, reviews) is frozen once written. Hooks
  enforce the mode of each layer.
- **P2 — The path is the gate.** A cycle may only write inside its own folder. Promotion out of the
  folder happens only after an approval backed by a verbatim answer file.
- **P3 — Authors do not review themselves.** Author, critic and arbiter are different agents. An agent
  receives only the files its role is allowed to read.
- **P4 — Machines count the limits.** Step transitions, rounds and question budgets are counted by
  the cycle engine. Agents are never trusted to stop themselves.
- **P5 — Evidence is tagged.** Key claims carry an evidence tag declared in the manifest. Numbers and
  legal text are never invented.
- **P6 — Lower layers report upward, never overwrite.** A downstream cycle that needs an upstream
  change files an entry in a register. The upstream owner decides in a new decision record.
- **P7 — Verifiers reproduce, not trust.** A verification step re-creates the evidence (for example,
  a test that fails before the change) instead of reading the author's report.
- **P8 — Roles record, then restrict.** Declared roles first produce a shadow ledger of out-of-role
  writes. Blocking is a later, explicit choice.
- **P9 — The system measures itself.** Dead exceptions fail. Portability is a test. The operating
  rules can be evaluated and improved like any other artifact.

## 4. Concepts

| Term | Meaning |
| --- | --- |
| **manifest** | `.strata/strata.toml` in the user's repository. Declares everything project-specific. |
| **track** | A work stage with its own folder, such as `business` or `product`. Tracks are opened and closed by people. |
| **layer** | A set of paths with one write mode (§ 5). Layers cut across tracks. |
| **document type** | Required front-matter keys and required sections for a kind of document. |
| **cycle** | A bounded multi-agent run that produces a proposal in its own folder. Has a type, steps, rounds and a state file. |
| **step** | One stage of a cycle, performed by one agent role. |
| **gate** | A point where a person must answer. The answer is stored verbatim in the cycle's `inputs/`. |
| **role** | A human role (for example `planner`, `reviewer`, `owner`). Roles own gates and have write scopes. |
| **register** | An append-only list of upward reports or open issues, with its own ID prefix. |
| **record** | The append-only run log (`.strata/records/YYYY-MM.md`). |
| **evidence tag** | A label such as `[measured]` or `[assumed]`, declared in the manifest with its reference rule. |

## 5. Layers and boundaries

### 5.1 Layer modes

| Mode | Create | Edit (partial) | Overwrite (full Write) | Delete |
| --- | --- | --- | --- | --- |
| `immutable` | no | no | no | no |
| `frozen` | yes | no | no | no |
| `append-only` | yes | yes¹ | no | no |
| `living` | yes | yes | only if not in a frozen status² | only if not in a frozen status² |
| `scratch` | yes | yes | yes | yes |

¹ Partial edits are allowed so that a record can be marked `superseded`. The cycle engine and
  validators check that the body did not change.
² A living document whose front-matter `status` is in `frozen_statuses` (for example `accepted`) cannot
  be overwritten or deleted. It can still be edited.

### 5.2 Boundaries and how each is enforced

| Boundary | What it protects | Enforcement | Kind |
| --- | --- | --- | --- |
| **Layer** | The mode of every layer (§ 5.1) | `layer_guard` hook | Blocks |
| **Track** | Closed tracks are not written | `layer_guard` hook | Blocks |
| **Cycle** | Unapproved proposals stay in their cycle folder | Loader's `writable_paths` + cycle engine | Contract |
| **Role** | Out-of-role writes are visible | `role_shadow` hook | Records only |

The cycle boundary is a contract on purpose: a hook cannot tell a subagent from its caller, and the
same conversation can edit state files. The approval itself — a person answering — is the line that
cannot be crossed.

### 5.3 Guard behaviour rules

These come directly from onway's guard regressions and are tested from day one:

- **Inert without a manifest.** In a repository with no `.strata/strata.toml` every hook exits 0.
- **Fail closed, but never lock the way out.** If the manifest exists but cannot be read, writes to
  protected zones are blocked, while `.strata/**` stays writable so the manifest can be fixed.
- **Outside the project is not judged.** Paths outside the repository root pass.
- **Relative paths are resolved against the tool's working directory**, including `cd` inside a Bash
  command.
- **Case-insensitive file systems are handled.** `Docs/x.md` and `docs/x.md` are the same file on
  macOS and Windows.
- **Bash is judged conservatively.** Redirections and common write commands (`rm`, `mv`, `cp`, `tee`,
  `sed -i`, `truncate`, `touch`, `dd`, `git rm`, `git mv`, `find -delete`) are parsed. Here-document
  bodies are skipped. Code passed to interpreters, `eval` and words containing `$` are not parsed, and
  the documentation says so.
- **Recursive deletes look inside.** `rm -r` or `mv` of a directory is blocked when any file under it
  would be blocked, and deleting a directory that contains the project root is always blocked.
- **When a command cannot be understood, block only what it names.** If tokenising fails, the command
  is blocked only when its text contains a protected zone (a layer path prefix or a closed track).
- **Bypass is explicit.** `STRATA_GUARD_BYPASS=1` in the environment that launched Claude Code. Every
  block message says how to bypass and when it is appropriate.

## 6. The manifest

The manifest is TOML (read with Python's standard `tomllib`). Keys are English; values may be in any
language. Unknown keys are errors.

```toml
[project]
name = "acme"
language = "en"            # message language for hooks and tools: "en" | "ko"
schema = 1

[[tracks]]
id = "business"
path = "tracks/business"
open = true

[[tracks]]
id = "product"
path = "tracks/product"
open = false

[[layers]]
id = "evidence"
mode = "frozen"
paths = ["tracks/*/archive/research/**", "tracks/*/archive/reviews/**"]

[[layers]]
id = "history"
mode = "append-only"
paths = ["tracks/*/decisions/**"]

[[layers]]
id = "current"
mode = "living"
paths = ["tracks/*/plan/**", "tracks/*/specs/**"]

[[layers]]
id = "source"
mode = "immutable"
paths = ["docs/originals/**"]

[documents]
frozen_statuses = ["accepted", "done", "superseded"]

[[documents.types]]
id = "decision"
frontmatter = ["type", "id", "title", "date", "status"]
sections = ["Context", "Decision", "Consequences", "Review conditions"]

[[evidence.tags]]
tag = "measured"
label = "[measured]"
reference = "P-\\d+"

[[cycles]]
id = "refine"
prefix = "RF"
track = "business"
folder = "archive/refinements"
steps = ["intake", "analysis", "plan", "critique", "verdict"]
max_rounds = 3
asks_per_round = 1
asks_total = 2
retry_to = ["analysis", "plan"]
approver = "owner"

[[roles]]
id = "owner"
writes = ["**"]
gates = ["refine.approve"]

[[registers]]
id = "upward"
prefix = "UP"
path = "tracks/business/registers/upward.md"
```

**Whether a track is open is a manifest field.** Opening a track is a human decision, so it should
show up as a reviewed diff. A separate state file would add one more thing that can be deleted or
corrupted — in onway, a broken state file once let writes through every track guard.

Cycle state is **not** in the manifest. It lives in each cycle's folder and is changed only through
the `strata cycle` command, which writes a record line (M2).

Layers are matched **in declaration order; the first match wins.** Paths that match no layer are not
judged. The manifest file itself (`.strata/strata.toml`) is always writable.

## 7. Plugin layout

```
.claude-plugin/
  plugin.json            plugin manifest
  marketplace.json       this repository is also its own marketplace
hooks/
  hooks.json             hook registrations
  run.sh                 POSIX launcher: finds Python 3.11+, then runs a hook module
strata/                  Python package (standard library only)
  manifest.py            load and validate .strata/strata.toml
  paths.py               glob matching, case folding, root resolution
  frontmatter.py         minimal front-matter reader
  bashwrites.py          conservative write-target extraction from Bash
  guard.py               layer and track decisions
  messages.py            message catalog lookup (en, ko)
  i18n/en.toml, ko.toml  user-facing strings
scripts/
  hook.py                hook entry, called by hooks/run.sh
  strata                 command line entry (`strata validate`, `strata cycle …`)   — M1
skills/                  slash commands, written in English                         — M3
agents/                  subagents, written in English                              — M3
templates/               project scaffolds per language (en, ko)                    — M1
tests/                   unittest suites and fixtures
tools/                   repository maintenance tools (i18n_check, …)
docs/en/, docs/ko/       documentation, English source and Korean translation
```

Runtime requirement: **Python 3.11 or later** (for `tomllib`), standard library only.

Packaging facts this layout relies on (Claude Code plugin reference, checked 2026-10-14):

- `.claude-plugin/marketplace.json` lists the plugin with `"source": "."`, so the repository root is the
  plugin. Install with `claude plugin marketplace add radiostart/strata` and
  `claude plugin install strata@strata`.
- **No top-level `bin/`.** A plugin `bin/` is put on the Bash tool's `PATH`, but it also stops claude.ai
  and Cowork from installing the plugin. The command line lives in `scripts/` and skills call it by
  its full path.
- `${CLAUDE_PLUGIN_ROOT}` is substituted in skill, command and agent Markdown and in `hooks.json`. It is
  **not** an environment variable inside the Bash tool, so skills write the substituted path into
  each command.
- **`python3` is not guaranteed to exist.** Hooks run through `hooks/run.sh`, which looks for Python
  3.11+. In a project without a manifest it exits 0 silently. In a project with a manifest and no
  usable Python it blocks file-writing tools with a message that names the fix (install Python or set
  the bypass). Bash commands get a warning instead of a block, because blocking every command would
  also block installing Python.
- A PreToolUse hook blocks by exiting with code 2; its stderr is shown to Claude.
- `CLAUDE.md` at the repository root is for people and agents developing strata. Claude Code does not
  load it as context for plugin users, and `claude plugin validate` reports that as a warning, which is
  expected.
- Plugin skills are invoked as `/strata:<skill>` and agents as `strata:<agent>`.

## 8. Language policy

| Artifact | Language |
| --- | --- |
| Code, identifiers, comments, commit messages | English |
| Skills and agents (`SKILL.md`, `agents/*.md`) | English. The model answers in the user's language. |
| Hook and tool messages | Message catalog. `project.language` selects `en` or `ko`; missing keys fall back to `en`. |
| Documentation | English source in `docs/en/`. Korean translation in `docs/ko/`, whose first line is a marker naming the source file and its hash. `tools/i18n_check.py` fails when a translation is missing or older than its source. |
| README | `README.md` (English) and `README.ko.md` (Korean), same rule as documentation. |
| Project scaffolds | One template set per language. Headings and labels are manifest values, so parsers never depend on a language. |

## 9. Testing rules

- Standard library `unittest`; `python3 -m unittest discover -s tests`.
- **Two fixtures, always.** Every guard and engine test runs against at least two fixture projects
  with different track names and different languages. A behaviour that only works for one is a bug.
- **No vocabulary in code.** A lint test scans the behavioural string literals in `strata/`, `hooks/`
  and `scripts/` (not docstrings or comments) for every track id, folder name, status, step and heading
  used by the fixtures. Any hit fails. Fixture words must not collide with strata's own schema keys.
- **Guards are tested for latency.** A hook that takes longer than a set budget fails the suite.
- **Translations are tested.** `tools/i18n_check.py` runs in the suite.

## 10. Roadmap

| Milestone | Scope | Done when |
| --- | --- | --- |
| **M0 — Foundation** | Manifest loader and schema, layer and track guard, message catalog, i18n check, repository conventions | Guard tests pass on two fixtures; plugin installs from this repository |
| **M1 — Records and validation** | `strata validate` (front-matter, sections, evidence tags), append-only record, registers, `strata init` scaffold | A scaffolded project validates clean in both languages |
| **M2 — Cycle engine** | Generic state machine from `[[cycles]]`: steps, rounds, asks, verdicts, answer-file approval, promotion | A cycle can stop on every hard-stop reason; approval without an answer file is refused |
| **M3 — Agents and skills** | Generic author, critic, arbiter and verifier agents; loader that returns `files_to_read` and `writable_paths` per role | One end-to-end cycle runs on a fixture project |
| **M4 — Roles and gates** | Role declaration, shadow ledger, gate ownership | Out-of-role writes appear in the ledger; gate answers name the role |
| **M5 — Coordination (optional)** | Work-item adapter contract and a coordinator built on native Claude Code sessions | Defined only after a second real project uses M0–M4 |

## 11. Open questions

| # | Question | Default if unanswered |
| --- | --- | --- |
| Q1 | Is Python 3.11+ an acceptable runtime requirement? | Yes |
| Q2 | Should onway itself migrate onto strata as the first user? | Not before M3 |
| Q3 | Should strata ship an "onway-like" preset (three tracks, three cycle types)? | Yes, at M3, as a template — not as code |
