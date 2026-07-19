# Experiment 025 Protocol — Closing-line value to realized-return bridge by outcome

Status: **post-hoc historical diagnostic specified after Experiments 023 and 024; not confirmatory**.

Experiment 024 found that practical realized return was concentrated in home-selected opportunities. Experiment 022, however, found positive closing-line dose slopes for home, draw and away. Experiment 025 separates price-quality evidence from outcome realization.

The audit reconstructs the unchanged matched-budget raw and residual policies and the four fixed practical execution envelopes: 1-hour delay, 90% fill, 25 bps slippage, under common-random fill, bookmaker-clustered outage, adverse-move rejection and highest-edge rejection.

For each selected outcome and envelope, every filled row receives a closing-relative value contribution:

`executed_decimal_odds / closing_decimal_odds - 1`.

Unfilled rows contribute zero. The metric is a closing-line relative valuation diagnostic, not a guaranteed expected return and not a replacement for devigged probability analysis.

The audit reports:

- residual realized return contribution;
- residual closing-relative value contribution;
- residual-minus-raw incremental realized contribution;
- residual-minus-raw incremental closing-relative contribution;
- the realization gap between those two incremental measures;
- event-cluster bootstrap intervals for every measure;
- sign agreement and divergence by home, draw and away.

Bookmaker and selected-outcome identity remain fixed by the raw model. No threshold, cutoff, stake or fill rule is changed.

Because the outcome concentration was already observed, this experiment cannot authorize a new selected-outcome policy. It can only determine whether home concentration is also present in closing-line value or is amplified by finite realized-outcome noise.
