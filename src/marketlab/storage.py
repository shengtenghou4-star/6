from __future__ import annotations

import gzip
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def payload_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def write_raw_json_gz(
    root: str | Path,
    *,
    source: str,
    dataset: str,
    payload: Any,
    observed_at: datetime | None = None,
) -> Path:
    """Write immutable raw payloads using content hashes to make deduplication auditable."""
    observed_at = observed_at or utc_now()
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    observed_at = observed_at.astimezone(timezone.utc)
    digest = payload_sha256(payload)
    folder = Path(root) / "raw" / source / dataset / observed_at.strftime("%Y/%m/%d")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{observed_at.strftime('%H%M%S_%f')}_{digest[:16]}.json.gz"
    if path.exists():
        return path
    envelope = {
        "source": source,
        "dataset": dataset,
        "observed_at": observed_at.isoformat(),
        "sha256": digest,
        "payload": payload,
    }
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        json.dump(envelope, fh, ensure_ascii=False, sort_keys=True)
    return path
