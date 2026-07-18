from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

import requests


ARCHIVE_URL = "https://github.com/statsbomb/open-data/archive/refs/heads/master.zip"
COMMIT_API_URL = "https://api.github.com/repos/statsbomb/open-data/commits/master"


def download(url: str, path: Path, *, timeout: float = 180.0) -> str:
    digest = hashlib.sha256()
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                digest.update(chunk)
                fh.write(chunk)
    return digest.hexdigest()


def fetch_commit_sha(*, timeout: float = 30.0) -> str | None:
    try:
        response = requests.get(COMMIT_API_URL, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        sha = payload.get("sha")
        return sha if isinstance(sha, str) else None
    except requests.RequestException:
        return None


def extract_selected(archive: Path, destination: Path) -> dict[str, int]:
    counts = Counter()
    with zipfile.ZipFile(archive) as zf:
        for info in zf.infolist():
            path = PurePosixPath(info.filename)
            if len(path.parts) < 2:
                continue
            relative = PurePosixPath(*path.parts[1:])
            include = relative.parts and (
                relative.parts[0] == "data" or str(relative) in {"README.md", "LICENSE.pdf"}
            )
            if not include or info.is_dir():
                continue
            target = destination.joinpath(*relative.parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as source, target.open("wb") as sink:
                shutil.copyfileobj(source, sink)
            counts[relative.parts[0]] += 1
    return dict(counts)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def profile(root: Path) -> dict[str, Any]:
    data = root / "data"
    competitions_path = data / "competitions.json"
    competitions = load_json(competitions_path)
    if not isinstance(competitions, list):
        raise ValueError("competitions.json must contain a list")

    match_files = sorted((data / "matches").rglob("*.json"))
    event_files = sorted((data / "events").glob("*.json"))
    lineup_files = sorted((data / "lineups").glob("*.json"))
    three_sixty_dir = data / "three-sixty"
    three_sixty_files = sorted(three_sixty_dir.glob("*.json")) if three_sixty_dir.exists() else []

    match_records = 0
    match_ids: set[int] = set()
    competition_season_pairs: set[tuple[int, int]] = set()
    for path in match_files:
        payload = load_json(path)
        if not isinstance(payload, list):
            raise ValueError(f"match file must contain list: {path}")
        match_records += len(payload)
        for item in payload:
            if isinstance(item, dict):
                match_id = item.get("match_id")
                if isinstance(match_id, int):
                    match_ids.add(match_id)
                competition = item.get("competition") or {}
                season = item.get("season") or {}
                cid = competition.get("competition_id") if isinstance(competition, dict) else None
                sid = season.get("season_id") if isinstance(season, dict) else None
                if isinstance(cid, int) and isinstance(sid, int):
                    competition_season_pairs.add((cid, sid))

    event_records = 0
    event_type_counts = Counter()
    for path in event_files:
        payload = load_json(path)
        if not isinstance(payload, list):
            raise ValueError(f"event file must contain list: {path}")
        event_records += len(payload)
        for item in payload:
            if not isinstance(item, dict):
                continue
            event_type = item.get("type")
            if isinstance(event_type, dict) and isinstance(event_type.get("name"), str):
                event_type_counts[event_type["name"]] += 1

    lineup_player_entries = 0
    lineup_team_entries = 0
    for path in lineup_files:
        payload = load_json(path)
        if not isinstance(payload, list):
            raise ValueError(f"lineup file must contain list: {path}")
        lineup_team_entries += len(payload)
        for team in payload:
            if isinstance(team, dict) and isinstance(team.get("lineup"), list):
                lineup_player_entries += len(team["lineup"])

    three_sixty_records = 0
    for path in three_sixty_files:
        payload = load_json(path)
        if not isinstance(payload, list):
            raise ValueError(f"360 file must contain list: {path}")
        three_sixty_records += len(payload)

    file_sizes = {
        "competitions_bytes": competitions_path.stat().st_size,
        "matches_bytes": sum(path.stat().st_size for path in match_files),
        "events_bytes": sum(path.stat().st_size for path in event_files),
        "lineups_bytes": sum(path.stat().st_size for path in lineup_files),
        "three_sixty_bytes": sum(path.stat().st_size for path in three_sixty_files),
    }

    return {
        "competition_season_rows": len(competitions),
        "match_files": len(match_files),
        "match_records": match_records,
        "unique_match_ids": len(match_ids),
        "competition_season_pairs_from_matches": len(competition_season_pairs),
        "event_files": len(event_files),
        "event_records": event_records,
        "event_type_counts": dict(event_type_counts.most_common()),
        "lineup_files": len(lineup_files),
        "lineup_team_entries": lineup_team_entries,
        "lineup_player_entries": lineup_player_entries,
        "three_sixty_files": len(three_sixty_files),
        "three_sixty_records": three_sixty_records,
        "file_sizes": file_sizes,
        "raw_data_bytes": sum(file_sizes.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire and profile the official StatsBomb Open Data snapshot.")
    parser.add_argument("--output-root", default="artifacts/statsbomb-open")
    parser.add_argument("--min-matches", type=int, default=1000)
    args = parser.parse_args()

    output = Path(args.output_root)
    raw_root = output / "raw" / "statsbomb_open"
    archive = output / "_download" / "statsbomb-open-master.zip"

    commit_sha = fetch_commit_sha()
    archive_sha256 = download(ARCHIVE_URL, archive)
    extracted_counts = extract_selected(archive, raw_root)
    archive.unlink(missing_ok=True)

    dataset_profile = profile(raw_root)
    manifest = {
        "source": "StatsBomb Open Data",
        "source_repository": "https://github.com/statsbomb/open-data",
        "archive_url": ARCHIVE_URL,
        "source_commit_sha": commit_sha,
        "archive_sha256": archive_sha256,
        "extracted_top_level_file_counts": extracted_counts,
        "profile": dataset_profile,
        "license_note": "Preserve StatsBomb attribution and follow the repository license/README requirements for publication or sharing.",
    }
    output.mkdir(parents=True, exist_ok=True)
    (output / "profile.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(dataset_profile, indent=2, sort_keys=True))

    if dataset_profile["unique_match_ids"] < args.min_matches:
        raise SystemExit(
            f"unexpectedly small StatsBomb snapshot: {dataset_profile['unique_match_ids']} < {args.min_matches} matches"
        )
    if dataset_profile["event_files"] == 0 or dataset_profile["lineup_files"] == 0:
        raise SystemExit("event or lineup layer unexpectedly empty")


if __name__ == "__main__":
    main()
