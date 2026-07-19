# Methods note prospectus - completed

The original prospectus has been promoted into a complete manuscript:

> `paper/methods_note.md` - **From Backtest to Evidence: A falsification-first protocol for machine learning in historical markets**

Current version: **0.9**  
Current status: **complete methods manuscript; external review pending**

The manuscript now contains:

- a full abstract and contribution statement;
- the six-layer evidence model;
- fixed-identity residual learning;
- structure-preserving falsification;
- threshold-free mechanism evidence;
- separation of price quality, payoff and execution;
- deployment-support audits and parallel repair;
- immutable prospective closure;
- machine-checkable claim governance;
- a benchmark implementation and synthetic contract test;
- failure taxonomy, limitations and conclusion.

Evidence provenance is enforced by:

- `paper/methods_claim_registry.json`;
- `scripts/validate_methods_note.py`;
- `tests/test_methods_note.py`;
- the `Research Assets Audit` workflow;
- the dual-paper PDF build.

## Remaining upgrades

The methods paper is ready for external circulation as a preprint draft. Its two material remaining upgrades are:

1. an independent adversarial review;
2. a real second-domain case study using independently sourced data.

The deterministic synthetic MARB profile verifies software and benchmark semantics, but it is not treated as empirical cross-domain replication.

## Publication boundary

The methods contribution is the evidence architecture. The football result remains the empirical paper's primary discovery and must not be repackaged as a second independent finding.
