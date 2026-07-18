# Agent Working Agreement

This file guides AI agents and human contributors. It is intentionally a working agreement, not a rigid architecture specification.

## Core behavior

Agents should optimize for truthful research progress, not for appearing productive.

### Must do

- Verify before claiming that a source, API, model, script, or experiment works.
- Preserve timestamp integrity and prevent future-information leakage.
- Keep evidence artifacts: logs, sample outputs, experiment configs, metrics, and failure notes.
- Distinguish `proposed`, `implemented`, `executed`, and `validated` states explicitly.
- Prefer small falsifiable experiments over long chains of unsupported assumptions.
- Record meaningful negative results.
- Surface uncertainty and data-quality problems early.
- Treat existing docs as current context, not unquestionable truth.

### Must not do

- Do not invent successful API calls, training runs, scores, or model identities.
- Do not call a hypothesis validated because it fits a small or repeatedly tuned sample.
- Do not silently use post-event or later-revised information in historical features.
- Do not preserve a failing research direction merely because it appears in an earlier plan.
- Do not add complexity, agents, dashboards, or metrics solely to create an appearance of progress.

## Research autonomy

Agents are explicitly allowed to challenge and replace:

- the current bookmaker-abnormality hypothesis,
- feature definitions,
- dependent variables,
- modeling methods,
- data sources,
- storage architecture,
- other agents' proposals,
- this repository's folder structure.

A proposed change should explain the expected benefit and how it will be tested.

## Evidence ladder

Use these labels consistently when reporting work:

1. **Idea** — plausible but untested.
2. **Implemented** — code/config exists but has not necessarily run successfully.
3. **Executed** — actually ran; logs/artifacts exist.
4. **Replicated** — result reproduced independently or across reruns/data slices.
5. **Validated** — survives predefined out-of-sample and audit criteria.
6. **Operational candidate** — validated enough to consider live/shadow deployment, still subject to risk and execution constraints.

Never skip levels in reporting.

## Suggested roles, not permanent roles

As the project grows, work may be divided among agents for:

- data-source research,
- collection and ingestion,
- normalization/entity resolution,
- feature research,
- modeling,
- leakage/data-quality audit,
- experiment replication,
- backtesting and execution analysis.

These roles may be merged, removed, or redesigned. The project does not require a master-apprentice hierarchy.

## Handoff rule for long-running engineering

When work becomes dominated by repeated local execution, dependency installation, large downloads, database operations, long data pipelines, iterative debugging, or batch model runs, hand the execution loop to a coding/runtime agent such as Codex while keeping research decisions evidence-driven and reviewable in GitHub.
