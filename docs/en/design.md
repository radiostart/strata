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
  pull-request merges. Coordination across conversations is a later, optional module (§ 12, M6).
- **No domain knowledge in code.** Track names, document types, section headings, roles and evidence
  tags are data in the project manifest. Code must never contain a project's vocabulary.
- **Not a code generator.** strata governs documents and plans. Implementation work can be tracked by
  a cycle, but strata does not write application code.

## 2. Origin and what changed

strata is a clean-room rewrite of an operating layer first built for an earlier, document-first
product project. That project ran three tracks (business planning → product planning → development)
with 15 skills, 17 agents and roughly 60k lines of tooling between 2026-09 and 2026-10.

The **principles** carried over unchanged (§ 3). The **code** did not, for reasons measured in the
earlier project itself:

| Lesson from the earlier project | strata rule |
| --- | --- |
| Track folder names were hard-coded in 23 tool files; renaming a track made 17 of 18 loader roles fail and an ID allocator return a silently wrong value. | All structure comes from the manifest. A lint test fails if a fixture's track names appear in code (§ 11). |
| The shared library looked up configuration by **Korean section headings** of a Markdown file. | The manifest is TOML with English keys. Human-language strings (headings, labels) are manifest *values*. |
| Only 14 of 32 configuration entries were actually read by tools; the rest was prose. | Every manifest key has a schema entry and a reader, or it is rejected as unknown. |
| Three cycle types (refine, spec, devplan) each had their own state machine with the same shape. | One cycle engine; cycle types are declared in the manifest (§ 6). |
| Lane and lock guards existed because several conversations shared one working tree; the project later moved to per-conversation worktrees. | Worktree + pull request is the assumed model. No lane or lock guards in the core. |
| Coordination tooling assumed one operator machine (launchd, local inbox). | Coordination is out of the core. If added, it uses Claude Code's native session features. |
| Ranking context by keyword matches alone pushed the thin current layer below thick archives: across 16 test queries, only 6% of the top-8 results came from current plans, 32% were cycle snapshots and 34% were duplicates. | Context ranking multiplies by layer weight, drops duplicates and leaves finished cycles out by default (§ 8). |

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
| **access scope** | What one cycle step may read and write, declared per step in the manifest (§ 8.1). |
| **section index** | Markdown documents split into heading-level sections, scored against a query to choose context (§ 8.2). |
| **change file** | One proposed change to one document, inside a cycle's `changes/` folder. Applied only after approval (§ 7.2). |
| **session brief** | The short orientation printed when a conversation starts in a strata project (§ 7.3). |

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
| **Cycle** | Unapproved proposals stay in their cycle folder | Loader's `writable_paths` + cycle engine + apply pre-flight | Contract |
| **Role** | Out-of-role writes are visible | `role_shadow` hook | Records only |

The cycle boundary is a contract on purpose: a hook cannot tell a subagent from its caller, and the
same conversation can edit state files. The approval itself — a person answering — is the line that
cannot be crossed.

### 5.3 Guard behaviour rules

These come directly from guard regressions in the earlier project and are tested from day one:

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
corrupted — in the earlier project, a broken state file once let writes through every track guard.

Cycle state is **not** in the manifest. It lives in each cycle's folder and is changed only through
the `strata cycle` command, which writes a record line (M3).

Layers are matched **in declaration order; the first match wins.** Paths that match no layer are not
judged. The manifest file itself (`.strata/strata.toml`) is always writable.

## 7. Document lifecycle

### 7.1 Where documents live

Everything is a Markdown file in the project's git repository. There is no database.

| What | Where | Typical layer mode | Written by |
| --- | --- | --- | --- |
| Cycle working files | `{track}/{cycle folder}/{PREFIX}-{nnn}-{slug}/` | `scratch` | the agent of each step, inside its access scope |
| Cycle state | `{cycle}/.state.json` | `scratch` | `strata cycle` only |
| Inputs and gate answers | `{cycle}/inputs/` | `frozen` | the skill, verbatim, before the step that uses them |
| Proposed changes | `{cycle}/changes/` | `scratch` | the plan step |
| Decision drafts | `{cycle}/decisions/` | `scratch` | the plan step |
| Current documents | for example `{track}/plan/` | `living` | `strata cycle apply` |
| Decision records | for example `{track}/decisions/` | `append-only` | `strata cycle apply` |
| Evidence | for example `{track}/archive/research/` | `frozen` | research steps, once |
| Registers | declared in `[[registers]]` | `append-only` | `strata register add` or `strata cycle apply` |
| Run records | `.strata/records/YYYY-MM.md` | `append-only` | `strata record` |

