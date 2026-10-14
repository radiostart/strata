---
name: status
description: Summarise the strata project — open and closed tracks, files per layer, documents per type, open register entries and recent run records. Read-only. Use when the user asks where the project stands or what strata is protecting.
---

# /strata:status

Run `strata status` and summarise it. This skill changes nothing.

## Run

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/strata" status --format json
```

Exit code 2 means there is no project or the manifest is invalid. Report the message and stop; for "no
project", suggest `/strata:init`.

## Report

Tell the user, in their language, briefly:

- the project name and which tracks are open or closed;
- each layer with its mode and how many files it holds;
- documents per type, and any type that is used but not declared;
- each register with its open and total entries — and a missing register file as a problem to fix;
- the most recent records.

If the user wants more detail on open register entries, run:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/strata" register list --open
```
