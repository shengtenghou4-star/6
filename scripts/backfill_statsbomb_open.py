from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO

import requests


ARCHIVE_URL = "https://codeload.github.com/statsbomb/open-data/zip/refs/heads/master"
COMMIT_API_URL = "https://api.github.com/repos/statsbomb/open-data/commits/master"


def download(url: str, path: Path, *, timeout: float = 600.0) -> str:
    digest = hashlib.sha256()
    path.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(url, stream=True, timeout=timeout) as response:
        response.raise_for_status()
        with path.open("wb") as fh:
            for chunk in response.iter_content(chunk_size=4 * 1024 * 1024):
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


def relative_path(filename: str) -> PurePosixPath | None:
    path = PurePosixPath(filename)
    if len(path.parts) < 2:
        return None
    return PurePosixPath(*path.parts[1:])


def load_json_stream(stream: BinaryIO) -> Any:
    return json.load(stream)


def profile_archive(archive_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(archive_path) as zf:
        infos = [info for info in zf.infolist() if not info.is_dir()]
        by_relative: dict[str, zipfile.ZipInfo] = {}
        for info in infos:
            rel = relative_path(info.filename)
            if rel is not None:
                by_relative[str(rel)] = info

        competitions_info = by_relative.get("data/competitions.json")
        if competitions_info is None:
            raise ValueError("StatsBomb archive missing data/competitions.json")
        with zf.open(competitions_info) as fh:
            competitions = load_json_stream(fh)
        if not isinstance(competitions, list):
            raise ValueError("competitions.json must contain a list")

        match_infos = sorted(
            (info for rel, info in by_relative.items() if rel.startswith("data/matches/") and rel.endswith(".json")),
            key=lambda item: item.filename,
        )
        event_infos = sorted(
            (info for rel, info in by_relative.items() if rel.startswith("data/events/") and rel.endswith(".json")),
            key=lambda item: item.filename,
        )
        lineup_infos = sorted(
            (info for rel, info in by_relative.items() if rel.startswith("data/lineups/") and rel.endswith(".json")),
            key=lambda item: item.filename,
        )
        three_sixty_infos = sorted(
            (info for rel, info in by_relative.items() if rel.startswith("data/three-sixty/") and rel.endswith(".json")),
            key=lambda item: item.filename,
        )

        match_records = 0
        match_ids: set[int] = set()
        competition_season_pairs: set[tuple[int, int]] = set()
        for info in match_infos:
            with zf.open(info) as fh:
                payload = load_json_stream(fh)
            if not isinstance(payload, list):
                raise ValueError(f"match file must contain list: {info.filename}")
            match_records += len(payload)
            for item in payload:
                if not isinstance(item, dict):
                    continue
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
        for info in event_infos:
            with zf.open(info) as fh:
                payload = load_json_stream(fh)
            if not isinstance(payload, list):
                raise ValueError(f"event file must contain list: {info.filename}")
            event_records += len(payload)
            for item in payload:
                if not isinstance(item, dict):
                    continue
                event_type = item.get("type")
                if isinstance(event_type, dict) and isinstance(event_type.get("name"), str):
                    event_type_counts[event_type["name"]] += 1

        lineup_player_entries = 0
        lineup_team_entries = 0
        for info in lineup_infos:
            with zf.open(info) as fh:
                payload = load_json_stream(fh)
            if not isinstance(payload, list):
                raise ValueError(f"lineup file must contain list: {info.filename}")
            lineup_team_entries += len(payload)
            for team in payload:
                if isinstance(team, dict) and isinstance(team.get("lineup"), list):
                    lineup_player_entries += len(team["lineup"])

        three_sixty_records = 0
        for info in three_sixty_infos:
            with zf.open(info) as fh:
                payload = load_json_stream(fh)
            if not isinstance(payload, list):
                raise ValueError(f"360 file must contain list: {info.filename}")
            three_sixty_records += len(payload)

        def bytes_for(items: list[zipfile.ZipInfo]) -> dict[str, int]:
            return {
                "compressed": sum(info.compress_size for info in items),
                "uncompressed": sum(info.file_size for info in items),
            }

        data_infos = [info for rel, info in by_relative.items() if rel.startswith("data/")]
        return {
            "competition_season_rows": len(competitions),
            "match_files": len(match_infos),
            "match_records": match_records,
            "unique_match_ids": len(match_ids),
            "competition_season_pairs_from_matches": len(competition_season_pairs),
            "event_files": len(event_infos),
            "event_records": event_records,
            "event_type_counts": dict(event_type_counts.most_common()),
            "lineup_files": len(lineup_infos),
            "lineup_team_entries": lineup_team_entries,
            "lineup_player_entries": lineup_player_entries,
            "three_sixty_files": len(three_sixty_infos),
            "three_sixty_records": three_sixty_records,
            "archive_file_count": len(infos),
            "data_file_count": len(data_infos),
            "size_bytes": {
                "matches": bytes_for(match_infos),
                "events": bytes_for(event_infos),
                "lineups": bytes_for(lineup_infos),
                "three_sixty": bytes_for(three_sixty_infos),
                "all_data": bytes_for(data_infos),
            },
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Acquire and profile the official StatsBomb Open Data snapshot.")
    parser.add_argument("--output-root", default="artifacts/statsbomb-open")
    parser.add_argument("--min-matches", type=int, default=1000)
    args = parser.parse_args()

    output = Path(args.output_root)
    raw_root = output / "raw"
    archive = raw_root / "statsbomb-open-master.zip"

    commit_sha = fetch_commit_sha()
    archive_sha256 = download(ARCHIVE_URL, archive)
    dataset_profile = profile_archive(archive)

    manifest = {
        "source": "StatsBomb Open Data",
        "source_repository": "https://github.com/statsbomb/open-data",
        "archive_url": ARCHIVE_URL,
        "source_commit_sha": commit_sha,
        "archive_sha256": archive_sha256,
        "raw_archive_path": str(archive),
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
