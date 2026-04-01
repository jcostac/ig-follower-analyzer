from pathlib import Path

import pytest

from ig_follower_analyzer.auth.session import resolve_credentials


def test_cli_credentials_override_env(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "IG_USERNAME=env_user\nIG_PASSWORD=env_pass\nIG_EMAIL=env@example.com\n",
        encoding="utf-8",
    )

    credentials = resolve_credentials(
        cli_username="cli_user",
        cli_password="cli_pass",
        cli_email="cli@example.com",
        env_path=env_file,
        prompt_for_missing=False,
    )

    assert credentials.username == "cli_user"
    assert credentials.password == "cli_pass"
    assert credentials.email == "cli@example.com"


def test_env_credentials_are_used_when_cli_missing(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "IG_USERNAME=env_user\nIG_PASSWORD=env_pass\nIG_EMAIL=env@example.com\n",
        encoding="utf-8",
    )

    credentials = resolve_credentials(
        cli_username=None,
        cli_password=None,
        cli_email=None,
        env_path=env_file,
        prompt_for_missing=False,
    )

    assert credentials.username == "env_user"
    assert credentials.password == "env_pass"
    assert credentials.email == "env@example.com"


def test_missing_required_credentials_raise(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("IG_EMAIL=env@example.com\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing Instagram username"):
        resolve_credentials(
            cli_username=None,
            cli_password=None,
            cli_email=None,
            env_path=env_file,
            prompt_for_missing=False,
        )
