# strata

**An operating layer for repositories where AI agents produce layered, approved documents.**

[한국어](README.ko.md)

strata is a [Claude Code](https://claude.com/claude-code) plugin. It is for projects where documents
build on each other — a business plan constrains a product spec, which constrains a development plan —
and where several AI conversations write those documents.

> **Status: early (0.1).** The layer and track guard works and is tested. Cycles, records, agents and
> skills are designed but not built yet. See the [roadmap](docs/en/design.md#12-roadmap).

## What it does

- **Protects layers by path.** Each document belongs to a layer with a write mode: `immutable`,
  `frozen`, `append-only`, `living` or `scratch`. A hook blocks writes that would break the mode —
  for example overwriting a decision record, or editing research after it was written.
- **Keeps closed tracks closed.** Work stages ("tracks") are opened by a person, in the manifest.
  Nothing is written into a track before it is opened.
- **Knows nothing about your domain.** Track names, folders, document types and section headings all
  come from your project's manifest. The code contains none of them, and a test enforces that.
- **Speaks your language.** Messages are available in English and Korean. Documentation is written in
  English and translated, with a check that fails when a translation falls behind.

Planned next: context selection that scores document sections by heading, path, front matter and
layer, so agents read only what they need; bounded multi-agent cycles with machine-counted limits;
approval gates backed by the person's verbatim answer; append-only records and upward-report
registers.

## Install

```bash
claude plugin marketplace add radiostart/strata
claude plugin install strata@strata
```

Requirements: Python 3.11 or later on `PATH`. No other dependencies.

## Use

strata does nothing until a project has a manifest at `.strata/strata.toml`:

```toml
[project]
name = "acme"
language = "en"   # or "ko"
schema = 1

[[tracks]]
id = "business"
path = "tracks/business"
open = true

[[layers]]
id = "decisions"
mode = "append-only"
paths = ["tracks/*/decisions/**"]

[[layers]]
id = "research"
mode = "frozen"
paths = ["tracks/*/research/**"]
```

The full schema is in the [design document](docs/en/design.md#6-the-manifest).

If a block is intended and approved, restart Claude Code with `STRATA_GUARD_BYPASS=1` in its
environment. The guards prevent accidents; they are not a security boundary.

## Develop

```bash
python3 -m unittest discover -s tests
python3 tools/i18n_check.py
```

Repository conventions for contributors and AI agents are in [CLAUDE.md](CLAUDE.md).

## Origin

strata is a clean-room rewrite of an operating layer first built for an earlier, document-first
product project. The principles carried over; the code was written again so that no project's
structure is baked into it. See [design § 2](docs/en/design.md#2-origin-and-what-changed).

## License

[MIT](LICENSE)
