# Paper package

This directory contains two living manuscripts with machine-checkable evidence provenance.

## Empirical paper

`manuscript.md`:

> **Abnormal Bookmaker Actions Predict Subsequent Repricing: Residual information in multi-book football odds**

The empirical paper centers the replicated historical repricing-information mechanism. Version 0.1 contains the literature position, chronology boundary, residual-action method, placebo, dose-response, heterogeneity, matched-return, execution and outcome-attribution results, plus a reserved prospective result block.

When the campaign closes, the historical sections should remain stable. Only the reserved prospective block, final abstract wording, prospective tables and transfer discussion should change.

Its claims are governed by `claim_evidence_registry.json` and `scripts/validate_paper_claims.py`.

## Methods paper

`methods_note.md`:

> **From Backtest to Evidence: A falsification-first protocol for machine learning in historical markets**

Version 0.9 is a complete methods manuscript, not an outline. It extracts the reusable research architecture:

- chronology and data contracts;
- fixed candidate identity;
- structure-preserving alignment placebos;
- threshold-free evidence before strategy selection;
- separation of mechanism, economics and execution;
- outcome-blind deployment support audits;
- parallel repair rather than retrospective stream rewriting;
- immutable future ledgers and evidence tiers;
- machine-checkable claim governance.

The football project is the worked example. The deterministic synthetic MARB profile is a contract test, not a claimed real-domain replication. The strongest missing extension is an independently sourced empirical second domain.

Methods-paper claims are governed by `methods_claim_registry.json` and `scripts/validate_methods_note.py`.

## Local checks

```bash
python scripts/validate_paper_claims.py
python scripts/validate_methods_note.py
pytest -q tests/test_paper_claim_registry.py tests/test_methods_note.py
```

The `Paper Evidence Audit`, `Research Assets Audit` and `Paper Build` workflows check provenance, tests and PDF compilation.

## PDF artifacts

The paper workflow builds:

- `abnormal-bookmaker-actions.pdf`;
- `from-backtest-to-evidence.pdf`.

Both are research drafts. Successful compilation does not promote an evidence tier.

## Evidence boundaries

The following claims remain prohibited until new evidence exists:

- stable realized profit;
- live execution readiness;
- scalable account capacity;
- validated prospective transfer;
- validated home-only strategy;
- validated empirical cross-domain transfer.

## Publication path

The current evidence base supports three distinct outputs:

1. **Empirical paper** - the historical bookmaker repricing mechanism and prospective test.
2. **Methods paper** - a falsification-first protocol for historical market ML.
3. **MARB benchmark** - fixed-identity residual ranking, evidence tiers and submission contracts.

The empirical paper carries the primary quantitative discovery. The methods paper contributes the evidence architecture. The benchmark supplies an executable extension path. They should cross-reference each other without presenting the same empirical finding as three independent discoveries.
