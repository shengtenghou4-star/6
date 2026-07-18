from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any

import requests


FIGSHARE_API = "https://api.figshare.com/v2"
COLLECTION_ID = 4415000
TARGET_TITLES = {
    "events",
    "matches",
    "players",
    "teams",
    "coaches",
    "competitions",
    "referees",
    "mapping of tag identifiers to tag names",
}


def slug(value: str) -> str:
    value = value.strip().casefold()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "item"


def get_json(url: str, *, timeout: float = 60.0) -> Any:
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    return response.json()


def download_file(url: str, path: Path, *, expected_size: int | None = None, timeout: float = 600.0) -> dict[str, Any]:
    digest = hashlib.sha256()
    path.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
                if not chunk:
                    continue
                digest.update(chunk)
                total += len(chunk)
                fh.write(chunk)
    if expected_size is not None and expected_size != total:
        raise ValueError(f"download size mismatch for {url}: got {total}, expected {expected_size}")
    return {"path": str(path), "bytes": total, "sha256": digest.hexdigest()}


def profile_json_bytes(content: bytes, source_name: str) -> dict[str, Any]:
    payload = json.loads(content.decode("utf-8-sig"))
    if isinstance(payload, list):
        return {"source_name": source_name, "format": "json", "root_type": "list", "records": len(payload)}
    if isinstance(payload, dict):
        return {"source_name": source_name, "format": "json", "root_type": "object", "keys": len(payload)}
    return {"source_name": source_name, "format": "json", "root_type": type(payload).__name__}


def profile_csv_bytes(content: bytes, source_name: str) -> dict[str, Any]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    return {
        "source_name": source_name,
        "format": "csv",
        "rows_including_header": len(rows),
        "columns": len(rows[0]) if rows else 0,
    }


def profile_file(path: Path) -> dict[str, Any]:
    suffix = path.suffix.casefold()
    failures: list[dict[str, str]] = []
    members: list[dict[str, Any]] = []
    if suffix == ".zip":
        with zipfile.ZipFile(path) as zf:
            for info in sorted(zf.infolist(), key=lambda item: item.filename):
                if info.is_dir():
                    continue
                name = info.filename
                lower = name.casefold()
                try:
                    content = zf.read(info)
                    if lower.endswith(".json"):
                        members.append(profile_json_bytes(content, name))
                    elif lower.endswith(".csv"):
                        members.append(profile_csv_bytes(content, name))
                    else:
                        members.append({"source_name": name, "format": "other", "bytes": len(content)})
                except Exception as exc:
                    failures.append({"source_name": name, "error_type": type(exc).__name__, "error": str(exc)})
        return {"format": "zip", "members": members, "parse_failures": failures}

    content = path.read_bytes()
    try:
        if suffix == ".json":
            return {"format": "json_file", "members": [profile_json_bytes(content, path.name)], "parse_failures": []}
        if suffix == ".csv":
            return {"format": "csv_file", "members": [profile_csv_bytes(content, path.name)], "parse_failures": []}
    except Exception as exc:
        failures.append({"source_name": path.name, "error_type": type(exc).__name__, "error": str(exc)})
    return {"format": suffix.lstrip(".") or "other", "members": [], "parse_failures": failures}


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire and profile the public Wyscout-derived Figshare soccer dataset.")
    parser.add_argument("--output-root", default="artifacts/wyscout-open")
    parser.add_argument("--collection-id", type=int, default=COLLECTION_ID)
    args = parser.parse_args()

    root = Path(args.output_root)
    raw_root = root / "raw"
    root.mkdir(parents=True, exist_ok=True)

    collection_url = f"{FIGSHARE_API}/collections/{args.collection_id}"
    articles_url = f"{FIGSHARE_API}/collections/{args.collection_id}/articles?page_size=100"
    collection = get_json(collection_url)
    articles = get_json(articles_url)
    if not isinstance(articles, list):
        raise SystemExit("Figshare collection article listing was not a list")

    selected = [article for article in articles if isinstance(article, dict) and str(article.get("title", "")).strip().casefold() in TARGET_TITLES]
    if not selected:
        raise SystemExit("no target Wyscout collection articles discovered")

    manifest: dict[str, Any] = {
        "collection_id": args.collection_id,
        "collection_url": collection_url,
        "collection_title": collection.get("title") if isinstance(collection, dict) else None,
        "licence_note": "Collection items are public research data; preserve each article's licence/citation metadata and do not treat post-match events as pre-match-known features.",
        "discovered_articles": len(articles),
        "selected_articles": [],
        "download_failures": [],
    }

    total_bytes = 0
    total_profiled_records = 0
    total_parse_failures = 0

    for article in sorted(selected, key=lambda item: str(item.get("title", ""))):
        article_id = article.get("id")
        title = str(article.get("title", ""))
        if not isinstance(article_id, int):
            manifest["download_failures"].append({"title": title, "error": "missing integer article id"})
            continue
        try:
            detail = get_json(f"{FIGSHARE_API}/articles/{article_id}")
            files = detail.get("files") if isinstance(detail, dict) else None
            if not isinstance(files, list) or not files:
                raise ValueError("article has no downloadable files")
            article_entry: dict[str, Any] = {
                "article_id": article_id,
                "title": title,
                "doi": detail.get("doi"),
                "url_public_api": detail.get("url_public_api"),
                "license": detail.get("license"),
                "files": [],
            }
            for file_info in files:
                if not isinstance(file_info, dict):
                    continue
                file_name = str(file_info.get("name") or f"file-{file_info.get('id')}")
                download_url = file_info.get("download_url")
                if not isinstance(download_url, str) or not download_url:
                    raise ValueError(f"file lacks download_url: {file_name}")
                target = raw_root / slug(title) / file_name
                meta = download_file(download_url, target, expected_size=file_info.get("size") if isinstance(file_info.get("size"), int) else None)
                profile = profile_file(target)
                record_count = sum(int(member.get("records", 0)) for member in profile.get("members", []) if isinstance(member, dict))
                parse_failures = len(profile.get("parse_failures", []))
                total_profiled_records += record_count
                total_parse_failures += parse_failures
                total_bytes += int(meta["bytes"])
                article_entry["files"].append(
                    {
                        "file_id": file_info.get("id"),
                        "name": file_name,
                        "download_url": download_url,
                        "supplied_md5": file_info.get("supplied_md5"),
                        **meta,
                        "profile": profile,
                    }
                )
            manifest["selected_articles"].append(article_entry)
        except Exception as exc:
            manifest["download_failures"].append({"article_id": article_id, "title": title, "error_type": type(exc).__name__, "error": str(exc)})

    manifest["summary"] = {
        "selected_articles_succeeded": len(manifest["selected_articles"]),
        "download_failures": len(manifest["download_failures"]),
        "downloaded_bytes": total_bytes,
        "profiled_list_records": total_profiled_records,
        "parse_failures": total_parse_failures,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(manifest["summary"], indent=2, sort_keys=True))

    titles_succeeded = {str(item["title"]).casefold() for item in manifest["selected_articles"]}
    if "events" not in titles_succeeded or "matches" not in titles_succeeded:
        raise SystemExit("critical Events/Matches articles were not successfully acquired")
    if manifest["download_failures"]:
        raise SystemExit(f"download failures detected: {len(manifest['download_failures'])}; inspect manifest")
    if total_parse_failures:
        raise SystemExit(f"source parse failures detected: {total_parse_failures}; inspect manifest")


if __name__ == "__main__":
    main()