- **Cycle folders stay after a cycle closes.** They become the evidence behind the decision records the
  cycle produced.
- **Inputs are frozen inside a scratch folder.** Declare an `inputs` layer before the cycle's scratch
  layer; the first match wins (§ 6). A verbatim answer then cannot be edited after the fact.
- **State is JSON**, because the standard library can read TOML but not write it.
- The "written by" column is partly a contract. The guard blocks what a layer mode forbids, but an
  agent outside any cycle may still edit a living document. Such edits are visible in git and, from
  M5, in the role ledger.

### 7.2 Promotion: how an approved proposal reaches the documents

A cycle proposes changes as **change files**, one per target document, in `{cycle}/changes/`:

```markdown
---
target: tracks/business/plan/04-launch.md
action: modify          # create | modify | append | retire
---

Narrow the trial to the districts named in the request.

<!-- strata:current -->
The trial runs in one district.
<!-- strata:revised -->
The trial runs in two neighbouring districts.
<!-- strata:end -->
```

| Action | Meaning |
| --- | --- |
| `modify` | One or more current/revised pairs. Each current block must occur exactly once in the target. |
| `create` | The revised block is the whole new file. The target must not exist. |
| `append` | The revised block is added at the end. Used for registers and append-only documents. |
| `retire` | Sets the target's status to `[documents] retired_status`. The body does not change. |

The markers are HTML comments, so a change file reads naturally in any language and no heading text is
parsed.

**Decision records** are drafted in `{cycle}/decisions/` without a number. Apply gives each the next
free ID in the target folder and adds `based_on: {cycle id}`.

`strata cycle apply --id RF-001` runs in three phases:

1. **Check the approval.** The cycle state must be `approved`, and the approval answer must exist in
   `inputs/` and name the approver role.
2. **Pre-flight every change before writing anything.** The target must exist or not, as the action
   requires. Every current block must still match exactly once. The action must be allowed by the
   target's layer mode, so existing `immutable` and `frozen` files are never touched. Every resulting
   document is validated in memory. Any failure stops the whole apply and nothing is written.
3. **Write, then record.** Write all changes, number and write the decision records, append a record
   line, set the state to `applied`, and print the downstream impacts the plan declared. Apply does not
   open the next cycle; a person does.

A target that no longer matches means the documents changed after approval. The cycle goes back to the
person; the tool never merges around the difference.

An answer that approves "only part", "with changes" or "not now" is not an approval. The skill stores
the answer verbatim and asks whether to open a new cycle or stop. It never applies a subset.

**Why a tool and not the agent.** In the earlier project the agent applied change files by hand, and a
separate rule had to catch the plan and the change files disagreeing. A tool that applies exact text
pairs makes the applied result equal to what was approved, byte for byte, and turns a drifted target
into a stop instead of a silent merge.

### 7.3 Session brief: how a conversation finds its way

When a conversation starts in a project with a manifest, a `SessionStart` hook prints a short brief:

- the project name and the open tracks;
- open cycles, their step and whose turn it is — waiting for an answer, or approved and waiting to be
  applied (from M3);
- the documents to read first, from `[context] start`;
- the strata skills available.

The brief is capped at `[context] brief_chars` (default 1,500 characters). It names files instead of
including them, and it is written in `project.language`. Without a manifest the hook prints nothing.

### 7.4 Manifest keys for the lifecycle (planned — M2 and M3)

Like § 8.3, these keys are **not accepted by the loader yet**.

```toml
[documents]
retired_status = "superseded"          # what a `retire` change sets

[context]
start = ["README.md", "tracks/business/plan/index.md"]   # named in the session brief
brief_chars = 1500

[[cycles]]
id = "refine"
# ...
decisions = { folder = "decisions", prefix = "D" }   # where apply numbers decision records; omit for none
```

