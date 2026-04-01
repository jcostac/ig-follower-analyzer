from __future__ import annotations


class SelectionParseError(ValueError):
    """Raised when selection syntax is invalid."""


def parse_selection(selection: str, *, upper_bound: int) -> list[int]:
    if upper_bound < 0:
        raise ValueError(f"upper_bound must be >= 0, received: {upper_bound}")
    if upper_bound == 0:
        return []

    raw = selection.strip().lower()
    if not raw:
        raise SelectionParseError("selection cannot be empty")

    if raw == "all":
        return list(range(1, upper_bound + 1))

    selected: set[int] = set()
    tokens = [token.strip() for token in raw.split(",") if token.strip()]
    if not tokens:
        raise SelectionParseError("selection must contain at least one value")

    for token in tokens:
        if "-" in token:
            parts = token.split("-", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:
                raise SelectionParseError(f"invalid range token: {token}")
            try:
                start = int(parts[0])
                end = int(parts[1])
            except ValueError as err:
                raise SelectionParseError(f"invalid numeric range token: {token}") from err
            if start > end:
                raise SelectionParseError(f"range start > end: {token}")
            for value in range(start, end + 1):
                _validate_bounds(value, upper_bound)
                selected.add(value)
            continue

        try:
            index = int(token)
        except ValueError as err:
            raise SelectionParseError(f"invalid numeric token: {token}") from err
        _validate_bounds(index, upper_bound)
        selected.add(index)

    return sorted(selected)


def _validate_bounds(value: int, upper_bound: int) -> None:
    if value < 1 or value > upper_bound:
        raise SelectionParseError(
            f"selection index out of range: {value} (must be between 1 and {upper_bound})"
        )
