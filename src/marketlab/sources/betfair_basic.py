from __future__ import annotations

import bz2
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator


@dataclass(frozen=True, slots=True)
class BetfairLtpChange:
    publish_time_ms: int
    market_id: str
    selection_id: int
    last_traded_price: float
    market_status: str | None = None
    in_play: bool | None = None


def iter_messages_from_bz2(path: str | Path) -> Iterator[dict[str, Any]]:
    """Yield newline-delimited Exchange Stream messages from a Betfair historical .bz2 file."""
    with bz2.open(path, mode="rt", encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_number}") from exc
            if not isinstance(payload, dict):
                raise ValueError(f"Expected JSON object at {path}:{line_number}")
            yield payload


def extract_ltp_changes(messages: Iterable[dict[str, Any]]) -> Iterator[BetfairLtpChange]:
    """Extract last-traded-price changes from Exchange market-change messages.

    The parser intentionally ignores fields it does not understand so it can survive package/schema
    additions. Market definition state is carried forward only within each message; production replay
    code may later maintain a fuller cache when needed.
    """
    for message in messages:
        pt = message.get("pt")
        market_changes = message.get("mc")
        if not isinstance(pt, int) or not isinstance(market_changes, list):
            continue

        for market_change in market_changes:
            if not isinstance(market_change, dict):
                continue
            market_id = market_change.get("id")
            if not isinstance(market_id, str):
                continue

            market_definition = market_change.get("marketDefinition") or {}
            market_status = market_definition.get("status") if isinstance(market_definition, dict) else None
            in_play = market_definition.get("inPlay") if isinstance(market_definition, dict) else None

            runner_changes = market_change.get("rc") or []
            if not isinstance(runner_changes, list):
                continue
            for runner_change in runner_changes:
                if not isinstance(runner_change, dict):
                    continue
                selection_id = runner_change.get("id")
                ltp = runner_change.get("ltp")
                if not isinstance(selection_id, int) or not isinstance(ltp, (int, float)):
                    continue
                yield BetfairLtpChange(
                    publish_time_ms=pt,
                    market_id=market_id,
                    selection_id=selection_id,
                    last_traded_price=float(ltp),
                    market_status=market_status if isinstance(market_status, str) else None,
                    in_play=in_play if isinstance(in_play, bool) else None,
                )
