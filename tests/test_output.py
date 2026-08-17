from pathlib import Path

from instagram_analyzer.output import save_usernames


def test_save_usernames_writes_unnumbered_entries(tmp_path: Path) -> None:
    output_path = save_usernames(
        ["alice", "bob"],
        "example",
        output_directory=tmp_path,
    )

    assert output_path == tmp_path / "non_followers_example.txt"
    assert output_path.read_text(encoding="utf-8") == "@alice\n@bob\n"
