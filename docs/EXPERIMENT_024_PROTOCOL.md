# Experiment 024 Protocol — Outcome attribution of the execution bottleneck

Status: **post-hoc historical diagnostic specified after Experiment 023 exposed outcome concentration; not confirmatory**.

Experiment 023 found that the residual policy remained directionally better than the raw reference across practical execution envelopes, while positive incremental contribution was concentrated in the home outcome. Experiment 024 determines whether that concentration is cosmetic or whether the execution advantage actually disappears without home selections.

The audit reconstructs the unchanged Experiment 017/023 matched-budget policies and the four fixed practical envelopes: 1-hour delay, 90% fill, 25 bps slippage, under common-random fill, bookmaker-clustered outage, adverse-move rejection and highest-edge rejection.

For each envelope it reports:

- residual standalone fills, profit and ROI by selected outcome;
- residual-minus-raw incremental return by selected outcome;
- event-cluster bootstrap intervals by outcome;
- leave-one-outcome-out incremental return and bootstrap intervals;
- combined non-home attribution;
- positive incremental contribution concentration.

Bookmaker and outcome identity remain fixed by the raw model, so the comparison does not switch which outcome is being evaluated between policies.

Because the concentration warning was already observed, this experiment cannot validate a new strategy or authorize outcome filtering. It can only identify whether the historical execution bottleneck is broadly distributed or home-dependent. Negative and concentrated findings remain first-class results.
