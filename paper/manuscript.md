# Abnormal Bookmaker Actions Predict Subsequent Repricing

## Residual information in multi-book football odds

**Draft version:** 0.1  
**Evidence status:** historical mechanism replicated; economic execution and untouched prospective transfer pending  
**Author line:** withheld in the public draft

## Abstract

Sports-betting research usually treats bookmaker odds as forecasts to be calibrated, combined or challenged. We study a different object: whether a bookmaker's *deviation from its own expected response to the contemporaneous market* contains incremental information about its subsequent repricing. For each bookmaker and horizon, a normal-action model predicts the next price response from the observable market state. The realized-minus-expected action becomes an abnormal-action residual. A raw closing-price model fixes the bookmaker and outcome candidate; residual information is then allowed only to rerank that same candidate universe.

The core historical evaluation contains 59,816 opportunities across 18,072 matches [C01_sample_scale]. Correct match-specific residual alignment beats all 4,000 baseline-preserving chronological circular-shift placebos for selected and incremental closing log-CLV (empirical upper-tail p=0.00025) [C02_placebo]. Across the full opportunity universe, a one-standard-deviation increase in residual uplift is associated with +0.004430 same-book closing log-CLV, with an event-cluster 95% interval of [+0.003316,+0.005515] [C03_dose_response]. The slope is positive for all eight tested bookmakers, all three selected outcomes and all four historical horizons, and remains positive with its lower confidence bound above zero after removing any one bookmaker [C04_broad_heterogeneity].

Economic conversion is much weaker. At matched 5% capacity, the residual policy has a +0.565% historical ROI versus -0.747% for the raw reference, but the relevant uncertainty intervals cross zero [C05_matched_return]. Residual-minus-raw point return is positive in 60 of 64 frozen execution cells, yet no preregistered practical envelope clears paired uncertainty and adversarial rejection removes standalone profitability [C06_execution]. Historical practical-envelope return is concentrated in home-selected opportunities [C07_outcome_concentration], while closing-line relative value remains positive across home, draw and away residual selections [C08_clv_return_bridge]. The evidence therefore supports a general repricing-information mechanism, not a validated betting strategy. A separately frozen seven-day prospective campaign tests transfer without altering the historical claim.

**Keywords:** bookmaker behavior; market microstructure; football odds; closing-line value; residual learning; falsification; prospective validation

## 1. Introduction

Bookmaker odds are simultaneously forecasts, prices and strategic responses to a competitive market. A large literature asks whether those prices are efficient, how margins should be removed, whether favorite-longshot bias remains, and whether combinations of bookmaker prices improve forecast accuracy. Classic work models football outcomes directly and compares model probabilities with offered odds. Other work treats quoted odds as market forecasts, studies bookmaker heterogeneity, or tests whether competitors' odds contain unused information.

This paper asks a narrower behavioral question. Suppose the contemporaneous market state implies that bookmaker \(b\) would normally move a particular way. If the bookmaker instead moves more, less, or in a different direction, does that *abnormal response* predict where the same bookmaker will later close?

The distinction matters. A bookmaker can display an informative price without displaying an informative *action residual*. Raw price levels may already summarize team strength, public information and broad consensus. The residual framework conditions on that observable state and focuses on the unexpected component of the bookmaker's response. Conceptually, it is closer to event-study abnormal returns or microstructure order-flow surprises than to a conventional match-outcome model.

The project makes four contributions.

1. It defines a bookmaker-action residual conditional on contemporaneous multi-book market state.
2. It fixes candidate identity with a raw model, so the residual model cannot manufacture gains by switching bookmakers or outcomes.
3. It subjects the mechanism to chronological placebos, threshold-free dose-response analysis, subgroup and leave-one-book-out tests, matched-capacity return analysis and explicit execution envelopes.
4. It separates historical discovery from a later untouched prospective campaign, with immutable ledgers and frozen gates.

The central result is deliberately asymmetric: the residual contains broad information about subsequent same-book repricing, while stable realized profit is not established.

## 2. Relation to prior work

The football-betting literature has repeatedly used market odds as probability forecasts and benchmarks. Dixon and Coles (1997) developed a dynamic score model and examined betting-market inefficiencies. Kuypers (2000) showed theoretically and empirically that bookmaker objectives can produce odds that are not informationally efficient. Graham and Stott (2008) studied prediction of bookmaker odds and UK football market efficiency. Štrumbelj (2014) compared methods for extracting probability forecasts from odds and documented meaningful differences across bookmakers. Angelini and De Angelis (2019) and Elaad, Reade and Singleton (2020) provided more recent evidence that efficiency varies across football markets and that competitors' prices may contain information not fully incorporated by individual bookmakers.

