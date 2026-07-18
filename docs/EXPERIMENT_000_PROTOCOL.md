# Experiment 000 — Coarse Bookmaker-Relative Movement

Status: **preregistered before external holdout acquisition**
Date: 2026-07-18

Purpose: test the research machinery and one narrow version of the core hypothesis. This is not the final high-frequency bookmaker-abnormality model.

## Question

After conditioning on the closing market-average 1X2 probabilities, does Bet365's change in relative pricing versus the market from the first recorded odds set to closing contain incremental outcome information?

## Data semantics

Football-Data documents that from 2019/20 onward it collected:
- a first odds set after market opening at scheduled collection times; and
- closing odds marked by `C` in column names.

Exact intraday first-known timestamps are unavailable. Therefore this experiment is only about first-set-to-close relative movement, not minute-level intent or a precise betting cutoff.

## Development data

Big-5 top divisions:
- `E0`, `D1`, `I1`, `SP1`, `F1`
- seasons `1920`, `2021`, `2122`, `2223`, `2324`

These data are development data and may be used to fit the correction table.

## External holdout — locked before acquisition

Leagues not used in development:
- Netherlands `N1`
- Portugal `P1`
- Belgium `B1`
- Scotland top division `SC0`

Seasons:
- `2425`
- `2526`

The external holdout must not be used to alter bins, shrinkage, signal definition, or inclusion rules after results are seen.

## Required fields

Outcome:
- `FTR`

Market-average first/closing 1X2:
- `AvgH`, `AvgD`, `AvgA`
- `AvgCH`, `AvgCD`, `AvgCA`

Bet365 first/closing 1X2:
- `B365H`, `B365D`, `B365A`
- `B365CH`, `B365CD`, `B365CA`

Rows with missing/non-positive required odds or missing H/D/A result are excluded and counted.

## Base probabilities

Base = de-vigged closing market-average implied probabilities from `AvgCH`, `AvgCD`, `AvgCA`.

## Candidate signal

For each selection `j ∈ {H,D,A}`:

`signal_j = log(B365C_j / AvgC_j) - log(B365_j / Avg_j)`

Interpretation: how Bet365's relative price versus market consensus moved between the first set and close.

## Frozen signal bins

`[-inf, -0.03, -0.015, -0.0075, 0, 0.0075, 0.015, 0.03, +inf]`

No bin changes after external holdout acquisition.

## Frozen correction learner

For each selection and signal bin on development data:

1. compute mean residual `y_j - p_base_j`
2. shrink correction toward zero by `n / (n + 500)`
3. at prediction time add the bin correction to each base probability
4. clip each component to `[0.01, 0.98]`
5. renormalize to sum to 1

Shrinkage constant is fixed at `500` before external holdout acquisition.

## Metrics

Primary:
- multiclass Brier score (lower is better)
- multiclass log loss (lower is better)

Report:
- aggregate holdout
- each league separately
- sample counts/exclusions
- corrected minus base metric differences
- paired bootstrap 95% interval for aggregate differences, fixed RNG seed `20260718`

## Interpretation rule

- If corrected model does not improve both aggregate Brier and log loss on external holdout, Experiment 000 does **not** support this coarse signal as robust incremental information.
- Even if it improves both, it remains only a candidate signal because market averages may include Bet365 and timing is coarse. It must be replicated on independent high-frequency, bookmaker-level history before any alpha claim.

Negative results are valid results and must be preserved.
