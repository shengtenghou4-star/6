# From Backtest to Evidence

## A falsification-first protocol for machine learning in historical markets

**Draft version:** 0.9  
**Status:** complete methods manuscript; external review pending  
**Role:** protocol paper with the football market project as a worked example

## Abstract

Machine-learning studies of historical markets often compress several different questions into one backtest number. A model may identify a genuine predictive mechanism yet fail to convert it into stable return; an apparent return improvement may instead come from identity substitution, threshold selection, temporal leakage or optimistic execution assumptions. We present a falsification-first protocol that separates six layers: chronology, candidate identity, mechanism, economic conversion, execution and prospective transfer.

The protocol uses five devices. A raw model fixes agent and instrument identity before flexible residual information is introduced. Structure-preserving placebos break only the claimed entity-time alignment while retaining baseline score, chronology, score distribution and capacity. Threshold-free dose response precedes top-tail policy selection. Price-quality, realized-payoff and execution endpoints are reported separately. Deployment repairs are activated as parallel challengers rather than used to rewrite an original prospective stream.

A football-odds program provides a worked example. Its historical mechanism survives 4,000 alignment placebos, has a positive continuous residual-uplift relationship and remains positive across bookmakers, outcomes and horizons [M01_PLACEBO] [M02_DOSE] [M03_DISTRIBUTION]. Matched return and execution remain uncertain or fragile [M04_ECONOMICS] [M05_EXECUTION]. An outcome-blind deployment audit identifies timing and source-panel mismatch, handled through separately activated adapters [M06_DOMAIN_SHIFT]. A deterministic synthetic profile verifies that the benchmark recovers a known residual mechanism without manufacturing a profit claim [M07_SYNTHETIC].

The contribution is an auditable evidence architecture, applicable wherever multiple agents repeatedly revise prices or forecasts and later same-agent targets can be observed.

## 1. The identification problem

Historical market data are easy to over-interpret. The analyst sees the entire sequence, can test many thresholds and subgroups, and can silently alter the object being predicted. Even without an explicit future feature, leakage can enter through revised data, entity resolution, outcome-dependent filtering, repeated observations crossing a split or execution prices chosen after a strategy is known.

A single backtest is often asked to establish all of the following:

1. a statistical relationship exists;
2. it is attached to the correct entity and time;
3. it improves decisions at equal capacity;
4. it survives delay, slippage and non-fill;
5. it transfers to future data;
6. it can operate at useful scale.

These are separate claims. Passing an earlier layer does not imply passing the next, and failure at a later layer does not necessarily erase a scientifically useful mechanism.

## 2. Six evidence layers

### 2.1 Chronology

Every field needs an availability timestamp and revision rule. Event time, observation time and target time must remain separate. Post-event and settlement fields are forbidden from scoring. Repeated entities must not leak across splits. Confirmatory inputs should carry manifests and checksums.

A chronology-unsafe dataset cannot be repaired by stronger statistics later.

### 2.2 Candidate identity

Let each opportunity contain entity \(e_i\), agent \(a_i\), instrument \(j_i\), observation time \(t_i\) and state \(X_i\). A flexible model can appear to improve simply because it changes the agent or instrument.

The fixed-identity rule assigns two roles:

- the raw model fixes \((a_i,j_i)\);
- the augmented model may alter only confidence or rank for that same identity.

Identity and policy membership are written before future prices or outcomes are joined. This isolates incremental information rather than gains from choosing a different object.

### 2.3 Mechanism

A normal-action model estimates

\[
\widehat{A}_i=f(X_i),
\]

and the abnormal action is

\[
R_i=A_i-\widehat{A}_i.
\]

A raw future-price score is \(S_i^{raw}\); an augmented score using residual information is \(S_i^{aug}\). Residual uplift is

\[
U_i=S_i^{aug}-S_i^{raw}.
\]

The mechanism question is whether larger \(U_i\), conditional on baseline state and fixed identity, predicts better later same-agent price quality.

### 2.4 Economic conversion

Economic conversion compares raw and residual policies on the same candidate universe at the same quota. Prices are bound before outcomes are loaded, uncertainty is paired at entity level, and agents, instruments or horizons cannot be deleted after results are seen.

