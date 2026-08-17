"""Console and file output helpers."""

from __future__ import annotations

from collections.abc import Iterable
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

