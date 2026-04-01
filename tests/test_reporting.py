from pathlib import Path

from ig_follower_analyzer.models import RelationshipSets, UnfollowResult
from ig_follower_analyzer.reporting import write_reports


def test_write_reports_outputs_json_and_csv(tmp_path: Path) -> None:
    sets = RelationshipSets(
        following=["a", "b"],
        followers=["b", "c"],
        follow_you_back=["b"],
        you_dont_follow_back=["c"],
        dont_follow_you_back=["a"],
    )

    files = write_reports(
        sets,
        output_dir=tmp_path,
        formats=("json", "csv"),
        unfollow_results=[UnfollowResult(username="a", attempted=True, success=True)],
        timestamp="20260401T000000Z",
    )

    assert len(files["following"]) == 2
    assert len(files["followers"]) == 2
    assert len(files["follow_you_back"]) == 2
    assert len(files["you_dont_follow_back"]) == 2
    assert len(files["dont_follow_you_back"]) == 2
    assert len(files["unfollow_actions"]) == 2

    expected_json = tmp_path / "20260401T000000Z_following.json"
    expected_csv = tmp_path / "20260401T000000Z_following.csv"
    assert expected_json.exists()
    assert expected_csv.exists()
