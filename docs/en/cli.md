# strata — command reference

> Applies to strata 0.2 (milestone M1). The design behind these commands is in [design.md](design.md).

Run the command line with Python 3.11 or later:

```bash
python3 <plugin>/scripts/strata <command> [options]
```

Inside Claude Code, the skills `/strata:init`, `/strata:validate` and `/strata:status` call it for you.

Every command accepts `--root DIR` (default: the nearest folder at or above the working directory that
holds `.strata/strata.toml`) and most accept `--format text|json`. Messages use the project's
`project.language`.

| Exit code | Meaning |
| --- | --- |
| 0 | Success |
| 1 | Problems found (`validate`) or the operation was refused (`record`, `register`) |
| 2 | Usage error, no project found, or an invalid manifest |

## init

Create a project skeleton from a template.

```bash
strata init [--lang en|ko] [--name ID] [--actor NAME]
```

- `--lang` picks the template; default `en`. Templates live in `templates/<lang>/`.
- `--name` is the project id: lowercase letters, digits and `-`, starting with a letter. Default: derived
  from the folder name.
- Creates `.strata/strata.toml`, the folders and an example decision from the template, every register
  file the manifest declares, and an `init` record.
- **Never overwrites.** If any file it would create already exists, nothing is written and the exit
  code is 2.

## validate

Check documents against the manifest.

```bash
strata validate [PATH ...]
```

With no paths, every `*.md` file in the project is examined, skipping hidden folders such as `.git` and
`.strata`. Paths may be files or folders.

A file is checked only when its front matter has a `type`. Then:

| Check | Severity |
| --- | --- |
| The `type` is declared in `[[documents.types]]` | warning if not |
| Every key in the type's `frontmatter` list is present and not empty | error |
| Every heading in the type's `sections` list appears as a level-2 heading (`## …`). A leading number such as `1.`, `2.3` or `4)` and letter case are ignored | error |
| Every evidence tag that has a `reference` pattern is followed, **on the same line**, by a match of that pattern | error |
| Front matter that starts with `---` is closed | error |

Text inside fenced code blocks is ignored for headings and tags. Warnings do not change the exit code.

## status

Summarise the project: tracks, files per layer, documents per type, registers and recent records.
Read-only.

```bash
strata status [--format json]
```

## record

Append-only run records, one file per month: `.strata/records/YYYY-MM.md`.

```bash
strata record add --kind KIND --target TARGET --result RESULT [--actor NAME] [--evidence PATH] [--note TEXT]
strata record list [--limit N]
```

- `kind`, `target`, `actor` and `result` must not be empty. `--actor` defaults to the `STRATA_ACTOR`
  environment variable, then `-`.
- Each cell is at most 300 characters. Put longer details in a file and pass its path as `--evidence`.
- A row is one line of a Markdown table. `|` is escaped and newlines become spaces.
- The guard treats `.strata/records/` as append-only in every project, whatever the manifest says:
  rows can be added, never replaced or deleted.

## register

Registers are append-only lists of upward reports or issues, declared in `[[registers]]`.

```bash
strata register add --register ID --title TEXT [--source REF]
strata register close --id ENTRY-ID --resolution TEXT
strata register list [--register ID] [--open]
```

A register file is a Markdown table with the columns ID, date, status, title, source and resolution.

- **IDs.** The next ID is one more than the highest `{prefix}-{n}` in the **first column**. IDs quoted
  in titles never shift numbering.
- **Missing file.** If the register file does not exist, `add` fails. It never creates a new file,
  because a wrong path would otherwise restart numbering at 1.
- **Status.** The status cell holds the fixed tokens `open` or `closed`, so tools read it the same way in
  every language. `close` changes only that entry's line: status becomes `closed` and the resolution
  cell is filled.