A positive point estimate with an interval crossing zero remains a diagnostic.

### 2.5 Execution

Execution is a separate model of the path from selection to fill. It should vary delay, slippage, fill rate, clustered outage, adverse-move rejection and highest-edge rejection. Random missingness alone is optimistic because non-fill can be informative.

### 2.6 Prospective transfer

A future test starts only after the model bundle, activation boundary, policy and gates are frozen. Candidate ledgers are written before targets mature. Volume, uncertainty, stability and concentration gates are specified in advance. Insufficient volume is an outcome, not permission to lower thresholds or backfill earlier rows.

## 3. Structure-preserving falsification

A fully random label shuffle usually destroys too much structure. Beating it may show only that some temporal or cross-sectional signal exists.

A demanding alignment placebo preserves:

- baseline scores;
- agent and instrument identity;
- chronological agent-by-horizon groups;
- residual-score distribution;
- exact decision capacity;

while attaching residual uplift to the wrong opportunities within each group. Circular shifts are useful because they preserve the empirical distribution without replacement.

In the football example, correct match-specific alignment beats all 4,000 baseline-preserving chronological shifts for selected and incremental closing log-price quality, with empirical upper-tail probability 0.00025 [M01_PLACEBO]. This supports correct alignment, not profitability.

Useful negative controls include wrong-agent targets, distant-time residuals, synthetic noise residuals, calendar-block shifts and source-removal tests. A pipeline that passes every negative control deserves suspicion.

## 4. Threshold-free evidence first

Top-tail policies are easy to tune. The protocol therefore estimates a continuous relationship before selecting a strategy. Baseline scores are divided into narrow strata, residual uplift is standardized, and later price quality is related to uplift after within-stratum centering.

Supporting diagnostics include the slope per standard deviation, highest-minus-lowest dose contrast, entity-cluster uncertainty, alignment placebos, subgroup slopes and leave-one-agent-out estimates.

In the worked example, one standard deviation of residual uplift is associated with +0.004430 same-book closing log-price quality, with event-cluster 95% interval [+0.003316,+0.005515] [M02_DOSE]. Slopes are positive for all eight tested bookmakers, all three selected outcomes and all four horizons; every leave-one-book-out lower bound remains above zero [M03_DISTRIBUTION].

Only after this relationship is established should a top-tail rule be treated as an economic diagnostic.

## 5. Endpoint hierarchy

### 5.1 Price quality is not profit

A later improved price can be informative even when the final event outcome is unfavorable. Realized payoff adds outcome variance to the price-selection problem. Closing-price quality is therefore a lower-variance mechanism endpoint, although it is not a guarantee of devigged expected return.

### 5.2 Profit is not execution

A strategy evaluated at the observation quote has not shown that the quote can be captured. The football example moves matched point ROI from -0.747% for the raw reference to +0.565% for the residual policy, but standalone and paired intervals cross zero [M04_ECONOMICS]. Residual-minus-raw point return remains positive in 60 of 64 frozen execution cells, yet no practical envelope clears paired uncertainty and adversarial rejection removes standalone profitability [M05_EXECUTION].

The mechanism is supported more strongly than the economics. That is a coherent result, not a contradiction.

### 5.3 Concentration

A positive aggregate can be supplied by one agent, horizon, instrument or calendar block. Concentration limits and leave-one-group-out checks should be frozen with the main test. A post-hoc subgroup result may motivate a new prospective cohort but cannot authorize retrospective filtering.

## 6. Deployment support and parallel repair

Before interpreting prospective performance, compare historical and deployment inputs without reading future targets. Recommended diagnostics include standardized mean difference, population-stability index, interval overlap, out-of-support rate, a grouped historical-versus-deployment discriminator, panel breadth and timing compatibility.

When a mismatch appears:

1. preserve the original deployment as the test of the original specification;
2. document the mismatch outcome-blindly;
3. activate a separate challenger with a new timestamp;
4. give it an independent ledger and evaluator;
5. compare coverage and score agreement without targets.

