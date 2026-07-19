from __future__ import annotations

import pandas as pd
import pytest

from marketlab.home_only_power_forecast import filter_home_forecast_candidates


def candidates() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "event_id": ["e1", "e2", "e3", "e4"],
            "realized_snapshot_id": ["s1", "s1", "s2", "s3"],
            "realized_snapshot_ingested_at": [
                "2026-07-19T14:59:00Z",
                "2026-07-19T15:01:00Z",
                "2026-07-19T15:02:00Z",
                "2026-07-19T15:03:00Z",
            ],
            "raw_candidate_outcome": ["home", "home", "draw", "home"],
        }
    )


def test_filters_home_and_reports_future_only_volume() -> None:
    filtered, diagnostics = filter_home_forecast_candidates(candidates())
    assert filtered["event_id"].tolist() == ["e1", "e2", "e4"]
    assert diagnostics["source_rows"] == 4
    assert diagnostics["home_rows_all_times"] == 3
    assert diagnostics["home_rows_post_activation"] == 2
    assert diagnostics["home_events_post_activation"] == 2
    assert diagnostics["home_snapshots_post_activation"] == 2
    assert diagnostics["filter_applied_before_forecast"] is True
    assert diagnostics["performance_fields_used"] is False


def test_rejects_unknown_outcomes() -> None:
    frame = candidates()
    frame.loc[0, "raw_candidate_outcome"] = "other"
    with pytest.raises(ValueError, match="unexpected candidate outcomes"):
        filter_home_forecast_candidates(frame)


def test_rejects_invalid_timestamps() -> None:
    frame = candidates()
    frame.loc[0, "realized_snapshot_ingested_at"] = "not-a-time"
    with pytest.raises(ValueError, match="invalid ingestion timestamps"):
        filter_home_forecast_candidates(frame)
