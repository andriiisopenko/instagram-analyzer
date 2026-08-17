"""Local SQLite storage for reusable Instagram accounts."""

from __future__ import annotations

import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterator


@dataclass(frozen=True, slots=True)
class SavedAccount:
    """Metadata for one locally saved Instagram account."""

    id: int
    username: str
    session_file: str
    created_at: str
    last_used_at: str


class AccountStore:
    """Manage account metadata without storing credentials or session contents."""

    def __init__(
        self,
        database_path: Path = Path("data/accounts.db"),
        sessions_directory: Path = Path("data/sessions"),
    ) -> None:
        self.database_path = database_path
        self.sessions_directory = sessions_directory
        self._initialize()

    def list_accounts(self) -> list[SavedAccount]:
        """Return all saved accounts sorted by username."""
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT id, username, session_file, created_at, last_used_at
                FROM accounts
                ORDER BY username COLLATE NOCASE
                """
            ).fetchall()
        return [_account_from_row(row) for row in rows]

    def get_by_username(self, username: str) -> SavedAccount | None:
        """Return a saved account by case-insensitive username."""
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id, username, session_file, created_at, last_used_at
                FROM accounts
                WHERE username = ? COLLATE NOCASE
                """,
                (username,),
            ).fetchone()
        return _account_from_row(row) if row is not None else None

    def save_account(self, username: str, session_file: str) -> SavedAccount:
        """Insert an account or update its session reference and last-used time."""
        timestamp = _current_timestamp()
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO accounts (
                    username, session_file, created_at, last_used_at
                ) VALUES (?, ?, ?, ?)
                ON CONFLICT(username) DO UPDATE SET
                    session_file = excluded.session_file,
                    last_used_at = excluded.last_used_at
                """,
                (username, session_file, timestamp, timestamp),
            )
        account = self.get_by_username(username)
        if account is None:
            raise sqlite3.DatabaseError("Saved account could not be read back.")
        return account

    def mark_used(self, account_id: int) -> None:
        """Update the account's last-used timestamp."""
        with self._connection() as connection:
            connection.execute(
                "UPDATE accounts SET last_used_at = ? WHERE id = ?",
                (_current_timestamp(), account_id),
            )

    def delete_account(self, account_id: int) -> SavedAccount | None:
        """Delete one account record and return its previous metadata."""
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT id, username, session_file, created_at, last_used_at
                FROM accounts
                WHERE id = ?
                """,
                (account_id,),
            ).fetchone()
            if row is None:
                return None
            connection.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        return _account_from_row(row)

    def session_path(self, account: SavedAccount) -> Path:
        """Resolve an account session filename inside the private sessions folder."""
        return self.sessions_directory / Path(account.session_file).name

    def session_path_for_username(self, username: str) -> Path:
        """Return the sanitized session path for a username."""
        safe_username = re.sub(r"[^a-z0-9._]", "_", username.casefold())
        safe_username = safe_username.strip(".") or "instagram_account"
        return self.sessions_directory / f"{safe_username}.json"

    def _initialize(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.chmod(0o700)
        self.sessions_directory.mkdir(parents=True, exist_ok=True)
        self.sessions_directory.chmod(0o700)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    session_file TEXT NOT NULL UNIQUE,
                    created_at TEXT NOT NULL,
                    last_used_at TEXT NOT NULL
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


def _account_from_row(row: sqlite3.Row) -> SavedAccount:
    return SavedAccount(
        id=int(row["id"]),
        username=str(row["username"]),
        session_file=str(row["session_file"]),
        created_at=str(row["created_at"]),
        last_used_at=str(row["last_used_at"]),
    )


def _current_timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
