---
name: validate
description: Check the project's documents against the strata manifest — required front-matter keys, required sections and evidence-tag references. Use after writing or changing documents, or when the user asks whether documents are valid. Reports problems; fixes only on request.
---

# /strata:validate

Run `strata validate` and report the result.

## Run

With no arguments, check the whole project. If the user names files or folders, pass them:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/strata" validate --format json [PATH ...]
```

- Exit code 0: no errors (warnings may still be listed).
- Exit code 1: errors were found.
- Exit code 2: no project or an invalid manifest. Report the message and stop. For "no project",
  suggest `/strata:init`.

## Report

Tell the user, in their language:

- how many files were checked and how many errors and warnings were found;
- each problem as `path:line — message`, grouped by file, errors before warnings;
- for a warning about an undeclared document type, that the type can be declared in
  `.strata/strata.toml` under `[[documents.types]]`.

## Fixing

Do not fix anything unless the user asks. When asked:

- fix only documents in layers that allow the change — frozen evidence cannot be edited, and an
  append-only record must not be rewritten. If a fix would need that, say so instead;
- never invent a reference to satisfy an evidence tag. If the source is unknown, change the tag to one
  that needs no reference (for example an assumption tag) and tell the user;
- run validation again after fixing and report the new result.
