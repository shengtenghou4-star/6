# Portfolio case study

## Project

**Football Market Behavior Lab - leakage-safe residual learning and prospective research infrastructure**

## One-line portfolio description

Built an end-to-end research system that models abnormal bookmaker reactions, falsifies the signal with structure-preserving placebos, separates price-quality evidence from profit and execution, and runs an immutable future validation campaign.

## The problem

Static odds already contain team strength, public information and market consensus. The project asks a narrower question: after conditioning on the observable market state, does a bookmaker's unexpected action predict where that same bookmaker will later reprice?

This creates a difficult attribution problem. A flexible model must not appear better merely because it changes bookmaker or outcome identity. Historical analysis must also avoid future leakage, tuned thresholds, favorable execution assumptions and result-dependent subgroup selection.

## The solution architecture

### Data layer

- timestamped multi-book 1X2 market states;
- chronology-safe quote and transition chains;
- invalid-price, missing-consensus and post-commence rejection;
- immutable raw responses, manifests and hashes;
- separate historical and prospective evidence boundaries.

### Modeling layer

- normal movement-hazard model;
- conditional H/D/A action-delta models;
- raw future-closing models;
- action-residual augmented closing models;
- fixed bookmaker/outcome candidate identity;
- threshold-free residual-uplift analysis.

### Validation layer

- 4,000 baseline-preserving chronological alignment placebos;
- event-cluster confidence intervals;
- dose-response analysis;
- bookmaker, outcome and horizon heterogeneity;
- leave-one-book-out tests;
- equal-capacity return comparison;
- 64-cell delay/fill/rejection execution grid;
- outcome-blind domain-shift audit.

### Prospective layer

- scheduled snapshot collection;
- separately activated original, strict-support and canonical-timing streams;
- frozen candidate ledgers before future targets;
- liveness, source-hash and adapter-coverage audits;
- predefined volume, uncertainty, stability and concentration gates.

### Research-governance layer

- machine-checkable claim-to-evidence registry;
- CI workflows that fail when evidence provenance breaks;
- schema-validated benchmark submissions;
- explicit evidence tiers preventing silent promotion;
- negative and insufficient results retained as first-class outputs.

## Quantitative result summary

- 59,816 matched historical opportunities across 18,072 matches.
- Correct residual alignment beat all 4,000 structure-preserving placebos for closing-price quality.
- One-SD residual-uplift slope: +0.004430 same-book closing log-CLV.
- Event-cluster 95% interval: [+0.003316,+0.005515].
- Positive slopes across 8/8 bookmakers, 3/3 selected outcomes and 4/4 horizons.
- Matched historical ROI: +0.565% residual versus -0.747% raw, with uncertainty crossing zero.
- Incremental point return positive in 60/64 execution cells, but practical execution not validated.
- Synthetic benchmark recovered a planted +0.12 coefficient as +0.120512 without manufacturing a profit claim.

## What this demonstrates to an employer

### Data scientist

Formulated a non-obvious behavioral target, built chronological validation, quantified uncertainty and separated mechanism from economic noise.

### Machine-learning engineer

Serialized and version-pinned a multi-model bundle, enforced feature contracts, added checksums, scheduled workflows, failure recovery and regression tests.

### Quantitative researcher

Used equal-capacity comparisons, alignment placebos, clustered inference, execution stress and prospective freezing rather than relying on one headline backtest.

### Research engineer

Turned experimental evidence into auditable infrastructure: immutable artifacts, claim registries, automated tables, benchmark schemas and reproducibility packets.

### Product or LLM/AI product role

Converted a narrow modeling project into a reusable platform with a paper, benchmark, external-review workflow and cross-domain abstraction.

## Resume bullets

### Research-focused version

- Developed a fixed-identity residual-learning framework over 59.8K football-market opportunities; abnormal bookmaker actions predicted later same-book repricing with positive event-cluster lower bound and passed 4,000 structure-preserving placebo tests.
- Designed a falsification-first evidence ladder separating mechanism, matched return, execution and future transfer; preserved negative profit/execution gates instead of optimizing a promotional backtest.
- Launched an immutable seven-day prospective campaign with pre-target ledgers, source hashes, domain-shift challengers and frozen volume/stability criteria.

### ML engineering version

- Built and productionized a 12-model bookmaker-identity-free scoring bundle with pinned Python/scikit-learn/joblib versions, feature-order contracts, SHA-256 verification and fail-closed loaders.
- Orchestrated scheduled collection, normalization, three-snapshot feature construction, parallel adapter scoring, liveness audits and automatic evidence artifacts through GitHub Actions.
- Added regression coverage for timestamp leakage, identity preservation, model tampering, unsupported horizons, quota logic and evidence-tier promotion.

### General data-science version

- Created an end-to-end market-behavior research pipeline spanning 403K+ historical rows, 18K matches, model training, backtesting, uncertainty, execution simulation and prospective monitoring.
- Identified a broad repricing-information signal across all tested bookmakers, outcomes and horizons while quantifying why the signal had not yet become statistically stable profit.
- Published a reproducible empirical paper draft and open residual-ranking benchmark with machine-checkable claim provenance.

## Interview story: Situation, Task, Action, Result

### Situation

A conventional football prediction approach risked becoming another overfit betting backtest. Static odds already summarized much of the available information.

### Task

Find a scientifically sharper question and build a system capable of distinguishing a real behavioral mechanism from threshold tuning, identity switching and lucky realized outcomes.

### Action

Modeled each bookmaker's expected market reaction, measured abnormal action residuals and froze bookmaker/outcome identity with a raw model. Built alignment placebos preserving baseline structure, tested a continuous dose response, stress-tested equal-capacity economics and execution, audited deployment shift, and froze a future campaign. Added evidence registries and CI to prevent later prose from exceeding results.

### Result

The historical repricing mechanism survived demanding falsification and broad heterogeneity checks. Profit and execution remained unvalidated, which the system recorded explicitly. The repository became a paper, open benchmark and reusable research-infrastructure case study.

## Technical deep-dive prompts

Be prepared to explain:

1. why fixed identity changes causal attribution;
2. why circular shifts are harder than random permutation;
3. why closing-price quality is a mechanism endpoint but not profit;
4. why entity-cluster uncertainty matters;
5. why informed non-fill is more dangerous than random fill loss;
6. why domain-shift repairs must be parallel challengers;
7. how claim registries differ from ordinary tests;
8. what the prospective campaign can and cannot establish.

## Honest limitations

- Historical discovery involved multiple sequential analyses.
- The clean future test is short and may be underpowered in subgroups.
- The independent second profile is synthetic, not real-market replication.
- Closing-line value is not a complete expected-return model.
- Real limits, latency, rejection and account survival remain unmeasured prospectively.

These limitations strengthen the portfolio story: the project demonstrates the ability to identify and govern uncertainty, not merely to generate a favorable metric.

## Recommended portfolio presentation

Lead with the behavioral question and mechanism diagram. Follow with the placebo and dose-response result. Then show the evidence ladder and one workflow diagram. End with the open benchmark and a clear statement that stable profit is not established.

Do not present the project as a betting bot. Present it as a research and ML-infrastructure system for extracting abnormal-agent information from a decentralized pricing market.