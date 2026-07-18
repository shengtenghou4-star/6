# Beat The Bookie — Primary-Source Tensor Semantics

This document freezes semantics verified from the original authors' public source code in `Lisandro79/BeatTheBookie`, not inferred from the Kaggle column names alone.

## Time axis

The generator creates hourly markers from `match_time - 0h` through `match_time - 71h`, sorts all odds updates and markers chronologically, then samples the latest known state at each marker.

Therefore the derived wide tensor is ordered **early to late**:

- `time_index = 0` → approximately **T-71h**
- `time_index = 1` → approximately **T-70h**
- ...
- `time_index = 70` → approximately **T-1h**
- `time_index = 71` → approximately **T-0h / kickoff marker**

Canonical conversion:

`hours_before_kickoff = 71 - time_index`

This interpretation is also strongly consistent with the acquired data: aggregate quote coverage rises almost monotonically from index 0 to 71 (Pearson correlation ≈ 0.990).

## Bookmaker-slot mapping

The original generator source defines a fixed 32-row bookmaker mapping. The Kaggle wide tensor's `b1`–`b32` slots correspond to those rows in order:

| Slot | Source bookmaker label(s) |
|---|---|
| b1 | Interwetten |
| b2 | bwin |
| b3 | bet-at-home |
| b4 | Unibet |
| b5 | Stan James |
| b6 | Expekt |
| b7 | 10Bet |
| b8 | William Hill |
| b9 | bet365 |
| b10 | Pinnacle Sports / Pinnacle |
| b11 | DOXXbet |
| b12 | Betsafe |
| b13 | Betway |
| b14 | 888sport |
| b15 | Ladbrokes |
| b16 | Betclic |
| b17 | Sportingbet |
| b18 | myBet / mybet |
| b19 | Betsson |
| b20 | 188BET |
| b21 | Jetbull |
| b22 | Paddy Power |
| b23 | Tipico |
| b24 | Coral |
| b25 | SBOBET |
| b26 | BetVictor |
| b27 | 12BET |
| b28 | Titanbet |
| b29 | youwin |
| b30 | ComeOn |
| b31 | Betadonis |
| b32 | Betfair Sports / Betfair |

The labels above are historical source labels. They must not be silently rewritten to present-day corporate identities or assumed to represent uninterrupted modern operators.

## Tensor layout

For each match row:

- identity/result prefix: `match_id`, `match_date`, `match_time`, `score_home`, `score_away`
- then 6,912 odds cells = `32 bookmakers × 3 outcomes × 72 hourly indices`
- outcomes: `home`, `draw`, `away`

The original source code and unpacker confirm that each bookmaker contributes a 72×3 block in the fixed source bookmaker order.

## Important limitation

The wide Kaggle tensor is a **derived hourly state representation**, not the raw exact-update history. The original SQL schema contains named bookmakers and exact `odds_datetime` updates. Recovering those SQL dumps remains preferable for final normal-behavior modeling if the original public archives are still obtainable.

## Primary-source references

- https://github.com/Lisandro79/BeatTheBookie
- original generator: `generate_odds_series_csv.php`
- original unpacker: `unpack.py`

Any future transformation that changes the slot mapping or time-axis convention must cite new primary-source evidence and record the change in the decision log.