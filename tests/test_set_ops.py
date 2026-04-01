from ig_follower_analyzer.set_ops import (
    build_relationship_sets,
    normalize_unique_usernames,
    normalize_username,
)


def test_normalize_username() -> None:
    assert normalize_username(" @TestUser ") == "testuser"
    assert normalize_username("https://www.instagram.com/Some.User/") == "some.user"


def test_normalize_unique_usernames_dedupes() -> None:
    normalized = normalize_unique_usernames(["Alice", "@alice", "bob", "BOB", ""])
    assert normalized == ["alice", "bob"]


def test_build_relationship_sets() -> None:
    sets = build_relationship_sets(
        following=["alice", "bob", "carol"],
        followers=["bob", "dave", "carol"],
    )

    assert sets.following == ["alice", "bob", "carol"]
    assert sets.followers == ["bob", "carol", "dave"]
    assert sets.follow_you_back == ["bob", "carol"]
    assert sets.you_dont_follow_back == ["dave"]
    assert sets.dont_follow_you_back == ["alice"]