Our contribution differs in endpoint and construction. We do not primarily estimate the true probability of home, draw or away, and we do not begin by searching for a profitable outcome rule. We model the bookmaker's *conditional action*, calculate the residual between observed and expected action, and test whether that residual predicts later repricing after raw candidate identity is fixed. The economic tests are downstream diagnostics rather than the definition of the mechanism.

The design also draws on the logic behind market-microstructure surprise measures: an observed action is decomposed into a predictable component and an abnormal component. In betting markets, this decomposition is especially useful because quoted prices are strategic and bookmaker-specific rather than a single centralized transaction price.

## 3. Data and evidence boundary

### 3.1 Historical universe

The main historical matched-candidate evaluation contains 59,816 bookmaker/cutoff opportunities across 18,072 matches, covering 1 September through 19 November 2016 [C01_sample_scale]. Eight fixed bookmaker slots, three selected outcomes and four horizons—T-48, T-24, T-12 and T-6—are represented in the heterogeneity analysis.

The unit of analysis is an opportunity whose bookmaker and outcome identity is selected by the raw model. This identity is frozen before the residual uplift is used for ranking. At matched 5% capacity, each policy selects 2,988 opportunities. Outcomes are loaded only after policy flags and executable prices are bound.

### 3.2 Prospective boundary

The historical manuscript is intentionally complete before the prospective result is known. The live shadow bundle contains twelve bookmaker-identity-free models, pinned runtime versions and checksum-verified model files [C10_bundle_integrity]. Prospective scores are explicitly marked research-only and no-execution.

An outcome-blind domain-shift audit found two structural deployment differences: historical exact-cutoff timing versus broad prospective timing windows, and a historical peer-book scale larger than the current provider panel [C09_domain_shift]. The original prospective stream was preserved. Two separately activated challengers—strict support repair and canonical-timing normalization—were created instead of retroactively rewriting the original evidence.

## 4. Method

### 4.1 Expected bookmaker action

Let \(X_{b,t}\) denote the observable state for bookmaker \(b\) at time \(t\): own prices, contemporaneous consensus, peer-book coverage, timing and related market-state variables. A normal-action model estimates the bookmaker's next action,

\[
\widehat{A}_{b,t+1}=f(X_{b,t}).
\]

The observed action \(A_{b,t+1}\) is represented with hazard and conditional home/draw/away price-delta components. The abnormal-action residual is

\[
R_{b,t+1}=A_{b,t+1}-\widehat{A}_{b,t+1}.
\]

Conditional probability deltas are projected back to the probability simplex before residual formation. This scoring convention is locked by regression tests.

### 4.2 Raw and residual closing models

A raw closing model uses the contemporaneous market state to select a bookmaker/outcome candidate and assign a closing-move score. An augmented model receives the same state plus action-residual fields. The residual uplift is the difference between augmented and raw ranking information,

\[
U_i=S^{\mathrm{aug}}_i-S^{\mathrm{raw}}_i.
\]

The raw candidate identity is fixed. The residual policy may rerank opportunities but may not switch the selected bookmaker or selected outcome. This prevents a common attribution failure in which a more flexible model appears superior because it chooses a different object.

### 4.3 Primary endpoint

The primary mechanism endpoint is subsequent same-book closing-price quality, measured with closing log-CLV. Realized return is analyzed separately because match outcomes add substantial finite-sample variance and execution assumptions add a second conversion layer.

### 4.4 Falsification and robustness sequence

The mechanism is evaluated through a sequence designed to attack convenient explanations:

- baseline-preserving chronological circular-shift placebos;
- threshold-free within-stratum dose response;
- bookmaker, outcome and cutoff heterogeneity;
- leave-one-book-out analysis;
- equal-capacity raw-versus-residual comparison;
- delay, fill-rate and fill-mechanism execution envelopes;
- outcome attribution of price quality and realized return;
- outcome-blind historical-to-prospective domain-shift audit;
- untouched prospective transfer.

## 5. Historical results

### 5.1 Match-specific alignment survives placebo

The observed residual policy records an incremental selected log-CLV sum of +9.3142 relative to the fixed raw reference. In 4,000 fixed-seed placebos, residual uplift is circularly shifted only within chronological bookmaker-by-cutoff groups, preserving baseline scores, candidate identity, score distribution and exact 5% capacity. The correctly aligned residual beats all 4,000 placebos for both selected and incremental closing log-CLV; the empirical upper-tail p-value is 0.00025 [C02_placebo].

This is the cleanest evidence that the signal is attached to the correct match-specific bookmaker action rather than to the marginal distribution of residual scores.

### 5.2 The relationship is graded rather than threshold-created

