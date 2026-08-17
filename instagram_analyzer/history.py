"""Persistent history of accounts that did not follow a target back."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True, slots=True)
class CheckedAccount:
    """A non-follower annotated with whether it appeared before this run."""

    username: str
    previously_checked: bool


class HistoryStore:
    """Track cumulative non-follower history independently for each target."""

    def __init__(self, database_path: Path = Path("data/history.db")) -> None:
        self.database_path = database_path
        self._initialize()

    def classify_accounts(
        self,
        target_username: str,
        account_usernames: list[str],
    ) -> list[CheckedAccount]:
        """Mark accounts already stored for this target without updating history."""
        normalized_target = target_username.casefold()
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT account_username
                FROM non_follower_history
                WHERE target_username = ?
                """,
                (normalized_target,),
            ).fetchall()
        previously_seen = {str(row["account_username"]).casefold() for row in rows}
        return [
            CheckedAccount(
                username=username,
                previously_checked=username.casefold() in previously_seen,
            )
            for username in account_usernames
        ]

    def record_results(
        self,
        target_username: str,
        account_usernames: list[str],
        seen_at: datetime,
    ) -> None:
        """Insert new results and update cumulative timestamps and counters."""
        if not account_usernames:
            return
        timestamp = seen_at.astimezone().isoformat(timespec="seconds")
        normalized_target = target_username.casefold()
        rows = [
            (normalized_target, username.casefold(), timestamp, timestamp)
            for username in account_usernames
        ]
        with self._connection() as connection:
            connection.executemany(
                """
                INSERT INTO non_follower_history (
                    target_username,
                    account_username,
                    first_seen_at,
                    last_seen_at,
                    times_seen
                ) VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(target_username, account_username) DO UPDATE SET
                    last_seen_at = excluded.last_seen_at,
                    times_seen = non_follower_history.times_seen + 1
                """,
                rows,
            )

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.chmod(0o700)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS non_follower_history (
                    target_username TEXT NOT NULL COLLATE NOCASE,
                    account_username TEXT NOT NULL COLLATE NOCASE,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    times_seen INTEGER NOT NULL DEFAULT 1 CHECK(times_seen > 0),
                    PRIMARY KEY (target_username, account_username)
                )
                """
            )
        self.database_path.chmod(0o600)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()