## 8. Context selection

Agents must not read large documents whole, and what they read must respect the layers (P1) and the
separation of authors and reviewers (P3). strata selects context in two ways: a fixed scope per cycle
step, and a scored search inside that scope.

### 8.1 Access scope per step

Each cycle step declares what it reads and writes. The loader turns that into two lists for the agent:
`files_to_read`, in order, and `writable_paths`. Anything not listed is not read; listed exclusions win
over inclusions.

```toml
[[cycles.access]]
step = "critique"
reads = ["{track}/plan/**", "{cycle}/request.md", "{cycle}/plan.md", "{cycle}/changes/**"]
excludes = ["{cycle}/verdict.md"]
writes = ["{cycle}/critique.md"]
```

- `{cycle}` is the cycle's own folder and `{track}` is its track's folder. Other placeholders are errors.
- `writes` must stay inside `{cycle}`. This is how P2 ("the path is the gate") reaches the agent.
- A step without an access entry is refused by the loader rather than given everything.
- The loader reports what it excluded, so an agent knows a sibling's output exists and must not be
  looked up.

### 8.2 Scored search

Inside its scope, an agent finds the parts it needs with `strata context`. Documents are indexed by
section (H2 and H3 by default). A query is scored per section; each signal counts at most once per
query token, so repetition does not inflate a score.

| Signal | Default weight |
| --- | --- |
| heading token, exact | 10 |
| file path segment | 8 |
| cited path segment (a path mentioned in the section) | 6 |
| heading token, partial | 5 |
| front-matter `description` | 4 |
| body word | 2 |
| path-shaped query ↔ cited path suffix, or ↔ front-matter `sources` glob | 6 |

The sum is then multiplied by:

- the **layer weight** of the file's layer (`[[layers]] weight`, default 1.0), so the current layer
  outranks an archived copy of the same words;
- the **status weight** of the file's front-matter status (`[documents] status_weights`, for example
  `superseded = 0.5`).

Further rules:

- **Duplicates collapse.** Sections with identical heading and body keep only the highest-ranked copy.
- **Finished cycles and records are left out by default.** "Finished" comes from the cycle engine's
  state, not from the path. An option includes them. Explicit `select:` queries always work. Until the
  cycle engine exists (M3), no cycle counts as finished.
- **Large sections are chunked** at blank lines or table rows, so one huge log table cannot take the
  whole budget.
- **Ties break by layer weight, then path.** Results are deterministic.
- **The index is built per call, in memory.** No cache is written, so the index is never stale. A test
  builds the index for a 500-document fixture inside the latency budget. If real projects outgrow it,
  the planned fallback is a cache under `.strata/` keyed by file size and modification time.
- **The search reports what the exclusions hid** only when an excluded section would have entered the
  top results, so the notice stays meaningful.

Query forms:

| Form | Meaning |
| --- | --- |
| `word word` | Optional tokens, scored together |
| `+word other` | `+word` must appear; the rest are scored |
| `select:path#heading, path2` | Exact sections or files, no scoring |

The intended flow has three steps: list candidates with scores and sizes but no bodies, let the agent
choose, then inject only the chosen sections within a byte budget.

**Language.** Tokenising is chosen by `project.language`. For Korean, adjacent words also match their
joined form (`접수 상태` ↔ `접수상태`) and long Hangul tokens match with or without spaces. Each
language's rules are tested with golden queries in that language's fixture.

**Measuring it.** Each fixture carries golden queries with the sections that must appear in the top
results. A ranking change that drops one fails the suite.

### 8.3 Manifest keys for context selection (planned — M2)

These keys are part of the design and are **not accepted by the loader yet**. They will be added to the
schema, its tests and § 6 together, when M2 is built.

```toml
[[layers]]
id = "current"
mode = "living"
paths = ["tracks/*/plan/**"]
weight = 1.5                 # context ranking multiplier, default 1.0

[documents]
status_weights = { superseded = 0.5 }

[context]
section_levels = [2, 3]      # heading levels that start a section
chunk_bytes = 6000           # sections larger than twice this are chunked
budget_bytes = 40000         # maximum injected per call
limit = 12                   # default number of results
exclude = [".strata/records/**"]   # left out unless asked for

[[cycles.access]]            # one entry per step, see § 8.1
step = "analysis"
reads = ["{track}/plan/**", "{cycle}/inputs/**", "{cycle}/request.md"]
writes = ["{cycle}/analysis.md"]
```

