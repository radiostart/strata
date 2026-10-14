# strata — working agreement for AI agents

strata is a Claude Code plugin. Its design is [`docs/en/design.md`](docs/en/design.md); read it before
changing behaviour. Where the work stands and what to do next is in
[`docs/en/development.md`](docs/en/development.md). This file holds only the rules for working in this
repository.

## Language

- **Talk to the maintainer in Korean.** Everything that ships is English: code, identifiers,
  comments, commit messages, skills, agents, hook and tool messages (source catalog `en.toml`).
- **Documentation is written in English first, then translated.** English lives in `docs/en/` and
  `README.md`. The Korean translation lives in `docs/ko/` and `README.ko.md`.
- Every translation starts with a marker line written by `tools/i18n_check.py --stamp <file>`. When an
  English source changes, update its translation in the same change and re-stamp it. The test suite
  fails while a translation is stale or missing.
- User-facing strings go in `strata/i18n/en.toml` with the same key in `ko.toml`. Never inline a message
  in code. Placeholders must match across languages; a test checks this.

## Code rules

- **Standard library only. Python 3.11+.** No third-party imports anywhere in `strata/`, `hooks/`,
  `scripts/` or `tools/`.
- **No project vocabulary in code.** Track names, folder names, headings, statuses and roles come from
  the user's manifest. `tests/test_conventions.py` fails if any fixture word appears in a behavioural
  string literal.
- **Every manifest key has a schema entry and a reader.** Adding a key means updating
  `strata/manifest.py`, its tests, and design § 6 in one change.
- **Guards are accident prevention, not security.** Prefer a clear block message over clever parsing.
  When a command cannot be understood, block only if it names a protected zone.
- **Never lock the way out.** `.strata/strata.toml` stays writable in every state.
- Do not add a top-level `bin/` directory; it stops claude.ai and Cowork from installing the plugin.

## Tests

```bash
python3 -m unittest discover -s tests
python3 tools/i18n_check.py
```

- Behaviour tests run against **every fixture** in `tests/fixtures/` through the `per_fixture`
  decorator. A behaviour that works for one fixture only is a bug.
- Fixtures must use different track names, folder names and languages from each other. Fixture words
  must not collide with strata's own schema keys, or the vocabulary test cannot see them.
- When fixing a guard bug, add the failing case first.

## Commits

- Conventional style, English, one line summary: `feat(guard): ...`, `fix(manifest): ...`,
  `docs(design): ...`, `test(guard): ...`, `chore: ...`.
- Stage files by name. Do not use `git add -A`.
- Commit or push only when the maintainer asks.

## Scope

- The earlier project in design § 2 is the origin of the principles, not a dependency. Do not import
  or copy its code, and do not name it in anything this repository ships; re-derive behaviour from
  the design document and write it fresh.
- Do not use other plugins as design references unless the maintainer names one.
