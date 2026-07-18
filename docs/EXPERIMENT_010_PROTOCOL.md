# Experiment 010 Protocol — Modern Asian Handicap Residual Repricing

Status: **preregistered before execution**.

## Purpose

Test whether the abnormal-action residual mechanism transfers to a modern 2024–2025 Asian Handicap time-series sample with exact update timestamps and 15 masked bookmaker codes.

No match outcomes are used. The dataset's final scores remain excluded from all model inputs and targets.

## Source

Public Kaggle sample: `realsingwong/european-football-asian-handicap-odds-time-series`.

Verified scope:

- 90 matches
- 30 EPL, 30 LaLiga and 30 SerieA
- 15 masked bookmaker codes
- exact UTC update timestamps
- Hong Kong payout odds and Asian Handicap line

The public archive is a 90-match sample, not the advertised full 7,494-match corpus.

## Time convention

For each match, the maximum recorded timestamp is called provider close marker `C`.

`C` is not asserted to equal kickoff. The experiment uses only relative provider-record timing:

- signal states: C-24h, C-12h, C-6h and C-4h
- prior state: one hour before the signal
- residual observation state: one hour after the signal
- future target state: three hours after residual observation

Thus future targets end at C-20h, C-8h, C-2h and C respectively.

## State representation

The source's `Home Odds` and `Away Odds` are Hong Kong net payouts. Decimal odds are `1 + payout`.

Binary de-vigged home share:

`q_home = 1 / (1 + home_payout)`

`q_away = 1 / (1 + away_payout)`

`p_home = q_home / (q_home + q_away)`

Market overround is `q_home + q_away - 1`.

Because source handicap sign convention is not independently verified as home-oriented, the line feature is the absolute handicap magnitude in goals. Split-ball lines are converted to their quarter-ball midpoint.

A raw quote move occurs when line magnitude or either payout changes.

## Split

Within each league, matches are sorted by provider close marker and match ID:

- first 18 matches: normal-model training
- next 6 matches: repricing-model validation training
- last 6 matches: locked test

Total: 54 train, 18 validation and 18 test matches.

## Normal-behavior features

For each target bookmaker:

- prior/current own line magnitude, de-vigged home share and overround
- prior-hour own deltas
- prior/current cross-book median line, home share and overround excluding target
- cross-book line/home-share dispersion
- fraction of other books that moved in the prior hour
- contemporaneous cross-book coverage
- fixed bookmaker, league and cutoff indicators

Models:

- fixed HGB move/no-move classifier
- fixed HGB conditional line-delta regressor
- fixed HGB conditional home-share-delta regressor

All are trained only on the 54-match training split.

## Residuals

Validation/test residuals are frozen before future repricing models:

- signed and absolute move surprise
- conditional line/home-share residuals on actual mover states
- unconditional expected-action residuals
- residual magnitudes
- prior-cutoff residual counts, means and cumulative action residuals

Prior features use only earlier observed cutoffs within the same match/book.

## Fair repricing baseline

The raw-market baseline receives all normal-model features plus:

- actual signal-hour move flag
- actual signal-hour line/home-share deltas
- complete residual-observation line, home share and overround

The augmented model receives exactly the same information plus frozen residual features.

## Future repricing tasks

### A. Future move/no-move

Target: whether line magnitude or either payout changes during the following three hours.

Primary metric: Brier score.

### B. Conditional future state delta

Eligibility: future-mover states.

Targets:

- line-magnitude delta
- de-vigged home-share delta

Primary composite row error:

`0.5 × (absolute line-delta error / 0.25 + absolute home-share error / 0.01)`

The normalizers are domain-natural units: one quarter-ball and one percentage point.

Raw line MAE and home-share MAE are reported separately.

## Models and uncertainty

Baseline and augmented future models use identical fixed HGB architectures:

- `max_iter=120`
- `learning_rate=0.08`
- `max_leaf_nodes=15`
- `l2_regularization=1.0`
- `random_state=20260718`

Paired bootstrap unit: match ID, 2,000 replicates because locked test contains only 18 matches.

## Strict structural replication rule

All conditions are required:

1. augmented future-move Brier is lower than raw-market Brier;
2. move-hazard paired bootstrap CI is entirely above zero;
3. move hazard improves at least 3/4 cutoffs;
4. augmented conditional composite MAE is lower;
5. conditional paired bootstrap CI is entirely above zero;
6. conditional composite improves at least 3/4 cutoffs;
7. augmented raw line MAE is no more than 2% worse than baseline;
8. augmented raw home-share MAE is no more than 2% worse than baseline.

The 18-match test is small; concentration and uncertainty are part of the conclusion. Passing supports transfer of the repricing mechanism to modern AH trajectories. It does not establish kickoff timing, match-result alpha, profit or executable named-book pricing.