## 9. Plugin layout

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
  context/               section index, scoring, tokenisers per language, step loader   — M2
  brief.py               session brief printed at SessionStart                       — M2
  cycle/                 cycle state machine, change files, apply                    — M3
  i18n/en.toml, ko.toml  user-facing strings
scripts/
  hook.py                hook entry, called by hooks/run.sh
  strata                 command line entry (`strata validate`, `strata cycle …`)   — M1
skills/                  slash commands, written in English                         — M4
agents/                  subagents, written in English                              — M4
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

## 10. Language policy

| Artifact | Language |
| --- | --- |
| Code, identifiers, comments, commit messages | English |
| Skills and agents (`SKILL.md`, `agents/*.md`) | English. The model answers in the user's language. |
| Hook and tool messages | Message catalog. `project.language` selects `en` or `ko`; missing keys fall back to `en`. |
| Documentation | English source in `docs/en/`. Korean translation in `docs/ko/`, whose first line is a marker naming the source file and its hash. `tools/i18n_check.py` fails when a translation is missing or older than its source. |
| README | `README.md` (English) and `README.ko.md` (Korean), same rule as documentation. |
| Project scaffolds | One template set per language. Headings and labels are manifest values, so parsers never depend on a language. |

## 11. Testing rules

- Standard library `unittest`; `python3 -m unittest discover -s tests`.
- **Two fixtures, always.** Every guard and engine test runs against at least two fixture projects
  with different track names and different languages. A behaviour that only works for one is a bug.
- **No vocabulary in code.** A lint test scans the behavioural string literals in `strata/`, `hooks/`
  and `scripts/` (not docstrings or comments) for every track id, folder name, status, step and heading
  used by the fixtures. Any hit fails. Fixture words must not collide with strata's own schema keys.
- **Guards are tested for latency.** A hook that takes longer than a set budget fails the suite.
- **Translations are tested.** `tools/i18n_check.py` runs in the suite.

## 12. Roadmap

| Milestone | Scope | Done when |
| --- | --- | --- |
| **M0 — Foundation** | Manifest loader and schema, layer and track guard, message catalog, i18n check, repository conventions | Guard tests pass on two fixtures; plugin installs from this repository |
| **M1 — Records and validation** | `strata validate` (front-matter, sections, evidence tags), append-only record, registers, `strata init` scaffold | A scaffolded project validates clean in both languages |
| **M2 — Context selection** | Section index, scored search with layer and status weights, `strata context`, per-step access scope and the loader that returns `files_to_read` and `writable_paths` (§ 8); session brief with tracks and start documents (§ 7.3) | Golden queries pass on both fixtures; a step without an access entry is refused |
| **M3 — Cycle engine** | Generic state machine from `[[cycles]]`: steps, rounds, asks, verdicts, answer-file approval; change files and `strata cycle apply` with pre-flight and decision numbering (§ 7.2); open cycles in the session brief | A cycle can stop on every hard-stop reason; approval without an answer file is refused; apply on a drifted target writes nothing |
| **M4 — Agents and skills** | Generic author, critic, arbiter and verifier agents that start from the loader | One end-to-end cycle runs on a fixture project |
| **M5 — Roles and gates** | Role declaration, shadow ledger, gate ownership | Out-of-role writes appear in the ledger; gate answers name the role |
| **M6 — Coordination (optional)** | Work-item adapter contract and a coordinator built on native Claude Code sessions | Defined only after a second real project uses M0–M5 |

## 13. Open questions

| # | Question | Default if unanswered |
| --- | --- | --- |
| Q1 | Is Python 3.11+ an acceptable runtime requirement? | Yes |
| Q2 | Should the earlier project migrate onto strata as the first user? | Not before M4 |
| Q3 | Should strata ship a three-track preset (three tracks, three cycle types)? | Yes, at M4, as a template — not as code |
