from unittest.mock import Mock

import main
import pytest
from pytest import CaptureFixture, MonkeyPatch

from instagram_analyzer.browser_relationships import BrowserRelationshipError


def test_cli_shows_supported_target_formats(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    input_mock = Mock(side_effect=["2", "invalid username"])
    monkeypatch.setattr("builtins.input", input_mock)
    monkeypatch.setattr(
        main,
        "select_authenticated_account",
        Mock(return_value=Mock(username="login_account")),
    )

    exit_code = main.run()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Enter a profile URL, @username, or username." in captured.out
    assert "Example: https://instagram.com/example or @example" in captured.out


def test_incomplete_collection_does_not_save_report_or_history(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        main,
        "collect_browser_relationships",
        Mock(side_effect=BrowserRelationshipError("Instagram returned an incomplete list.")),
    )
    save_report = Mock()
    monkeypatch.setattr(main, "save_history_report", save_report)
    history_store = Mock()
    account_store = Mock()
    account_store.get_by_username.return_value = Mock()

    with pytest.raises(BrowserRelationshipError):
        main._run_analysis(
            Mock(username="saved_account", loader=Mock()),
            "target_account",
            Mock(),
            history_store,
            account_store,
        )

    save_report.assert_not_called()
    history_store.record_results.assert_not_called()
