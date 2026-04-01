from __future__ import annotations

import re
from typing import Callable

from .models import CollectionResult
from .selectors import InstagramSelectors
from .set_ops import normalize_unique_usernames

_USERNAME_PATH = re.compile(r"^/([A-Za-z0-9._]+)/?$")


def collect_connections(
    page: object,
    *,
    username: str,
    selectors: InstagramSelectors,
) -> tuple[CollectionResult, CollectionResult]:
    following = _collect_single_connection_type(
        page,
        username=username,
        relation="following",
        selectors=selectors,
    )
    followers = _collect_single_connection_type(
        page,
        username=username,
        relation="followers",
        selectors=selectors,
    )
    return following, followers


def can_proceed_with_unfollow(
    following_result: CollectionResult,
    followers_result: CollectionResult,
) -> bool:
    return following_result.complete and followers_result.complete


def collect_until_stable(
    fetch_items: Callable[[], list[str]],
    scroll_once: Callable[[], None],
    *,
    max_rounds: int = 250,
    max_idle_rounds: int = 5,
) -> list[str]:
    seen: list[str] = []
    seen_set: set[str] = set()
    idle_rounds = 0

    for _ in range(max_rounds):
        batch = normalize_unique_usernames(fetch_items())
        new_count = 0
        for username in batch:
            if username in seen_set:
                continue
            seen_set.add(username)
            seen.append(username)
            new_count += 1

        if new_count == 0:
            idle_rounds += 1
        else:
            idle_rounds = 0

        if idle_rounds >= max_idle_rounds:
            return sorted(seen)

        scroll_once()

    raise RuntimeError("list collection did not stabilize before max rounds")


def _collect_single_connection_type(
    page: object,
    *,
    username: str,
    relation: str,
    selectors: InstagramSelectors,
) -> CollectionResult:
    try:
        page.goto(
            f"https://www.instagram.com/{username}/{relation}/",
            wait_until="domcontentloaded",
        )
        page.wait_for_timeout(2000)

        if page.locator(selectors.dialog).count() == 0:
            raise RuntimeError(f"{relation} modal was not detected")

        usernames = collect_until_stable(
            fetch_items=lambda: _extract_usernames_from_dialog(page=page, selectors=selectors),
            scroll_once=lambda: _scroll_modal(page=page, selectors=selectors),
        )

        return CollectionResult(usernames=usernames, complete=True)
    except Exception as err:
        return CollectionResult(usernames=[], complete=False, error=str(err))


def _extract_usernames_from_dialog(page: object, *, selectors: InstagramSelectors) -> list[str]:
    hrefs = page.locator(selectors.dialog_links).evaluate_all(
        "nodes => nodes.map((node) => node.getAttribute('href') || '')"
    )
    usernames: list[str] = []
    for href in hrefs:
        match = _USERNAME_PATH.match(href)
        if not match:
            continue
        usernames.append(match.group(1))
    return usernames


def _scroll_modal(page: object, *, selectors: InstagramSelectors) -> None:
    scroll_container = page.locator(selectors.dialog_scroll_container)
    target = scroll_container if scroll_container.count() > 0 else page.locator(selectors.dialog)
    target.first.evaluate("node => { node.scrollTop = node.scrollHeight; }")
    page.wait_for_timeout(850)
