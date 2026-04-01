import pytest

from ig_follower_analyzer.selection_parser import SelectionParseError, parse_selection


def test_parse_selection_numbers_ranges_and_all() -> None:
    assert parse_selection("1,2,5-7", upper_bound=10) == [1, 2, 5, 6, 7]
    assert parse_selection("all", upper_bound=4) == [1, 2, 3, 4]


def test_parse_selection_out_of_range_raises() -> None:
    with pytest.raises(SelectionParseError, match="out of range"):
        parse_selection("1,8", upper_bound=5)


def test_parse_selection_invalid_token_raises() -> None:
    with pytest.raises(SelectionParseError, match="invalid"):
        parse_selection("a,3", upper_bound=5)
