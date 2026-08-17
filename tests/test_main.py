from unittest.mock import Mock

import main
from pytest import CaptureFixture, MonkeyPatch


def test_cli_shows_supported_target_formats(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    input_mock = Mock(return_value="invalid username")
    monkeypatch.setattr("builtins.input", input_mock)

    exit_code = main.run()

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Enter a profile URL, @username, or username." in captured.out
    assert "Example: https://instagram.com/example or @example" in captured.out
