---
name: init
description: Create a strata project skeleton in the current repository — manifest, layer folders, an example decision, the issues register and the first run record. Use when the user wants to start using strata in a project. Never overwrites an existing project.
---

# /strata:init

Create a strata project in the current repository with `strata init`.

## Before running

1. Check that Python 3.11 or later is available: `python3 --version`. If it is missing or older, stop
   and tell the user strata needs Python 3.11+.
2. If `.strata/strata.toml` already exists at or above the working directory, stop. Report that the
   project already exists and suggest `/strata:status`. `strata init` refuses to overwrite anyway.
3. Choose the template language:
   - use the language the user asked for, if any (`en` or `ko`);
   - otherwise use the language the user is writing in (Korean → `ko`, anything else → `en`).
4. Choose the project id: the user's choice if given, otherwise let the command derive it from the
   folder name. An id is lowercase letters, digits and `-`, starting with a letter.

## Run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/strata" init --lang <en|ko> [--name <id>] --actor claude
```

Exit code 0 means the skeleton was created. Any other exit code means nothing was written; report the
message as it is.

## After running

Tell the user, in their language:

- what was created (the command lists every file and folder);
- that writes are now guarded by layer. Read the `[[layers]]` tables in the new
  `.strata/strata.toml` and name each layer's paths and mode in plain words (frozen: new files only;
  append-only: never replaced or deleted; living: free until its status is frozen). Do not describe
  layers from memory — the manifest is the source;
- that `.strata/strata.toml` is theirs to edit — tracks, layers, document types and evidence tags;
- the next commands: `/strata:validate` to check documents, `/strata:status` for a summary.

Do not edit the manifest or create documents unless the user asks.
