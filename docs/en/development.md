# strata — development guide

> For anyone, person or AI agent, who picks up the next milestone. Read [CLAUDE.md](../../CLAUDE.md)
> for the repository rules and [design.md](design.md) for what strata is. This guide says where the
> work stands and how to continue it.

## 1. Status

| Milestone | State | Notes |
| --- | --- | --- |
| M0 — Foundation | done | Manifest loader, layer and track guard, message catalog, translation check |
| M1 — Records and validation | done | `strata init · validate · status · record · register`, templates `en` and `ko`, skills `/strata:init · validate · status` |
| **M2 — Context selection** | **next** | Work breakdown in § 6 |
| M3 — Cycle engine | not started | Design § 7.2 (change files and apply) |
| M4 — Cycle skills and agents | not started | Waits for M2 and M3 |
| M5 — Roles and gates | not started | |
| M6 — Coordination | not started | Only after a second real project uses M0–M5 |

`git log` has the commit for each milestone.

## 2. Getting started

```bash
git clone https://github.com/radiostart/strata.git
cd strata
python3 --version                      # 3.11 or later
python3 -m unittest discover -s tests  # all tests must pass
python3 tools/i18n_check.py            # translations must be up to date
claude plugin validate .               # one expected warning about CLAUDE.md (design § 9)
```

To try the plugin on a project from your working copy:

```bash
claude plugin marketplace add /path/to/strata
claude plugin install strata@strata
```

To try the command line without the plugin:

```bash
python3 scripts/strata init --lang en --root /tmp/demo
python3 scripts/strata status --root /tmp/demo
```

## 3. Code map

| Path | Responsibility |
| --- | --- |
| `strata/manifest.py` | Schema and loader for `.strata/strata.toml`. Every key is declared here |
| `strata/paths.py` | Glob matching, case folding, project-root discovery |
| `strata/guard.py` | Layer and track decisions for one tool call |
| `strata/bashwrites.py` | Write targets of a Bash command, conservatively |
| `strata/hook.py`, `hooks/run.sh`, `scripts/hook.py` | Hook entry: find Python, read the payload, exit 0 or 2 |
| `strata/validate.py` | Document checks on text, so a proposal can be validated before it is written |
| `strata/records.py` | Monthly append-only run records |
| `strata/registers.py` | Register files: IDs, add, close, list |
| `strata/scaffold.py`, `templates/<lang>/` | `strata init` |
| `strata/status.py` | Read-only project summary |
| `strata/cli.py`, `scripts/strata` | Command line |
| `strata/messages.py`, `strata/i18n/*.toml` | Message catalog |
| `skills/*/SKILL.md` | Thin skills that wrap one command each |
| `tests/` | Unit tests; behaviour tests run on every fixture in `tests/fixtures/` |
| `tools/i18n_check.py` | Translation freshness |

## 4. Rules that catch people out

[CLAUDE.md](../../CLAUDE.md) has the full list. These are the ones that failed during M0 and M1:

- **No project vocabulary in code.** `tests/test_conventions.py` fails when a fixture word appears in a
  behavioural string. It caught a message key named `init.done`, because one fixture uses `done` as a
  status. Rename your identifier; never weaken the test.
- **No `{lang}` placeholder in messages.** `text(key, lang, **params)` already takes `lang`.
- **Every user-facing string goes through the catalog,** with the same key and placeholders in `en.toml`
  and `ko.toml`.
- **Templates must not contain a `.strata/` folder.** The template manifest is `templates/<lang>/manifest.toml`;
  a real `.strata/` would make the template folder a project that the guard judges.
- **The guard sees only Claude's tool calls.** strata's own commands write files directly, so a command
  that writes into layers must check the layer rules itself. This matters for `apply` in M3.
- **English source first.** When `docs/en/*.md` or `README.md` changes, update the Korean translation in
  the same change and run `python3 tools/i18n_check.py --stamp <translation>`.

## 5. How to take a milestone

1. Read the milestone's row in [design § 12](design.md#12-roadmap) and the sections it points to.
2. If the design leaves a decision open, decide it, write it into `docs/en/design.md` and the Korean
   translation **in the same change** as the code, and keep the reason short.
