import pytest

from ig_follower_analyzer.auth.session import (
    LoginAttemptContext,
    LoginChallengeError,
    login_with_headful_fallback,
    run_with_logout,
)
from ig_follower_analyzer.models import CollectionResult, UnfollowResult
from ig_follower_analyzer.scraping import can_proceed_with_unfollow, collect_until_stable
from ig_follower_analyzer.unfollow import execute_if_confirmed, execute_unfollow_batch


class DummyPerformer:
    def unfollow(self, username: str) -> UnfollowResult:
        return UnfollowResult(username=username, attempted=True, success=True)


def test_login_fallback_retries_in_headful_mode_after_challenge() -> None:
    attempts: list[LoginAttemptContext] = []

    def attempt(context: LoginAttemptContext) -> str:
        attempts.append(context)
        if context.headless:
            raise LoginChallengeError("challenge required")
        return "ok"

    result = login_with_headful_fallback(attempt, force_headful=False)

    assert result == "ok"
    assert attempts == [
        LoginAttemptContext(headless=True, allow_manual_challenge=False),
        LoginAttemptContext(headless=False, allow_manual_challenge=True),
    ]


def test_collect_until_stable_dedupes_and_stops() -> None:
    snapshots = [
        ["alice"],
        ["alice", "bob"],
        ["alice", "bob"],
        ["alice", "bob"],
    ]
    fetch_index = {"value": 0}
    scroll_calls = {"value": 0}

    def fetch_items() -> list[str]:
        idx = min(fetch_index["value"], len(snapshots) - 1)
        fetch_index["value"] += 1
        return snapshots[idx]

    def scroll_once() -> None:
        scroll_calls["value"] += 1

    result = collect_until_stable(fetch_items, scroll_once, max_idle_rounds=2)

    assert result == ["alice", "bob"]
    assert scroll_calls["value"] >= 2


def test_fail_closed_unfollow_guard() -> None:
    following = CollectionResult(usernames=["alice"], complete=False, error="modal missing")
    followers = CollectionResult(usernames=["alice"], complete=True)
    assert can_proceed_with_unfollow(following, followers) is False


def test_unfollow_confirmation_gate_blocks_actions() -> None:
    results = execute_if_confirmed(
        ["alice", "bob"],
        performer=DummyPerformer(),
        confirmed=False,
        jitter_min=0.5,
        jitter_max=1.0,
    )

    assert all(result.attempted is False for result in results)
    assert all(result.success is False for result in results)


def test_unfollow_jitter_applies_between_actions() -> None:
    sleeps: list[float] = []

    def fake_sleep(value: float) -> None:
        sleeps.append(value)

    def fake_random(low: float, high: float) -> float:
        assert low == 0.4
        assert high == 0.9
        return 0.7

    results = execute_unfollow_batch(
        ["alice", "bob", "carol"],
        performer=DummyPerformer(),
        jitter_min=0.4,
        jitter_max=0.9,
        sleep_fn=fake_sleep,
        random_fn=fake_random,
    )

    assert len(results) == 3
    assert sleeps == [0.7, 0.7]


def test_run_with_logout_always_executes_logout_on_error() -> None:
    calls: list[str] = []

    def work() -> str:
        calls.append("work")
        raise RuntimeError("boom")

    def logout() -> None:
        calls.append("logout")

    with pytest.raises(RuntimeError, match="boom"):
        run_with_logout(work, logout)

    assert calls == ["work", "logout"]
