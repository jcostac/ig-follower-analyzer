from __future__ import annotations

from typing import Iterable

from .models import RelationshipSets


def normalize_username(username: str) -> str:
    cleaned = username.strip().lower()
    if cleaned.startswith("@"):
        cleaned = cleaned[1:]
    if cleaned.startswith("https://www.instagram.com/"):
        cleaned = cleaned.replace("https://www.instagram.com/", "", 1)
    cleaned = cleaned.strip("/")
    return cleaned


def normalize_unique_usernames(usernames: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for username in usernames:
        cleaned = normalize_username(username)
        if not cleaned:
            continue
        if cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def build_relationship_sets(
    following: Iterable[str],
    followers: Iterable[str],
) -> RelationshipSets:
    following_normalized = sorted(normalize_unique_usernames(following))
    followers_normalized = sorted(normalize_unique_usernames(followers))

    following_set = set(following_normalized)
    followers_set = set(followers_normalized)

    return RelationshipSets(
        following=following_normalized,
        followers=followers_normalized,
        follow_you_back=sorted(following_set & followers_set),
        you_dont_follow_back=sorted(followers_set - following_set),
        dont_follow_you_back=sorted(following_set - followers_set),
    )