3. Write the failing tests first. Behaviour tests use the `per_fixture` decorator.
4. Build. Keep modules standard-library only.
5. Update `docs/en/cli.md` for any command change, `README.md` if users see a difference, and § 1 of
   this guide. Translate and re-stamp.
6. Run the full suite, the translation check and `claude plugin validate .`.
7. Commit on a branch (`feat/m2-…`), stage files by name, and merge to `main` when the maintainer says so.

## 6. M2 — Context selection: work breakdown

Design: [§ 8](design.md#8-context-selection) and [§ 7.3](design.md#73-session-brief-how-a-conversation-finds-its-way).
Each item is one reviewable change.

| # | Work | Done when |
| --- | --- | --- |
| M2.1 | **Schema.** Accept the planned keys from § 8.3 and the M2 keys from § 7.4: `[[layers]] weight`, `[documents] status_weights`, `[context]` (`section_levels`, `chunk_bytes`, `budget_bytes`, `limit`, `exclude`, `start`, `brief_chars`), `[[cycles.access]]` (`step`, `reads`, `excludes`, `writes`). Reject unknown placeholders and `writes` outside `{cycle}`. Move the keys in § 8.3 and § 7.4 out of "planned" | Schema tests cover each key and each rejection; both fixtures load |
| M2.2 | **Section index** in `strata/context/`. Split Markdown by the configured heading levels, keep the preamble as a section, chunk oversized sections at blank lines or table rows, record path, heading, level, front-matter `description`, `status`, `sources` and cited paths | Index tests on both fixtures, including a chunked table |
| M2.3 | **Tokenisers** per `project.language`. English: lowercase word split. Korean: also match adjacent words joined (`접수 상태` ↔ `접수상태`) and long Hangul tokens with or without spaces | Tokeniser tests per language |
| M2.4 | **Search.** Signals and default weights from § 8.2, layer and status multipliers, duplicate collapse, default exclusions (`.strata/records/**`, `[context] exclude`), deterministic ties, the "hidden by exclusion" notice, the three query forms | Golden queries pass on both fixtures; a current-layer section outranks an archived copy of the same text |
| M2.5 | **Commands.** `strata context QUERY [--limit N] [--format text|json|manifest] [--inject] [--max-bytes N]`. `strata load --cycle-type T --step S --cycle DIR` returns `files_to_read`, `writable_paths` and `excluded` as JSON, and refuses a step without an access entry | CLI tests; refusal test |
| M2.6 | **Session brief.** A `SessionStart` hook prints project, open tracks, `[context] start` documents and strata skills, capped at `brief_chars`, in the project language; nothing without a manifest | Hook test on both fixtures and on a folder without a manifest |
| M2.7 | **Skill** `/strata:context`, wrapping `strata context` with the list → choose → inject flow | Skill calls the command by `${CLAUDE_PLUGIN_ROOT}` path |

**Fixtures need documents for M2.** Add a small corpus to each fixture: current documents, an archived
copy of one of them, a superseded document and an oversized table, in that fixture's language. Store
golden queries next to them, for example `tests/fixtures/<name>/golden.toml`:

```toml
[[queries]]
query = "pricing small shops"
expect = ["<path>#<heading>"]   # must appear in the top results
top = 3
```

**Latency.** Generate a 500-document corpus in a test and assert that indexing plus one query stays
inside the budget. The index is built per call, in memory (§ 8.2).

## 7. Known issues to decide later

- **Fixture word `decisions` versus M3.** Design § 7.1 puts decision drafts in `{cycle}/decisions/`, and
  fixture `alpha` uses `decisions` as a folder name. When M3 code contains that word, the vocabulary
  test will fail. Decide in M3: make the drafts folder a manifest key, or change the fixture's folder
  name. Do not weaken the test.
- **Records actor.** `--actor` falls back to `STRATA_ACTOR`, then `-`. Roles (M5) will decide what an
  actor is.
- **Windows.** Hooks run through `sh`; on Windows that means Git Bash. Not yet tested.
- **Commands refused by permission policies.** Some environments refuse shell commands such as
  `rm -rf` or `chmod`. Tests use `tempfile` and never need them; keep it that way.