Within cutoff, raw baseline scores are divided into 15 equal-count bins. Residual uplift is standardized and divided into ten dose bins within bookmaker-by-cutoff-by-baseline strata. The within-stratum slope is +0.004430 same-book closing log-CLV per one standard deviation of residual uplift, with event-cluster 95% interval [+0.003316,+0.005515] [C03_dose_response]. The highest-minus-lowest dose contrast is +0.014581, also with a lower confidence bound above zero. Both statistics beat every chronological placebo.

This result rules out an explanation based solely on a tuned top-5% cutoff. The relationship exists across the opportunity distribution.

### 5.3 The mechanism is broadly distributed

The closing log-CLV slope is positive for all eight bookmakers, all three raw-selected outcomes and all four historical horizons [C04_broad_heterogeneity]. After omitting each bookmaker in turn, every remaining global slope retains a positive event-cluster lower confidence bound. The most conservative leave-one-book-out estimate is +0.003803 with interval [+0.002493,+0.005087].

The mechanism is therefore not reducible to one bookmaker, one outcome identity or one cutoff. This broad price-quality stability contrasts with the return results below.

### 5.4 Matched-capacity return is promising but uncertain

At exact 5% capacity within cutoff, the raw reference loses 22.31 units for an ROI of -0.747%, while the residual policy gains 16.89 units for an ROI of +0.565% [C05_matched_return]. The residual-minus-raw point improvement is +39.20 units. The residual is positive at T-48, T-24 and T-12, and negative at T-6.

Neither the residual standalone ROI interval nor the paired incremental interval clears zero. The point estimate is economically encouraging only in an informal sense; the frozen diagnostic gate remains false.

### 5.5 Execution consumes the thin economic margin

A 64-cell grid crosses four delays, four exact fill rates and four outcome-blind fill mechanisms. Residual-minus-raw point return is positive in 60 cells, compared with positive residual standalone ROI in 18 cells and positive raw standalone ROI in six [C06_execution].

The four preregistered practical envelopes use one-hour delay, 90% fill and 25 basis points of common slippage. Incremental point return remains positive in all four, but every paired confidence interval crosses zero. Common-random fill and bookmaker-clustered outages retain small positive residual standalone ROI; adverse-move rejection and highest-edge rejection make it negative. The mechanism's ranking advantage is broad, while its executable margin is thin and vulnerable to informed non-fill.

### 5.6 Price quality and realized return diverge by outcome

Home-selected opportunities produce positive residual-minus-raw realized point return in all four practical mechanisms. Draw is negative in all four, and away is positive in only one. Removing home makes the combined non-home uplift negative in three of four mechanisms [C07_outcome_concentration]. This attribution is post hoc and cannot authorize a home-only policy.

The closing-line bridge adds an important qualification. Residual standalone closing-line relative value is positive for home, draw and away in all four mechanisms, and all 12 residual outcome-by-mechanism bootstrap lower bounds exceed zero [C08_clv_return_bridge]. Incremental away closing value is positive in all four mechanisms even though incremental realized return is negative in three. Draw is the only outcome with consistently negative incremental point estimates on both dimensions.

The historical home concentration is therefore partly price-quality structure and partly finite outcome realization. A broad repricing signal can coexist with narrow realized-return concentration.

## 6. Summary table

| Question | Frozen result | Evidentiary implication |
|---|---:|---|
| Does correct residual alignment matter? | 4,000/4,000 placebos beaten; p=0.00025 | Strong historical mechanism evidence |
| Is the effect created by the top-5% threshold? | One-SD slope +0.004430; 95% CI [+0.003316,+0.005515] | Threshold-free dose response |
| Is it one bookmaker or horizon? | Positive 8/8 books, 3/3 outcomes, 4/4 cutoffs | Broad historical distribution |
| Does it improve matched historical return? | +0.565% residual vs -0.747% raw | Positive point estimate, uncertain |
| Does it survive execution stress? | Positive incremental point estimate in 60/64 cells | Ranking survives broadly; margin is thin |
| Is economic value broad by outcome? | Home 4/4, draw 0/4, away 1/4 mechanisms | Realized uplift is concentrated |
| Is price quality also home-only? | Residual standalone closing value positive in 12/12 cells | No; price quality is broader than return |
| Is future transfer established? | Prospective campaign in progress | Pending |

## 7. Prospective test

The prospective campaign is not a seventh historical robustness check. It is the first clean transfer test after model and policy construction. Near-event 1X2 snapshots are collected every three hours, transformed into leakage-safe three-snapshot chains and scored without match outcomes. Candidate ledgers are written and hashed before closing targets are read.

