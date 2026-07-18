from __future__ import annotations

import bz2
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


@dataclass(frozen=True, slots=True)
class BetfairMarketUpdate:
    publish_time: datetime
    market_id: str
    event_id: str | None
    event_name: str | None
    market_type: str | None
    market_time: str | None
    market_status: str | None
    in_play: bool | None
    runner_id: int | None
    runner_name: str | None
    last_traded_price: float | None
    runner_total_matched: float | None
    available_to_back: list[list[float]] | None
    available_to_lay: list[list[float]] | None
    traded_volume: list[list[float]] | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["publish_time"] = self.publish_time.isoformat()
        return data


def publish_time_from_ms(value: int) -> datetime:
    if not isinstance(value, int) or value <= 0:
        raise ValueError("Betfair publish time `pt` must be a positive integer in milliseconds")
    return datetime.fromtimestamp(value / 1000.0, tz=timezone.utc)


def _coerce_price_ladder(value: Any) -> list[list[float]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("price ladder must be a list")
    result: list[list[float]] = []
    for row in value:
        if not isinstance(row, list):
            raise ValueError("price ladder rows must be lists")
        try:
            result.append([float(item) for item in row])
        except (TypeError, ValueError) as exc:
            raise ValueError("price ladder entries must be numeric") from exc
    return result


def _runner_names(definition: dict[str, Any]) -> dict[int, str]:
    result: dict[int, str] = {}
    runners = definition.get("runners")
    if not isinstance(runners, list):
        return result
    for runner in runners:
        if not isinstance(runner, dict):
            continue
        runner_id = runner.get("id")
        name = runner.get("name")
        if isinstance(runner_id, int) and isinstance(name, str):
            result[runner_id] = name
    return result


def _flatten_market_change(
    *,
    publish_time: datetime,
    market_change: dict[str, Any],
    definition: dict[str, Any],
) -> list[BetfairMarketUpdate]:
    market_id = market_change.get("id")
    if not isinstance(market_id, str) or not market_id:
        raise ValueError("market change missing market id")

    event_id = definition.get("eventId") if isinstance(definition.get("eventId"), str) else None
    event_name = definition.get("eventName") if isinstance(definition.get("eventName"), str) else None
    market_type = definition.get("marketType") if isinstance(definition.get("marketType"), str) else None
    market_time = definition.get("marketTime") if isinstance(definition.get("marketTime"), str) else None
    market_status = definition.get("status") if isinstance(definition.get("status"), str) else None
    in_play = definition.get("inPlay") if isinstance(definition.get("inPlay"), bool) else None
    runner_names = _runner_names(definition)

    runner_changes = market_change.get("rc")
    if runner_changes is None:
        return [
            BetfairMarketUpdate(
                publish_time=publish_time,
                market_id=market_id,
                event_id=event_id,
                event_name=event_name,
                market_type=market_type,
                market_time=market_time,
                market_status=market_status,
                in_play=in_play,
                runner_id=None,
                runner_name=None,
                last_traded_price=None,
                runner_total_matched=None,
                available_to_back=None,
                available_to_lay=None,
                traded_volume=None,
            )
        ]
    if not isinstance(runner_changes, list):
        raise ValueError("runner-change field `rc` must be a list")

    output: list[BetfairMarketUpdate] = []
    for runner_change in runner_changes:
        if not isinstance(runner_change, dict):
            raise ValueError("runner change entries must be objects")
        runner_id = runner_change.get("id")
        if runner_id is not None and not isinstance(runner_id, int):
            raise ValueError("runner id must be integer when present")
        ltp = runner_change.get("ltp")
        tv = runner_change.get("tv")
        output.append(
            BetfairMarketUpdate(
                publish_time=publish_time,
                market_id=market_id,
                event_id=event_id,
                event_name=event_name,
                market_type=market_type,
                market_time=market_time,
                market_status=market_status,
                in_play=in_play,
                runner_id=runner_id,
                runner_name=runner_names.get(runner_id) if runner_id is not None else None,
                last_traded_price=float(ltp) if ltp is not None else None,
                runner_total_matched=float(tv) if tv is not None else None,
                available_to_back=_coerce_price_ladder(runner_change.get("batb")),
                available_to_lay=_coerce_price_ladder(runner_change.get("batl")),
                traded_volume=_coerce_price_ladder(runner_change.get("trd")),
            )
        )
    return output


class BetfairStreamNormalizer:
    """Stateful normalizer for Betfair's incremental Exchange Stream messages.

    Market definitions are not repeated on every price update. Retaining the latest
    definition per market is therefore required to attach stable event/market/runner
    identity to later runner-change messages without inventing data.
    """

    def __init__(self) -> None:
        self._definitions: dict[str, dict[str, Any]] = {}

    def consume(self, message: dict[str, Any]) -> list[BetfairMarketUpdate]:
        if message.get("op") != "mcm":
            return []
        publish_time = publish_time_from_ms(message.get("pt"))
        market_changes = message.get("mc")
        if not isinstance(market_changes, list):
            raise ValueError("Betfair market-change message must contain list field `mc`")

        output: list[BetfairMarketUpdate] = []
        for market_change in market_changes:
            if not isinstance(market_change, dict):
                raise ValueError("market change entries must be objects")
            market_id = market_change.get("id")
            if not isinstance(market_id, str) or not market_id:
                raise ValueError("market change missing market id")

            incoming_definition = market_change.get("marketDefinition")
            if incoming_definition is not None and not isinstance(incoming_definition, dict):
                raise ValueError("marketDefinition must be an object when present")
            if isinstance(incoming_definition, dict):
                # Market definitions are snapshots of the definition state. Keep the newest
                # snapshot intact rather than trying to infer undocumented patch semantics.
                self._definitions[market_id] = dict(incoming_definition)

            definition = self._definitions.get(market_id, {})
            output.extend(
                _flatten_market_change(
                    publish_time=publish_time,
                    market_change=market_change,
                    definition=definition,
                )
            )
        return output


def flatten_market_change_message(message: dict[str, Any]) -> list[BetfairMarketUpdate]:
    """Stateless helper for one self-contained message.

    For real historical files prefer :class:`BetfairStreamNormalizer`, because later
    price updates commonly omit ``marketDefinition``.
    """

    return BetfairStreamNormalizer().consume(message)


def iter_json_messages(lines: Iterable[str]) -> Iterator[dict[str, Any]]:
    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON on Betfair historical line {line_number}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"Betfair historical line {line_number} must contain a JSON object")
        yield payload


def iter_bz2_messages(path: str | Path) -> Iterator[dict[str, Any]]:
    with bz2.open(Path(path), "rt", encoding="utf-8") as fh:
        yield from iter_json_messages(fh)


def iter_bz2_updates(path: str | Path) -> Iterator[BetfairMarketUpdate]:
    normalizer = BetfairStreamNormalizer()
    for message in iter_bz2_messages(path):
        yield from normalizer.consume(message)
