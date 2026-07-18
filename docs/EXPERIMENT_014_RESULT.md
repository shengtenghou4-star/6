# Experiment 014 — Completely unseen-book action-residual transfer result

Status: **primary transfer not promoted; structural transfer supported**

This was a diagnostic leave-one-book-out audit on an already opened historical period. It is not a new untouched alpha or profit test.

## Locked scope

- 8 leave-one-book-out folds
- 18,072 locked-test matches
- 403,248 held-out-book quote rows
- 59,816 match/cutoff strategy opportunities
- every quote scored by normal-action and closing models that never trained on that bookmaker
- bookmaker one-hot identity removed from all model inputs

## Structural closing-model transfer

### Closing move hazard

- generic raw-market Brier: `0.12172419`
- action-residual Brier: `0.12169382`
- improvement: `0.00003037`
- paired match-bootstrap CI: `[-0.00002773, 0.00009096]`
- improved cutoffs: `2/4`

The move-timing layer was not promoted, consistent with Experiment 012: contemporaneous action residuals were not the main move-hazard carrier.

### Conditional closing H/D/A repricing

- generic raw-market MAE: `0.02015174`
- action-residual MAE: `0.02014590`
- improvement: `0.00000584`
- paired match-bootstrap CI: `[0.00000111, 0.00001061]`
- improved cutoffs: `4/4`

The conditional direction/magnitude layer transferred significantly to bookmakers excluded from all model training.

## Frozen rank-only closing-CLV strategy

The generic raw model selected bookmaker/outcome candidates. The unseen-book action model only reranked those fixed identities.

- raw baseline mean trade log-CLV: `0.02373370`
- unseen-book action ranker mean trade log-CLV: `0.02518585`
- incremental opportunity log-CLV: `0.00029038`
- paired match-bootstrap CI: `[-0.00002835, 0.00062046]`
- positive point lift at `3/4` cutoffs

The action selector, which could replace candidate identity, added only `0.00008847` opportunity log-CLV and also had a confidence interval crossing zero.

## Bookmaker concentration

Positive ranker contributions came from four held-out bookmakers and negative contributions from four.

Largest positive contribution share:

- bet365 (`b9`): `41.14%`

The frozen concentration ceiling was `40%`, so this gate failed narrowly. Other positive contributors were Betclic (`27.35%`), Tipico (`19.52%`) and 10Bet (`11.99%`).

## Frozen gate decision

Primary promotion required all three:

1. incremental rank-only CLV CI above zero — **failed narrowly**;
2. positive lift in at least 3/4 cutoffs — **passed**;
3. no held-out bookmaker above 40% of positive contribution — **failed narrowly** at 41.14%.

Therefore generic unseen-book economic transfer is **not promoted**.

The structural transfer gate passed:

- conditional closing-delta improvement CI was above zero;
- all four cutoffs improved.

## Interpretation

The action-residual mechanism is not merely memorizing bookmaker identity. Its directional/magnitude information survives complete bookmaker exclusion, and its rank-only economic point estimate remains positive. However, the historical evidence is still too concentrated and the incremental CLV interval touches zero.

The correct operational stance is:

- generic action residuals are justified as a **research shadow-ranking signal** for new bookmaker keys;
- they are not yet justified as a transferable executable alpha rule;
- bookmaker-specific calibration should remain optional context, not a prerequisite for structural scoring;
- untouched prospective data is required to resolve the remaining uncertainty.

No post-result threshold, fold, feature, cutoff or concentration rule was changed.

Artifact digest: `sha256:076c3cfb65eababdad7ac192d71a68261bd7d202cbc1df67ddc55c2e9c77b008`