The original stream and both domain-shift challengers have independent activation times and campaign-close evaluators. The original matched-budget evaluator requires, among other fixed gates, at least 300 candidates, 75 events, at least 15 selections per policy and at least three cutoffs with 40 candidates. Failure to reach volume remains a failed or inconclusive confirmatory test; the threshold cannot be lowered after observation.

### Reserved prospective result block

This block is intentionally left unfilled in version 0.1.

- Campaign close: 26 July 2026, 06:30 UTC.
- Primary transfer endpoint: residual-minus-raw same-book closing-price quality under the frozen matched-budget design.
- Secondary diagnostics: cutoff stability, event-cluster uncertainty, concentration, adapter agreement and practical execution simulations.
- Prohibited inference: a one-week positive result alone does not establish scalable live profitability.

## 8. Discussion

The historical evidence is unusually consistent on the price-quality mechanism and unusually cautious on economics. That combination is substantively useful. Many market-prediction projects treat a positive backtest as both mechanism and business case. Here, the mechanism survives tests that deliberately preserve easy structure while breaking match-specific residual alignment. Yet the profit claim fails because outcome variance, latency, slippage and adverse fill are distinct problems.

The findings suggest that bookmaker actions may reveal information beyond static odds levels. A bookmaker's unexpected response to the market can be informative even after the raw state has selected the candidate. This does not require the bookmaker to possess literal private information. The residual may reflect superior internal models, customer-flow information, risk management, faster data, differing liabilities or a mixture of these channels. The current design identifies predictive residual information, not its institutional source.

The divergence between closing value and realized return is also important. Closing-price quality is not automatically profit, but it is a lower-variance diagnostic of whether the selected price subsequently improves relative to the same bookmaker. The away result demonstrates how a directionally better price-quality signal can fail to appear in a finite realized-return sample. Conversely, a lucky return without price-quality support would deserve skepticism.

## 9. Limitations

First, the strongest completed evidence remains historical. Repeated historical analysis can expose alternative explanations but cannot substitute for untouched future transfer.

Second, the main historical period is finite and may not represent current bookmaker technology, market composition or limits. The prospective domain-shift audit already identifies meaningful timing and source-breadth differences [C09_domain_shift].

Third, closing-line value is a diagnostic relative to later quoted prices, not a guarantee of positive expected return after margin removal, latency, limits and account restrictions.

Fourth, fill mechanisms are simulations. Real-world rejection, stake limits, price movement during submission and account survival require separate prospective execution evidence.

Fifth, the outcome-attribution analyses were specified after concentration was observed. Their role is diagnosis and future hypothesis generation, not retrospective strategy authorization.

## 10. Conclusion

Abnormal bookmaker-action residuals contain broad historical information about subsequent same-book repricing. The effect survives baseline-preserving chronological placebos, appears as a graded dose response, spans bookmakers, outcomes and horizons, and remains after removing any one bookmaker. Economic conversion is thinner: matched historical return improves, but uncertainty crosses zero; practical execution margins are small; adversarial non-fill is damaging; and realized uplift is concentrated in home selections.

The defensible conclusion is therefore precise. The project has identified a replicated historical repricing-information mechanism. It has not established stable profit, scalable execution or prospective transfer. The frozen future campaign determines whether the mechanism survives its first untouched deployment test; it does not retroactively change the historical result.

## References

Angelini, G., & De Angelis, L. (2019). Efficiency of online football betting markets. *International Journal of Forecasting, 35*(2), 712–721. https://doi.org/10.1016/j.ijforecast.2018.07.008

Dixon, M. J., & Coles, S. G. (1997). Modelling association football scores and inefficiencies in the football betting market. *Journal of the Royal Statistical Society: Series C, 46*(2), 265–280. https://doi.org/10.1111/1467-9876.00065

Elaad, G., Reade, J. J., & Singleton, C. (2020). Information, prices and efficiency in an online betting market. *Finance Research Letters, 35*, 101291. https://doi.org/10.1016/j.frl.2019.09.006

Graham, I., & Stott, H. (2008). Predicting bookmaker odds and efficiency for UK football. *Applied Economics, 40*(1), 99–109. https://doi.org/10.1080/00036840701728799

Kuypers, T. (2000). Information and efficiency: an empirical study of a fixed odds betting market. *Applied Economics, 32*(11), 1353–1363. https://doi.org/10.1080/00036840050151449

Shin, H. S. (1993). Measuring the incidence of insider trading in a market for state-contingent claims. *The Economic Journal, 103*(420), 1141–1153. https://doi.org/10.2307/2234240

Štrumbelj, E. (2014). On determining probability forecasts from betting odds. *International Journal of Forecasting, 30*(4), 934–943. https://doi.org/10.1016/j.ijforecast.2014.02.008
