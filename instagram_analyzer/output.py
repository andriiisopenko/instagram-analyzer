"""Console and file output helpers."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from pathlib import Path


def print_summary(following_count: int, follower_count: int, result_count: int) -> None:
    """Print relationship totals."""
    print(f"Following: {following_count}")
    print(f"Followers: {follower_count}")
    print(f"Non-followers: {result_count}")


def print_numbered_usernames(usernames: Iterable[str]) -> None:
    """Print usernames as a numbered list."""
    for index, username in enumerate(usernames, start=1):
        print(f"{index}. @{username}")


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
    usernames: Iterable[str],
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
    username_list = list(usernames)

    lines = [
        "Instagram Non-Followers Analyzer",
        "",
        f"Run started: {run_started_at:%Y-%m-%d %H:%M:%S}",
        f"Authenticated as: @{authenticated_username}",
        f"Target: @{target_username}",
        "",
        f"Following: {following_count}",
        f"Followers: {follower_count}",
        f"Non-followers: {len(username_list)}",
        "",
        "Non-followers:",
        "",
    ]
    if username_list:
        lines.extend(
            f"{index}. @{username}"
            for index, username in enumerate(username_list, start=1)
        )
    else:
        lines.append("None")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


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
