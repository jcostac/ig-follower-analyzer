from __future__ import annotations

import csv
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .models import OutputFormat, RelationshipSets, UnfollowResult


def utc_timestamp_slug(now: datetime | None = None) -> str:
    current = now or datetime.now(tz=timezone.utc)
    return current.strftime("%Y%m%dT%H%M%SZ")


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_reports(
    sets: RelationshipSets,
    output_dir: Path,
    formats: tuple[OutputFormat, ...],
    unfollow_results: list[UnfollowResult] | None = None,
    timestamp: str | None = None,
) -> dict[str, list[Path]]:
    slug = timestamp or utc_timestamp_slug()
    ensure_output_dir(output_dir)

    files_written: dict[str, list[Path]] = {
        "following": [],
        "followers": [],
        "follow_you_back": [],
        "you_dont_follow_back": [],
        "dont_follow_you_back": [],
        "unfollow_actions": [],
    }

    relationship_map: dict[str, list[str]] = {
        "following": sets.following,
        "followers": sets.followers,
        "follow_you_back": sets.follow_you_back,
        "you_dont_follow_back": sets.you_dont_follow_back,
        "dont_follow_you_back": sets.dont_follow_you_back,
    }

    for name, usernames in relationship_map.items():
        files_written[name].extend(
            write_username_collection(
                name=name,
                usernames=usernames,
                output_dir=output_dir,
                formats=formats,
                timestamp=slug,
            )
        )

    if unfollow_results is not None:
        files_written["unfollow_actions"].extend(
            write_unfollow_actions(
                output_dir=output_dir,
                formats=formats,
                timestamp=slug,
                results=unfollow_results,
            )
        )

    return files_written


def write_username_collection(
    *,
    name: str,
    usernames: list[str],
    output_dir: Path,
    formats: tuple[OutputFormat, ...],
    timestamp: str,
) -> list[Path]:
    files: list[Path] = []

    if "json" in formats:
        json_path = output_dir / f"{timestamp}_{name}.json"
        payload = {
            "name": name,
            "count": len(usernames),
            "usernames": usernames,
        }
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        files.append(json_path)

    if "csv" in formats:
        csv_path = output_dir / f"{timestamp}_{name}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as file_obj:
            writer = csv.writer(file_obj)
            writer.writerow(["username"])
            for username in usernames:
                writer.writerow([username])
        files.append(csv_path)

    return files


def write_unfollow_actions(
    *,
    output_dir: Path,
    formats: tuple[OutputFormat, ...],
    timestamp: str,
    results: list[UnfollowResult],
) -> list[Path]:
    files: list[Path] = []

    if "json" in formats:
        json_path = output_dir / f"{timestamp}_unfollow_actions.json"
        payload = {
            "count": len(results),
            "results": [asdict(result) for result in results],
        }
        json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        files.append(json_path)

    if "csv" in formats:
        csv_path = output_dir / f"{timestamp}_unfollow_actions.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as file_obj:
            writer = csv.writer(file_obj)
            writer.writerow(["username", "attempted", "success", "reason"])
            for result in results:
                writer.writerow([
                    result.username,
                    str(result.attempted).lower(),
                    str(result.success).lower(),
                    result.reason or "",
                ])
        files.append(csv_path)

    return files
