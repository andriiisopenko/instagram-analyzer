from datetime import datetime
from pathlib import Path

from instagram_analyzer.history import CheckedAccount
from instagram_analyzer.output import save_html_report, save_usernames


def test_save_usernames_writes_unnumbered_entries(tmp_path: Path) -> None:
    output_path = save_usernames(
        ["alice", "bob"],
        "example",
        output_directory=tmp_path,
    )

    assert output_path == tmp_path / "non_followers_example.txt"
    assert output_path.read_text(encoding="utf-8") == "@alice\n@bob\n"


def test_html_report_is_standalone_and_preserves_checked_markers(
    tmp_path: Path,
) -> None:
    output_path = save_html_report(
        [CheckedAccount("alice", True), CheckedAccount("bob", False)],
        "login_account",
        "target_account",
        10,
        8,
        datetime(2026, 8, 17, 19, 30, 15),
        html_directory=tmp_path,
    )

    contents = output_path.read_text(encoding="utf-8")
    assert output_path.name == "2026-08-17_19-30-15.html"
    assert "<style>" in contents
    assert "@target_account" in contents
    assert "Previously checked" in contents
    assert "[checked]" in contents
    assert "cdn" not in contents.casefold()
