# Experiment 004 Result — Independent Exact-Timestamp Move-Hazard Replication

Status: **completed; independent structural replication supported**.

## Source and eligible states

Independent source: `eladsil/football-games-odds`.

- 166,977 reconstructed match/cutoff states
- 31,882 unique matches with at least one eligible state
- locked test: 12,122 states across 2,150 matches
- no bookmaker identity or cross-book features
- features used only the source's own current/prior state and prior update history

## Important implementation audit

The first workflow attempt exposed a pandas datetime-resolution compatibility trap: converting a datetime series with plain `.astype("int64")` produced resolution-dependent integers under the runner's pandas version, while `Timestamp.value` remained nanoseconds. That made every as-of search select the final quote and falsely created an all-no-move target.

The pipeline now explicitly converts all source timestamps to `datetime64[ns]` before integer search. A state-profile gate records moves by split/cutoff and fails before modeling if a split contains only one class.

No result from the invalid attempt was retained.

## Logistic regression

Locked test against the frozen cutoff-rate baseline:

- baseline Brier: `0.17679303`
- model Brier: `0.17063328`
- relative Brier improvement: **3.48%**
- ROC AUC: `0.7290` versus baseline `0.6841`
- improves **6/6 cutoffs**
- match-bootstrap Brier-improvement CI: `[0.004498, 0.008261]`, entirely above zero

Replication criterion passed.

## Fixed HistGradientBoosting

Locked test:

- baseline Brier: `0.17679303`
- model Brier: `0.16600937`
- relative Brier improvement: **6.10%**
- ROC AUC: `0.7408`
- improves **5/6 cutoffs**
- T-1h is the one negative cutoff
- match-bootstrap Brier-improvement CI: `[0.009500, 0.013488]`, entirely above zero

Replication criterion passed.

## Conclusion

One-hour move/no-move structure is independently learnable in a separate exact-timestamp single-feed dataset, even without cross-book features.

This materially reduces the chance that Experiment 002's result was only an artifact of the Beat The Bookie tensor or its cross-book construction.

It does **not** establish bookmaker intent, outcome alpha or profitability. It independently supports only the normal-behavior hazard layer.

Workflow artifact digest: `sha256:af6381a7218bdfe691de01956536d52a243bbec5123f3f00c2fd0e9239e9c146`.
