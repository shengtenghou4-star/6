# Experiment 000 Result — Coarse Bookmaker-Relative Movement

Date: 2026-07-18
Status: completed, **inconclusive / not promoted**

Evidence artifact:
- workflow run `29647866094`
- artifact `experiment-000-evidence`
- artifact digest `sha256:11cafe53d1d8eb6d7482eacac8ab3642b4f047be0814a1329095310fe792514f`

## Samples

Development:
- Big-5 (`E0`, `D1`, `I1`, `SP1`, `F1`)
- seasons 2019/20–2023/24
- 8,950 eligible rows; 5 excluded for missing required fields

Locked external holdout:
- Belgium `B1`, Netherlands `N1`, Portugal `P1`, Scotland `SC0`
- seasons 2024/25–2025/26
- 2,298 eligible rows; 5 excluded for missing required fields

## Aggregate external-holdout result

Base closing market-average model:
- Brier: `0.5701443805`
- log loss: `0.9600270377`

Bookmaker-relative-movement correction:
- Brier: `0.5700237508`
- log loss: `0.9596423926`

Corrected minus base:
- Brier: `-0.0001206297`
- log loss: `-0.0003846451`

Point estimates therefore improved both preregistered metrics, so the minimal point-estimate success rule technically passed.

However paired-bootstrap 95% intervals crossed zero for both:
- Brier delta: `[-0.0008222156, +0.0005705947]`
- log-loss delta: `[-0.0015885092, +0.0007902257]`

League behavior was inconsistent:
- Netherlands improved on both metrics
- Portugal improved slightly on both
- Belgium worsened on both
- Scotland worsened slightly on both

## Decision

**Do not promote this coarse signal as alpha or robust incremental information.**

The experiment shows that the research pipeline can detect and externally test a bookmaker-relative movement hypothesis without relying on LLM scoring, but the observed effect is too small and unstable to support a substantive conclusion.

Next research should move to richer bookmaker-level time series and abnormal-behavior residuals rather than tuning this coarse Football-Data signal against the same holdout.

The external holdout is now considered consumed and must not be reused as an untouched confirmatory set for modified versions of Experiment 000.
