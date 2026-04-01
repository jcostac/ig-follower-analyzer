from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence, cast

from .auth.session import (
    InstagramBrowserSession,
    LoginAttemptContext,
    login_with_headful_fallback,
    resolve_credentials,
    run_with_logout,
)
from .models import Credentials, OutputFormat, RelationshipSets, RunConfig, UnfollowResult
from .reporting import utc_timestamp_slug, write_reports
from .scraping import can_proceed_with_unfollow, collect_connections
from .selection_parser import SelectionParseError
from .selectors import InstagramSelectors
from .set_ops import build_relationship_sets
from .unfollow import (
    PlaywrightUnfollowPerformer,
    build_indexed_users,
    confirm_token_matches,
    execute_if_confirmed,
    resolve_selection,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    try:
        config = _build_config(args)
    except ValueError as err:
        print(f"Configuration error: {err}")
        return 2

    try:
        credentials = resolve_credentials(
            cli_username=args.username,
            cli_password=args.password,
            cli_email=args.email,
            env_path=Path(args.env_file),
            prompt_for_missing=True,
        )
    except ValueError as err:
        print(f"Credential error: {err}")
        return 2

    selectors = InstagramSelectors()

    try:
        session = login_with_headful_fallback(
            attempt_login=lambda ctx: _login_attempt(
                context=ctx,
                selectors=selectors,
                config=config,
                credentials=credentials,
            ),
            force_headful=config.headful,
        )
    except Exception as err:
        print(f"Login failed: {err}")
        return 1

    try:
        result_code = run_with_logout(
            lambda: _run_analysis_flow(
                session=session,
                selectors=selectors,
                config=config,
                username=credentials.username,
            ),
            session.logout,
        )
        return result_code
    finally:
        try:
            session.close()
        except Exception as err:
            print(f"Warning: failed to close browser cleanly: {err}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ig-follower-analyzer",
        description="Analyze Instagram follow relationships and optionally unfollow non-mutual accounts.",
    )
    parser.add_argument("--username", help="Instagram username (overrides .env IG_USERNAME)")
    parser.add_argument("--password", help="Instagram password (overrides .env IG_PASSWORD)")
    parser.add_argument("--email", help="Instagram email (optional; overrides .env IG_EMAIL)")
    parser.add_argument("--env-file", default=".env", help="Path to .env file (default: .env)")
    parser.add_argument(
        "--fresh-login",
        action="store_true",
        help="Ignore stored session state and force a fresh login",
    )
    parser.add_argument(
        "--state-file",
        default=".state/instagram_state.json",
        help="Path for persisted Playwright storage state",
    )
    parser.add_argument(
        "--headful",
        action="store_true",
        help="Run browser in headed mode from start",
    )
    parser.add_argument(
        "--output-dir",
        default="reports",
        help="Directory for generated JSON/CSV reports",
    )
    parser.add_argument(
        "--format",
        default="json,csv",
        help="Comma-separated report formats: json,csv",
    )
    parser.add_argument(
        "--no-unfollow",
        action="store_true",
        help="Analyze and report only; do not execute unfollows",
    )
    parser.add_argument(
        "--select",
        help="Selection string for unfollow targets (e.g. 1,3,8-12 or all)",
    )
    parser.add_argument(
        "--jitter-min",
        type=float,
        default=0.9,
        help="Minimum delay (seconds) between unfollow actions",
    )
    parser.add_argument(
        "--jitter-max",
        type=float,
        default=2.2,
        help="Maximum delay (seconds) between unfollow actions",
    )
    return parser


def _build_config(args: argparse.Namespace) -> RunConfig:
    if args.jitter_min < 0 or args.jitter_max < 0:
        raise ValueError("jitter values must be >= 0")
    if args.jitter_min > args.jitter_max:
        raise ValueError("--jitter-min must be <= --jitter-max")

    formats = _parse_formats(args.format)
    return RunConfig(
        base_url="https://www.instagram.com/?flo=true",
        output_dir=Path(args.output_dir),
        output_formats=formats,
        state_file=Path(args.state_file),
        fresh_login=bool(args.fresh_login),
        headful=bool(args.headful),
        no_unfollow=bool(args.no_unfollow),
        select=args.select,
        jitter_min=args.jitter_min,
        jitter_max=args.jitter_max,
    )


def _parse_formats(raw: str) -> tuple[OutputFormat, ...]:
    tokens = [token.strip().lower() for token in raw.split(",") if token.strip()]
    if not tokens:
        raise ValueError("at least one output format must be provided")

    allowed: set[str] = {"json", "csv"}
    invalid = [token for token in tokens if token not in allowed]
    if invalid:
        raise ValueError(f"unsupported output formats: {', '.join(invalid)}")

    unique_tokens: list[OutputFormat] = []
    for token in tokens:
        typed_token = cast(OutputFormat, token)
        if typed_token in unique_tokens:
            continue
        unique_tokens.append(typed_token)
    return tuple(unique_tokens)


def _login_attempt(
    *,
    context: LoginAttemptContext,
    selectors: InstagramSelectors,
    config: RunConfig,
    credentials: Credentials,
) -> InstagramBrowserSession:
    session = InstagramBrowserSession(
        selectors=selectors,
        headless=context.headless,
        state_file=config.state_file,
        fresh_login=config.fresh_login,
    )
    try:
        session.login(credentials, allow_manual_challenge=context.allow_manual_challenge)
        session.persist_storage_state()
        return session
    except Exception:
        try:
            session.close()
        except Exception:
            pass
        raise


def _run_analysis_flow(
    *,
    session: InstagramBrowserSession,
    selectors: InstagramSelectors,
    config: RunConfig,
    username: str,
) -> int:
    timestamp = utc_timestamp_slug()

    following_result, followers_result = collect_connections(
        session.page,
        username=username,
        selectors=selectors,
    )

    if not can_proceed_with_unfollow(following_result, followers_result):
        print("Follower/following collection failed. Unfollow phase is blocked.")
        if following_result.error:
            print(f"Following extraction error: {following_result.error}")
        if followers_result.error:
            print(f"Followers extraction error: {followers_result.error}")
        return 1

    relationship_sets = build_relationship_sets(
        following_result.usernames,
        followers_result.usernames,
    )

    _print_summary(relationship_sets)
    _print_indexed_primary_targets(relationship_sets.dont_follow_you_back)

    unfollow_results: list[UnfollowResult] | None = None
    if not config.no_unfollow and relationship_sets.dont_follow_you_back:
        unfollow_results = _run_unfollow_phase(
            usernames=relationship_sets.dont_follow_you_back,
            page=session.page,
            selectors=selectors,
            config=config,
        )

    files = write_reports(
        relationship_sets,
        output_dir=config.output_dir,
        formats=config.output_formats,
        unfollow_results=unfollow_results,
        timestamp=timestamp,
    )

    total_files = sum(len(paths) for paths in files.values())
    print(f"Reports written to: {config.output_dir} ({total_files} files)")
    return 0


def _run_unfollow_phase(
    *,
    usernames: list[str],
    page: object,
    selectors: InstagramSelectors,
    config: RunConfig,
) -> list[UnfollowResult]:
    selection_raw = config.select
    if not selection_raw:
        selection_raw = input(
            "Select users to unfollow by index/range (e.g. 1,3,8-12) or 'all': "
        ).strip()

    try:
        selected_usernames = resolve_selection(usernames, selection_raw)
    except SelectionParseError as err:
        print(f"Selection error: {err}")
        return []

    if not selected_usernames:
        print("No users selected for unfollow.")
        return []

    print(f"Selected {len(selected_usernames)} account(s) for unfollow:")
    for index, username in enumerate(selected_usernames, start=1):
        print(f"{index}. {username}")

    token = input("Type UNFOLLOW to proceed: ")
    confirmed = confirm_token_matches(token)

    performer = PlaywrightUnfollowPerformer(page=page, selectors=selectors)
    results = execute_if_confirmed(
        selected_usernames,
        performer=performer,
        confirmed=confirmed,
        jitter_min=config.jitter_min,
        jitter_max=config.jitter_max,
    )

    success_count = sum(1 for result in results if result.success)
    print(f"Unfollow phase complete: {success_count}/{len(results)} succeeded")
    return results


def _print_summary(relationship_sets: RelationshipSets) -> None:
    print("Relationship summary:")
    print(f"- following: {len(relationship_sets.following)}")
    print(f"- followers: {len(relationship_sets.followers)}")
    print(f"- follow_you_back: {len(relationship_sets.follow_you_back)}")
    print(f"- you_dont_follow_back: {len(relationship_sets.you_dont_follow_back)}")
    print(f"- dont_follow_you_back: {len(relationship_sets.dont_follow_you_back)}")


def _print_indexed_primary_targets(usernames: list[str]) -> None:
    indexed = build_indexed_users(usernames)
    if not indexed:
        print("No users found in dont_follow_you_back.")
        return

    print("dont_follow_you_back:")
    for entry in indexed:
        print(f"{entry.index}. {entry.username}")
