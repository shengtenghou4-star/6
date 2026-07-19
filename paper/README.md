# Paper package

This directory turns the repository's strongest completed evidence into a living manuscript while keeping claim provenance machine-checkable.

## Main paper

`manuscript.md` is the empirical paper draft:

> **Abnormal Bookmaker Actions Predict Subsequent Repricing: Residual information in multi-book football odds**

The paper is deliberately framed around the replicated repricing-information mechanism. It does not present the project as a validated betting system.

Version 0.1 already contains:

- abstract, literature position and contribution statement;
- data and chronology boundary;
- residual-action method;
- placebo, dose-response and heterogeneity results;
- matched-return, execution and outcome-attribution diagnostics;
- a reserved prospective-results block;
- limitations and defensible conclusion;
- bibliography with DOI-level references.

When the prospective campaign closes, the historical text should remain stable. The update should be limited to the reserved result block, final abstract wording, prospective tables and discussion of transfer.

## Claim provenance

`claim_evidence_registry.json` maps every load-bearing empirical claim to a repository result file and literal evidence tokens. `scripts/validate_paper_claims.py` fails if a source disappears, a required value changes or a claim marker is removed from the manuscript.

Run locally:

```bash
python scripts/validate_paper_claims.py
pytest -q tests/test_paper_claim_registry.py
```

The `Paper Evidence Audit` workflow performs the same check on pull requests and main-branch changes.

## Evidence labels

The paper uses the repository's evidence ladder:

- replicated historical mechanism;
- historical diagnostic;
- post-hoc historical diagnostic;
- executed outcome-blind audit;
- validated prospective evidence only after frozen gates pass.

The following claims remain prohibited until new evidence exists:

- stable realized profit;
- live execution readiness;
- scalable account capacity;
- validated prospective transfer;
- validated home-only strategy.

## Publication path

The draft is designed for three outputs from one evidence base:

1. **Empirical paper** — abnormal bookmaker actions and future repricing.
2. **Methods note** — falsification-first, leakage-safe evaluation of market ML systems.
3. **Open benchmark** — fixed-identity residual ranking tasks and audit contracts.

The empirical paper should be the first submission because it has the strongest completed quantitative result. The methods note and benchmark can cite the same repository without recycling the empirical contribution as a second result claim.
