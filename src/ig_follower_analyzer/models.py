from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

OutputFormat = Literal["json", "csv"]


@dataclass(frozen=True)
class Credentials:
    username: str
    password: str
    email: str | None = None


@dataclass(frozen=True)
class RunConfig:
    base_url: str
    output_dir: Path
    output_formats: tuple[OutputFormat, ...]
    state_file: Path
    fresh_login: bool
    headful: bool
    no_unfollow: bool
    select: str | None
    jitter_min: float
    jitter_max: float


@dataclass(frozen=True)
class CollectionResult:
    usernames: list[str]
    complete: bool
    error: str | None = None


@dataclass(frozen=True)
class RelationshipSets:
    following: list[str]
    followers: list[str]
    follow_you_back: list[str]
    you_dont_follow_back: list[str]
    dont_follow_you_back: list[str]


@dataclass(frozen=True)
class UnfollowResult:
    username: str
    attempted: bool
    success: bool
    reason: str | None = None
