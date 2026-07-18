from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import requests


SOURCES = {
    "odds_series_sql_db": "https://www.dropbox.com/s/sftxhxq03jd12j6/odds_series_sql_db.zip?dl=1",
    "odds_series_b_sql_db": "https://www.dropbox.com/s/x6aookfjw25ne6q/odds_series_b_sql_db.zip?dl=1",
}


def probe(name: str, url: str, *, timeout: float = 60.0) -> dict[str, Any]:
    headers = {"Range": "bytes=0-1023", "User-Agent": "marketlab-source-audit/1.0"}
    try:
        with requests.get(url, headers=headers, stream=True, timeout=timeout, allow_redirects=True) as response:
            prefix = b""
            for chunk in response.iter_content(chunk_size=1024):
                if chunk:
                    prefix += chunk
                if len(prefix) >= 1024:
                    break
            return {
                "name": name,
                "requested_url": url,
                "status_code": response.status_code,
                "final_url": str(response.url),
                "content_type": response.headers.get("content-type"),
                "content_length": response.headers.get("content-length"),
                "content_range": response.headers.get("content-range"),
                "accept_ranges": response.headers.get("accept-ranges"),
                "content_disposition": response.headers.get("content-disposition"),
                "prefix_hex": prefix[:32].hex(),
                "zip_signature": prefix.startswith(b"PK"),
                "bytes_sampled": len(prefix),
            }
    except Exception as exc:
        return {
            "name": name,
            "requested_url": url,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe original BeatTheBookie SQL archive links without blind full downloads.")
    parser.add_argument("--output", default="artifacts/beat-original-sql-probe/probe_report.json")
    args = parser.parse_args()

    report = {
        "sources": [probe(name, url) for name, url in SOURCES.items()],
        "note": "A successful HTTP response or ZIP prefix proves link reachability only; exact-update SQL is not counted as acquired until a complete archive is downloaded, checksummed and opened.",
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
