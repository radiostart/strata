---
type: decision
id: D-001
title: Adopt strata for {{project}}
date: {{date}}
status: accepted
---

# D-001 — Adopt strata for {{project}}

## Context

Documents in this project build on each other and several AI conversations write them. Without
guard rails, a decision can be overwritten or research edited after the fact. [assumption]

## Decision

Use strata. Decisions go in `work/decisions/` and are append-only. Research goes in `work/evidence/`
and is frozen once written. Living documents go in `work/current/`.

## Consequences

- To change a decision, write a new one and mark the old one `superseded`.
- Issues that need a decision go in the `issues` register (`strata register add`).

## Review conditions

Revisit if the layer rules block more legitimate work than they prevent mistakes.
