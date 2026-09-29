"""Shared non-interactive analysis orchestration for CLI and web frontends."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from instagram_analyzer.accounts import AccountStore
from instagram_analyzer.analyzer import find_non_followers
from instagram_analyzer.auth import authenticate_saved_account
from instagram_analyzer.browser_relationships import collect_browser_relationships
from instagram_analyzer.history import CheckedAccount, HistoryStore
from instagram_analyzer.output import save_history_report, save_html_report
from instagram_analyzer.utils import normalize_username


ProgressWriter = Callable[[str, int, str], None]


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Complete result of one finished analysis."""

    authenticated_username: str
    target_username: str
    started_at: datetime
    completed_at: datetime
    following_count: int
    follower_count: int
    accounts: tuple[CheckedAccount, ...]
    txt_report_path: Path
    html_report_path: Path

    @property
    def total_analyzed(self) -> int:
        return len(self.accounts)

    @property
    def previously_checked_count(self) -> int:
        return sum(account.previously_checked for account in self.accounts)

    @property
    def new_count(self) -> int:
        return self.total_analyzed - self.previously_checked_count


def run_saved_account_analysis(
    account_id: int,
    target: str,
    *,
    account_store: AccountStore,
    history_store: HistoryStore,
    progress: ProgressWriter | None = None,
    history_directory: Path = Path("output/history"),
    html_directory: Path = Path("reports/html"),
) -> AnalysisResult:
    """Run the existing analysis flow for a saved account."""
    target_username = normalize_username(target)
    accounts = account_store.list_accounts()
    saved_account = next((account for account in accounts if account.id == account_id), None)
    if saved_account is None:
        raise ValueError("Saved Instagram account was not found.")

    started_at = datetime.now().astimezone()
    _progress(progress, "authenticating", 5, "Checking saved Instagram session")
    authenticated = authenticate_saved_account(account_store, saved_account)

    _progress(progress, "loading_profile", 15, f"Loading @{target_username}")

    def relationship_progress(kind: str, current: int, total: int | None) -> None:
        if kind == "following":
            percent = _collection_percent(22, 25, current, total)
            _progress(progress, "collecting_following", percent, "Collecting following")
        else:
            percent = _collection_percent(52, 28, current, total)
            _progress(progress, "collecting_followers", percent, "Collecting followers")

    following, followers = collect_browser_relationships(
        account_store.session_path(saved_account),
        target_username,
        progress=relationship_progress,
    )

    _progress(progress, "analyzing", 84, "Comparing followers and following")
    non_followers = sorted(find_non_followers(following, followers))
    checked_accounts = history_store.classify_accounts(target_username, non_followers)

    _progress(progress, "creating_reports", 92, "Creating TXT and HTML reports")
    txt_report_path = save_history_report(
        checked_accounts,
        authenticated.username,
        target_username,
        len(following),
        len(followers),
        started_at,
        history_directory=history_directory,
    )
    html_report_path = save_html_report(
        checked_accounts,
        authenticated.username,
        target_username,
        len(following),
        len(followers),
        started_at,
        html_directory=html_directory,
    )
    history_store.record_results(target_username, non_followers, started_at)
    completed_at = datetime.now().astimezone()
    _progress(progress, "finalizing", 99, "Finalizing analysis result")
    return AnalysisResult(
        authenticated_username=authenticated.username,
        target_username=target_username,
        started_at=started_at,
        completed_at=completed_at,
        following_count=len(following),
        follower_count=len(followers),
        accounts=tuple(checked_accounts),
        txt_report_path=txt_report_path,
        html_report_path=html_report_path,
    )


def _collection_percent(start: int, span: int, current: int, total: int | None) -> int:
    if not total or total <= 0:
        return start
    return min(start + span, start + int(span * current / total))


def _progress(
    writer: ProgressWriter | None,
    stage: str,
    percent: int,
    message: str,
) -> None:
    if writer is not None:
        writer(stage, percent, message)
