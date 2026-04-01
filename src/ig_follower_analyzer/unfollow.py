from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from typing import Callable, Protocol

from .models import UnfollowResult
from .selection_parser import parse_selection
from .selectors import InstagramSelectors


@dataclass(frozen=True)
class IndexedUser:
    index: int
    username: str


class UnfollowPerformer(Protocol):
    def unfollow(self, username: str) -> UnfollowResult:
        ...


def build_indexed_users(usernames: list[str]) -> list[IndexedUser]:
    sorted_usernames = sorted(usernames)
    return [IndexedUser(index=index + 1, username=username) for index, username in enumerate(sorted_usernames)]


def resolve_selection(usernames: list[str], selection: str) -> list[str]:
    indexed = build_indexed_users(usernames)
    selected_indexes = set(parse_selection(selection, upper_bound=len(indexed)))
    return [entry.username for entry in indexed if entry.index in selected_indexes]


def confirm_token_matches(value: str, *, expected: str = "UNFOLLOW") -> bool:
    return value.strip() == expected


def execute_if_confirmed(
    usernames: list[str],
    *,
    performer: UnfollowPerformer,
    confirmed: bool,
    jitter_min: float,
    jitter_max: float,
    sleep_fn: Callable[[float], None] = time.sleep,
    random_fn: Callable[[float, float], float] = random.uniform,
) -> list[UnfollowResult]:
    if not confirmed:
        return [
            UnfollowResult(
                username=username,
                attempted=False,
                success=False,
                reason="confirmation token was not provided",
            )
            for username in usernames
        ]

    return execute_unfollow_batch(
        usernames,
        performer=performer,
        jitter_min=jitter_min,
        jitter_max=jitter_max,
        sleep_fn=sleep_fn,
        random_fn=random_fn,
    )


def execute_unfollow_batch(
    usernames: list[str],
    *,
    performer: UnfollowPerformer,
    jitter_min: float,
    jitter_max: float,
    sleep_fn: Callable[[float], None] = time.sleep,
    random_fn: Callable[[float, float], float] = random.uniform,
) -> list[UnfollowResult]:
    if jitter_min < 0 or jitter_max < 0:
        raise ValueError("jitter values must be >= 0")
    if jitter_min > jitter_max:
        raise ValueError("jitter_min must be <= jitter_max")

    results: list[UnfollowResult] = []
    for position, username in enumerate(usernames):
        result = performer.unfollow(username)
        results.append(result)

        if position == len(usernames) - 1:
            continue
        delay = random_fn(jitter_min, jitter_max)
        sleep_fn(delay)

    return results


class PlaywrightUnfollowPerformer:
    def __init__(self, *, page: object, selectors: InstagramSelectors) -> None:
        self._page = page
        self._selectors = selectors

    def unfollow(self, username: str) -> UnfollowResult:
        try:
            self._page.goto(f"https://www.instagram.com/{username}/", wait_until="domcontentloaded")
            self._page.wait_for_timeout(900)

            following_button = self._page.locator(self._selectors.following_action_button)
            if following_button.count() == 0:
                # Fallback to role-based lookup for slightly different IG labels.
                fallback = self._page.get_by_role(
                    "button",
                    name=re.compile(r"^(Following|Requested)$", flags=re.IGNORECASE),
                )
                if fallback.count() == 0:
                    return UnfollowResult(
                        username=username,
                        attempted=False,
                        success=False,
                        reason="following button not found",
                    )
                fallback.first.click()
            else:
                following_button.first.click()

            self._page.wait_for_timeout(450)
            confirm_button = self._page.locator(self._selectors.unfollow_confirm_button)
            if confirm_button.count() == 0:
                confirm_button = self._page.get_by_role(
                    "button",
                    name=re.compile(r"^Unfollow$", flags=re.IGNORECASE),
                )

            if confirm_button.count() == 0:
                return UnfollowResult(
                    username=username,
                    attempted=True,
                    success=False,
                    reason="unfollow confirmation button not found",
                )

            confirm_button.first.click()
            self._page.wait_for_timeout(850)
            return UnfollowResult(username=username, attempted=True, success=True)
        except Exception as err:
            return UnfollowResult(username=username, attempted=True, success=False, reason=str(err))