The football audit identifies broad timing windows versus historical exact-cutoff states and a smaller current source panel than the historical peer-book scale [M06_DOMAIN_SHIFT]. The original stream remains intact; strict-support and canonical-timing challengers are separately activated.

The governing principle is simple: repair future evidence, do not rewrite past evidence.

## 7. Immutable prospective closure

A confirmatory campaign should retain three artifact classes.

**Inputs and provenance:** timestamped raw responses, normalized snapshots, manifests, model identifiers, adapter version and activation time.

**Pre-target decisions:** fixed identity, scores, quota, policy membership, excluded-row reasons, ledger checksum and research-only flags.

**Post-target evaluation:** target-join report, chronology rejection report, primary statistic, cluster uncertainty, subgroup stability, concentration, volume status and an interpretation constrained by the evidence tier.

A successful short campaign still does not establish capacity, long-run stationarity or live execution.

## 8. Machine-checkable claim governance

Research prose drifts. A claim registry assigns each load-bearing statement a stable ID, evidence level, source path, required source literals and manuscript marker. Continuous integration fails if a source disappears, a value changes or a marker is removed.

This does not prove truth; it prevents silent provenance breakage.

Benchmark submissions use the same principle. Their schema and semantic validator block a result from declaring a prospective or operational tier unless prospective status and execution fields justify the promotion.

## 9. Benchmark implementation

The Market Action Residual Benchmark defines four tasks: normal-action prediction, fixed-identity residual repricing, distribution and transport, and economic conversion. Each submission carries chronology controls, mechanism statistics, subgroup summaries, economic diagnostics, prospective status, hashes and an evidence tier.

A deterministic synthetic profile inserts a true residual coefficient of +0.12. The evaluation recovers +0.120512 with bootstrap interval [+0.107430,+0.133668], beats 1,000 alignment placebos and remains positive across every simulated agent, instrument and horizon. An independently generated return variable has an interval crossing zero, so execution validation remains false [M07_SYNTHETIC].

This validates software behavior under a known process. It is not a real cross-domain replication.

## 10. Practical sequence

A research team can implement the protocol in four stages.

**Contracts:** define entity, agent, instrument, action and same-agent target; timestamp every field; freeze splits, identity rules and prohibited claims.

**Mechanism:** fit the normal-action model on earlier data; form residuals; freeze identity; estimate dose response; run alignment placebos and heterogeneity checks.

**Economics:** compare equal-capacity policies; bind prices before outcomes; report paired intervals; stress delay, slippage and informative non-fill.

**Transfer:** serialize and checksum the bundle; audit deployment support; activate repairs separately; write future ledgers; join mature targets; apply frozen gates.

## 11. Failure taxonomy

The protocol records distinct failure modes:

- chronology failure;
- identity substitution;
- entity-time alignment failure;
- threshold-only effect;
- subgroup concentration;
- uncertain economic conversion;
- execution fragility;
- deployment-support mismatch;
- insufficient confirmatory volume;
- adequately powered transfer failure.

Each should remain visible. A project can pass one layer and fail another without inconsistency.

## 12. Limitations

Fixed identity may be too restrictive when the real decision is explicitly to choose among agents; that should be a separate task. Alignment placebos cannot eliminate every omitted contemporaneous variable. Later same-agent price may be a weak endpoint in illiquid or manipulated markets. Transparent histories cannot erase researcher choices made before preregistration. Synthetic recovery validates implementation but not empirical transport.

The strongest missing extension is an independently sourced real second domain with its own frozen chronology and identity contract.

## 13. Conclusion

Historical market models should not jump from predictive fit to operational claims. They should pass through chronology, fixed identity, mechanism falsification, threshold-free evidence, matched economic conversion, execution stress and untouched future transfer.

The worked football program shows why this separation matters: its repricing-information mechanism is historically strong, while economic and execution evidence remains incomplete. The synthetic benchmark shows that a known mechanism can be recovered without automatically becoming a profit claim.

The protocol is ready for external methodological review. Its next decisive extension is application to an independent real market, not another internally selected robustness test.

## Project artifacts

The worked-example evidence is mapped in `paper/methods_claim_registry.json`. The executable contract is in `benchmark/SPEC.md`; the football reference and synthetic profile are validated through the benchmark workflows.