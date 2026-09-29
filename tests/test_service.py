from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from pytest import MonkeyPatch

from instagram_analyzer.auth import AuthenticatedAccount
from instagram_analyzer.history import HistoryStore
from instagram_analyzer.service import run_saved_account_analysis


def test_service_creates_reports_from_browser_lists(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    account_store = Mock()
    account_store.list_accounts.return_value = [
        SimpleNamespace(id=1, username="saved_account")
    ]
    account_store.session_path.return_value = tmp_path / "session.json"
    monkeypatch.setattr(
        "instagram_analyzer.service.authenticate_saved_account",
        Mock(return_value=AuthenticatedAccount(Mock(), "saved_account")),
    )
    browser_collector = Mock(return_value=({"alice", "bob"}, {"alice"}))
    monkeypatch.setattr(
        "instagram_analyzer.service.collect_browser_relationships",
        browser_collector,
    )

    result = run_saved_account_analysis(
        1,
        "target_account",
        account_store=account_store,
        history_store=HistoryStore(tmp_path / "history.db"),
        history_directory=tmp_path / "txt",
        html_directory=tmp_path / "html",
    )

    assert result.following_count == 2
    assert result.follower_count == 1
    assert [account.username for account in result.accounts] == ["bob"]
    assert result.txt_report_path.is_file()
    assert result.html_report_path.is_file()
    browser_collector.assert_called_once()
