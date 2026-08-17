"""Console and file output helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path

from instagram_analyzer.history import CheckedAccount


def print_summary(following_count: int, follower_count: int, result_count: int) -> None:
    """Print relationship totals."""
    print(f"Following: {following_count}")
    print(f"Followers: {follower_count}")
    print(f"Non-followers: {result_count}")


def print_numbered_usernames(usernames: Iterable[str]) -> None:
    """Print usernames as a numbered list."""
    for index, username in enumerate(usernames, start=1):
        print(f"{index}. @{username}")


def print_checked_accounts(accounts: Iterable[CheckedAccount]) -> None:
    """Print non-followers with cumulative history annotations."""
    for line in format_checked_accounts(accounts):
        print(line)


def save_usernames(
    usernames: Iterable[str],
    target_username: str,
    *,
    output_directory: Path = Path("output"),
) -> Path:
    """Save one @username per line and return the output path."""
    output_directory.mkdir(parents=True, exist_ok=True)
    output_path = output_directory / f"non_followers_{target_username}.txt"
    contents = "".join(f"@{username}\n" for username in usernames)
    output_path.write_text(contents, encoding="utf-8")
    return output_path


def save_history_report(
    accounts: Iterable[CheckedAccount],
    authenticated_username: str,
    target_username: str,
    following_count: int,
    follower_count: int,
    run_started_at: datetime,
    *,
    history_directory: Path = Path("output/history"),
) -> Path:
    """Save a timestamped analysis report without overwriting earlier runs."""
    history_directory.mkdir(parents=True, exist_ok=True)
    output_path = _available_history_path(history_directory, run_started_at)
    account_list = list(accounts)
    previously_checked_count = sum(
        account.previously_checked for account in account_list
    )

    lines = [
        "Instagram Non-Followers Analyzer",
        "",
        f"Run started: {run_started_at:%Y-%m-%d %H:%M:%S}",
        f"Authenticated as: @{authenticated_username}",
        f"Target: @{target_username}",
        "",
        f"Following: {following_count}",
        f"Followers: {follower_count}",
        f"Non-followers: {len(account_list)}",
        "",
        "Non-followers:",
        "",
    ]
    if account_list:
        lines.extend(format_checked_accounts(account_list))
    else:
        lines.append("None")
    lines.extend(
        [
            "",
            f"Total: {len(account_list)}",
            f"Previously checked: {previously_checked_count}",
            f"New: {len(account_list) - previously_checked_count}",
        ]
    )

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def format_checked_accounts(accounts: Iterable[CheckedAccount]) -> list[str]:
    """Format account rows identically for console and text reports."""
    account_list = list(accounts)
    if not account_list:
        return []
    username_width = max(len(account.username) for account in account_list)
    return [
        (
            f"{account.username:<{username_width}}  [checked]"
            if account.previously_checked
            else account.username
        )
        for account in account_list
    ]


def _available_history_path(
    history_directory: Path,
    run_started_at: datetime,
) -> Path:
    timestamp = run_started_at.strftime("%Y-%m-%d_%H-%M-%S")
    output_path = history_directory / f"{timestamp}.txt"
    collision_index = 2
    while output_path.exists():
        output_path = history_directory / f"{timestamp}_{collision_index}.txt"
        collision_index += 1
    return output_path
