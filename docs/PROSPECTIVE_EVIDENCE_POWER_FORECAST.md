# Prospective evidence-volume and power forecast

Status: **operational forecast frozen before the first run**.

## Purpose

The seven-day campaign should not wait blindly for its final evaluation. This forecast estimates whether the untouched candidate stream is accumulating enough independent evidence to make the frozen Phase 43 test informative.

It cannot inspect prospective closing CLV, match outcomes or settlement data, and it cannot alter the running policy.

## Inputs

- cumulative `event-shadow-candidates.csv.gz` from `prospective-data`;
- rows at or after the corrected v2 policy activation `2026-07-19T11:00:00Z`;
- observations no later than the frozen eligible boundary `2026-07-26T03:15:00Z`;
- candidate identity, snapshot, cutoff, bookmaker and the two prospectively generated scores only for positive-score capacity counts.

## Forecast model

Candidate, event and cutoff accrual use a Jeffreys-prior gamma-Poisson model with homogeneous arrival rate over the eligible campaign window. Positive raw- and residual-score capacity uses beta-binomial posterior simulation within each cutoff.

The report uses 20,000 simulations and seed `20260719`.

The forecast does not claim that accrual is truly stationary. Early three-snapshot chain formation may make the first observations conservative, while competition scheduling may make later accrual uneven. Intervals and gate probabilities are operational planning estimates only.

## Frozen Phase 43 volume gates

- at least 300 matured candidate opportunities;
- at least 75 unique events;
- at least 15 exact 5% selections per policy;
- at least three cutoffs with 40 or more candidates;
- enough positive-score candidates to fill every exact quota for both policies.

## Effective sample and power

Repeated candidate rows from the same event and snapshot are summarized with Kish effective sample size.

The minimum detectable incremental log-CLV uses a historical event-cluster planning constant fixed before this prospective forecast:

- cluster sigma equivalent: `0.015268280246644523`;
- two-sided alpha: `0.05`;
- power: `0.80`;
- multiplier: `2.801585`.

This constant is used only for planning. It is not a prospective performance estimate.

## Outputs

- daily candidate/event/snapshot accrual;
- current and projected counts by cutoff;
- projected exact 5% capacity;
- probability of meeting every frozen evidence gate;
- conservative minimum detectable log-CLV lift;
- bookmaker, snapshot and sport concentration;
- explicit early warnings for weak cutoffs or positive-score capacity.

Scheduled forecasts are written immutably under the `prospective-data` branch. A weak forecast may justify a separately preregistered later campaign, but it cannot extend, alter or reinterpret the current seven-day test.