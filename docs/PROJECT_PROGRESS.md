# Project Progress Gates

This is a living progress model, not a contract. Weights may change if evidence shows a different path is more valuable. Percent complete is earned by evidence gates, not code volume or agent activity.

## End state (100%)

A reproducible research/production system that can:
1. preserve broad time-correct football and betting-market data;
2. learn conditional normal bookmaker/market behavior;
3. identify measurable abnormal behavior without storytelling;
4. test whether those signals add stable out-of-sample information and economic value;
5. run prospectively with auditability.

## Current weighted gates

| Gate | Weight | Completion rule |
|---|---:|---|
| Research constitution & falsification framework | 7% | time/provenance/audit rules implemented |
| Data-source map & acquisition economics | 6% | credible source landscape + benchmark protocol |
| Reproducible data/CI foundation | 7% | schemas, raw preservation, tests, workflows execute |
| Broad public match/odds baseline | 6% | large multi-league historical coarse layer verified |
| Event/player/context data layers | 12% | event + lineup/player + weather/news/context coverage usable |
| High-resolution historical bookmaker/exchange market data | 22% | real multi-book time series sampled, selected, acquired and profiled |
| Conditional normal-behavior model | 14% | time-safe model predicts expected bookmaker actions/states out of sample |
| Abnormal-residual signal discovery & replication | 12% | signals survive independent datasets/periods/leagues |
| Economic validation/backtest | 9% | realistic odds, costs, availability, limits and robustness evaluated |
| Prospective/live audited operation | 5% | collector + inference + monitoring run prospectively without leakage |

Total: 100%.

## Counting rules

- Documentation alone earns discovery credit, not connection/validation credit.
- A source is not complete until real payloads are sampled and profiled.
- A model is not complete because it trains; it must pass frozen out-of-sample tests.
- Negative experiments can complete a research gate if they decisively eliminate a hypothesis.
- High-resolution market data is intentionally the largest single gate because the central research question cannot be answered honestly without it.

## Current status snapshot — 2026-07-18

Completed/strongly evidenced:
- research constitution/falsification framework
- source map and vendor benchmark method
- reproducible Python/CI/raw-preservation foundation
- initial 19,763-row Big-5 public baseline
- first preregistered external-holdout experiment (inconclusive signal, valid pipeline evidence)

In progress:
- full StatsBomb Open event lake
- full Football-Data seasonal archive expansion
- Tier-1 high-resolution market source sampling/acquisition

Current overall estimate before the in-progress lake expansions finish: **~30%**.

This percentage should only move when a gate produces verified evidence.
