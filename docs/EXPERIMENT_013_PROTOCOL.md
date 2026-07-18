# Experiment 013 — Selection versus ranking decomposition

## Status

Preregistered before opening the decomposition output.

This is a diagnostic mechanism study on the already opened Experiment 011 historical test period. It cannot create a new untouched alpha or profit claim.

## Frozen reconstruction

- same Beat The Bookie source and chronological split
- same eight named bookmaker slots
- same T-48h, T-24h, T-12h and T-6h signals
- same final same-book closing state at index 71
- same raw-market and full-residual HGB models
- no match outcomes
- same top-20% trade fraction by cutoff
- deterministic tie handling

## Candidate identity

For each bookmaker row, select the H/D/A outcome with the largest predicted closing-probability increase. For each match × cutoff, select the bookmaker/outcome row with the largest score. This bookmaker/outcome pair is the candidate identity.

## Frozen strategies

1. **Raw baseline**: baseline identity and baseline ranking score.
2. **Full residual**: full-residual identity and full-residual ranking score.
3. **Rank-only overlay**: baseline identity is fixed; the full-residual model scores that exact bookmaker/outcome identity for top-20% trade ranking.
4. **Selection-only overlay**: full-residual identity is fixed; the baseline model scores that exact bookmaker/outcome identity for top-20% trade ranking.

Every strategy settles CLV using the selected candidate's actual observation and closing prices.

## Outputs

- bookmaker/outcome identity overlap between baseline and full residual
- trade-set overlap
- mean trade and opportunity closing log-CLV and fair-probability CLV
- paired match-bootstrap incremental opportunity log-CLV versus baseline
- incremental lift by cutoff
- rank-only and selection-only point lift as a share of the full residual lift

## Interpretation

A stronger rank-only overlay means residuals mainly identify **when** an otherwise similar market signal is trustworthy. A stronger selection-only overlay means residuals mainly change **which bookmaker/outcome direction** is chosen. Both can contribute.

No thresholds, models, cutoffs, candidate rules or trade fractions may be changed after the result is opened.