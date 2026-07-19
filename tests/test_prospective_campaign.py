from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from marketlab.prospective_campaign import (
    CampaignPolicy,
    campaign_window_active,
    select_near_event_sports,
    utc_iso,
)


def event(event_id: str, commence: datetime) -> dict[str, str]:
    return {
        "id": event_id,
        "commence_time": utc_iso(commence),
    }


def test_selects_at_most_four_active_near_event_sports_deterministically() -> None:
    now = datetime(2026, 7, 19, 6, 0, tzinfo=UTC)
    sports = (
        "sport_a",
        "sport_b",
        "sport_c",
        "sport_d",
        "sport_e",
        "sport_f",
    )
    policy = CampaignPolicy(
        sports=sports,
        maximum_paid_sports_per_run=4,
        horizon_hours=60,
        maximum_paid_credits_per_run=4,
    )
    payloads = {
        "sport_a": [event("a1", now + timedelta(hours=50)) for _ in range(1)],
        "sport_b": [
            event(f"b{i}", now + timedelta(hours=12 + i)) for i in range(3)
        ],
        "sport_c": [
            event(f"c{i}", now + timedelta(hours=30 + i)) for i in range(4)
        ],
        "sport_d": [
            event(f"d{i}", now + timedelta(hours=48 + i)) for i in range(5)
        ],
        "sport_e": [event("e1", now + timedelta(hours=2))],
        "sport_f": [event("f1", now + timedelta(hours=90))],
    }
    selected = select_near_event_sports(
        active_sport_keys=sports,
        events_by_sport=payloads,
        now=now,
        policy=policy,
    )
    assert [item.sport_key for item in selected] == [
        "sport_b",
        "sport_c",
        "sport_d",
        "sport_e",
    ]
    assert all(item.event_count >= 1 for item in selected)
    assert all(item.minimum_hours_to_commence <= 60 for item in selected)


def test_inactive_invalid_past_and_out_of_horizon_events_are_excluded() -> None:
    now = datetime(2026, 7, 19, 6, 0, tzinfo=UTC)
    policy = CampaignPolicy(
        sports=("active", "inactive", "bad"),
        maximum_paid_sports_per_run=3,
        maximum_paid_credits_per_run=3,
    )
    selected = select_near_event_sports(
        active_sport_keys=("active", "bad"),
        events_by_sport={
            "active": [
                event("past", now - timedelta(minutes=1)),
                event("valid", now + timedelta(hours=8)),
                event("far", now + timedelta(hours=61)),
            ],
            "inactive": [event("inactive-event", now + timedelta(hours=2))],
            "bad": [{"id": "bad-time", "commence_time": "not-a-time"}],
        },
        now=now,
        policy=policy,
    )
    assert [item.sport_key for item in selected] == ["active"]
    assert selected[0].event_ids == ("valid",)


def test_campaign_window_is_half_open_and_timezone_aware() -> None:
    start = datetime(2026, 7, 19, 0, 0, tzinfo=UTC)
    end = datetime(2026, 7, 26, 0, 0, tzinfo=UTC)
    assert campaign_window_active(start, start=start, end=end)
    assert campaign_window_active(end - timedelta(seconds=1), start=start, end=end)
    assert not campaign_window_active(end, start=start, end=end)
    with pytest.raises(ValueError, match="timezone-aware"):
        campaign_window_active(
            datetime(2026, 7, 20), start=start, end=end
        )


def test_policy_rejects_scope_and_budget_drift() -> None:
    with pytest.raises(ValueError, match="h2h"):
        CampaignPolicy(market="spreads")
    with pytest.raises(ValueError, match="exactly one region"):
        CampaignPolicy(region="uk,eu")
    with pytest.raises(ValueError, match="credit ceiling"):
        CampaignPolicy(
            maximum_paid_sports_per_run=4,
            maximum_paid_credits_per_run=3,
        )
