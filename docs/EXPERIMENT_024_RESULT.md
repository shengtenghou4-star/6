# Experiment 024 Result — Outcome attribution of the execution bottleneck

Status: **completed; the historical practical-envelope advantage is home-dependent at the point-estimate level and is not broadly distributed across selected outcomes**.

Run: `29690091781`.

Artifact digest: `sha256:bfc1d45516a4930378a7ece747c1733617c722e14f13bd2aa93b32daa5734901`.

## Frozen reconstruction

The diagnostic rebuilt the exact Experiment 017/023 matched-budget policies over 59,816 opportunities and 18,072 matches, then reran the four fixed practical envelopes: 1-hour delay, 90% fill and 25 bps slippage under common-random fill, adverse-move rejection, highest-edge rejection and bookmaker-clustered outage.

Raw and residual policies retained the same selected-outcome identity. The analysis therefore attributes execution return without allowing the residual policy to switch outcomes.

## Outcome attribution

### Home selections

Home produced positive residual-minus-raw point return in all four mechanisms:

- common random: `+65.84` incremental units, `+0.2456%` per home opportunity;
- adverse-move rejection: `+46.03` units, `+0.1717%`;
- highest-edge rejection: `+41.31` units, `+0.1541%`;
- bookmaker-clustered outage: `+57.58` units, `+0.2148%`.

Residual standalone ROI on filled home selections remained positive in every mechanism, ranging from `+5.14%` to `+6.35%`.

### Draw selections

Draw produced negative incremental point return in all four mechanisms, from `-5.28` to `-12.27` units. Residual standalone draw ROI ranged from `-45.52%` to `-49.34%`.

### Away selections

Away produced negative incremental point return under common-random, adverse-move and highest-edge rejection. It was positive only under bookmaker-clustered outage (`+6.27` units). Residual standalone away ROI remained negative in every mechanism, from `-5.41%` to `-10.75%`.

## Removing home selections

The combined non-home cohort was:

- common random: `-26.27` incremental units;
- adverse-move rejection: `-18.57` units;
- highest-edge rejection: `-13.67` units;
- bookmaker-clustered outage: `+0.99` units.

Thus the residual-minus-raw point advantage became negative in three of four practical mechanisms after home selections were removed. The one remaining positive estimate was economically negligible. No leave-home-out event-cluster 95% interval had a lower bound above zero.

The non-home residual policy was independently unprofitable in every mechanism, with filled ROI between `-10.67%` and `-16.10%`.

## Concentration

Home supplied all positive incremental contribution in common-random, adverse-move and highest-edge rejection. It supplied `90.18%` of positive contribution under bookmaker-clustered outage.

The recorded classification is therefore:

- home incremental point return positive in 4/4 mechanisms;
- draw positive in 0/4;
- away positive in 1/4;
- non-home combined positive in 1/4;
- leave-home-out confidence interval above zero in 0/4;
- `home_dependent_point_attribution = true`;
- `outcome_execution_broadly_distributed = false`.

## Evidence boundary

This experiment was specified after Experiment 023 had already revealed outcome concentration. It is therefore a post-hoc historical diagnostic, not a confirmatory test and not permission to create a home-only strategy.

The supported conclusion is narrower: the historical residual ranking mechanism is broad, but its small practical execution return is not. Under the tested matched-budget policy, the economic value is concentrated in home selections while draw and away selections consume it. A future home-specific policy would require a new, prospectively frozen experiment rather than retrospective filtering of this result.
