from __future__ import annotations

import pandas as pd
import pytest

from marketlab.prospective_adapter_coverage import audit_adapter_coverage


def frame(ids: list[tuple[str, str]], *, score_shift: float = 0.0) -> pd.DataFrame:
    rows = []
    for index, (event, snapshot) in enumerate(ids):
        rows.append(
            {
                "event_id": event,
                "realized_snapshot_id": snapshot,
                "realized_snapshot_ingested_at": "2026-07-19T15:10:00Z",
                "supported_closing_cutoff_hours": 24,
                "bookmaker_key": f"b{index % 2}",
                "raw_candidate_outcome": "home" if index % 2 == 0 else "away",
                "raw_candidate_score": float(index + 1 + score_shift),
                "action_rank_score_for_raw_candidate": float(index + 2 + score_shift),
            }
        )
    return pd.DataFrame(rows)


def test_reports_common_boundary_and_pair_overlap() -> None:
    original = frame([("e1", "s1"), ("e2", "s1"), ("e3", "s2")])
    support = frame([("e1", "s1")], score_shift=0.1)
    canonical = frame([("e1", "s1"), ("e2", "s1")], score_shift=0.2)
    result, streams = audit_adapter_coverage(
        original,
        support,
        canonical,
        "2026-07-19T15:00:00Z",
    )
    assert result["streams"]["original"]["rows"] == 3
    assert result["streams"]["support_repaired"]["rows"] == 1
    assert result["streams"]["canonical_timing"]["rows"] == 2
    assert result["pairs"]["support_vs_canonical"]["intersection"] == 1
    assert result["pairs"]["original_vs_canonical"]["right_only"] == 0
    assert result["coverage"]["canonical_minus_support_rows"] == 1
    assert len(streams["canonical_timing"]) == 2


def test_excludes_pre_common_activation_rows() -> None:
    original = frame([("e1", "s1")])
    original["realized_snapshot_ingested_at"] = "2026-07-19T14:59:59Z"
    support = frame([("e1", "s1")])
    canonical = frame([("e1", "s1")])
    result, _ = audit_adapter_coverage(
        original,
        support,
        canonical,
        "2026-07-19T15:00:00Z",
    )
    assert result["streams"]["original"]["rows"] == 0
    assert result["streams"]["support_repaired"]["rows"] == 1


def test_rejects_forbidden_evidence_columns() -> None:
    original = frame([("e1", "s1")])
    original["won"] = False
    with pytest.raises(ValueError, match="forbidden"):
        audit_adapter_coverage(
            original,
            frame([("e1", "s1")]),
            frame([("e1", "s1")]),
            "2026-07-19T15:00:00Z",
        )


def test_rejects_duplicate_identity() -> None:
    original = pd.concat(
        [frame([("e1", "s1")]), frame([("e1", "s1")])],
        ignore_index=True,
    )
    with pytest.raises(ValueError, match="duplicate"):
        audit_adapter_coverage(
            original,
            frame([("e1", "s1")]),
            frame([("e1", "s1")]),
            "2026-07-19T15:00:00Z",
        )
