# Experiment 018 Protocol — Matched-budget execution-friction diagnostic

Status: preregistered before scenario results are opened.

## Question

Does the frozen 5% residual ranking policy retain either standalone or incremental realized-return value after deterministic execution frictions are imposed against a capacity-matched 5% raw-score reference?

## Frozen policies

Reconstruct Experiment 017 exactly:

- deterministic Experiment 016 validation-fit partition;
- raw model fixes bookmaker and outcome identity;
- raw reference requires positive raw score and retains 5% per cutoff;
- residual policy requires positive action-rank score and retains 5% per cutoff;
- timestamp prices and policy flags are bound before outcomes are loaded.

## Execution data

For the selected bookmaker/outcome, extract same-source decimal prices at:

- signal time;
- one hour later;
- two hours later;
- three hours later.

## Frozen scenario grid

Use the existing audited execution engine and its full 64-scenario grid:

- latency: 0, 1, 2, 3 hours;
- adverse slippage: 0, 25, 50, 100 basis points;
- base fill rate: 100%, 90%, 75%, 50%;
- adverse price movement independently reduces fill probability.

The four core scenarios are:

1. 0h / 0 bps / 100% fill;
2. 1h / 25 bps / 90% fill;
3. 2h / 50 bps / 75% fill;
4. 3h / 100 bps / 50% fill.

## Frozen diagnostic checks

The policy is called friction-robust only if all hold:

1. residual ROI per fill is positive in the zero-friction core scenario;
2. residual ROI per fill is positive in the practical 1h/25bps/90% scenario;
3. residual-minus-raw paired 95% lower bound is above zero in zero friction;
4. residual-minus-raw paired 95% lower bound is above zero in the practical scenario;
5. incremental point return is positive in all four core scenarios;
6. no single residual-selected bookmaker supplies more than 50% of positive practical incremental profit.

No rule may be changed after results are opened. This is historical and diagnostic, not live execution evidence.