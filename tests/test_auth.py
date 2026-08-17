import pickle
from pathlib import Path
from unittest.mock import Mock

import instaloader
from pytest import MonkeyPatch

from instagram_analyzer import auth


def test_authenticate_reuses_valid_session(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    session_path = tmp_path / "session-example"
    session_path.touch()
    loader = Mock()
    loader.test_login.return_value = "example"
    monkeypatch.setattr(auth, "create_loader", lambda: loader)
    password_reader = Mock()

    result = auth.authenticate(
        "example",
        session_directory=tmp_path,
        status=lambda _: None,
        password_reader=password_reader,
    )

    assert result is loader
    loader.load_session_from_file.assert_called_once_with("example", str(session_path))
    password_reader.assert_not_called()


def test_authenticate_logs_in_and_saves_session(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    loader = Mock()

    def save_session(filename: str) -> None:
        Path(filename).touch()

    loader.save_session_to_file.side_effect = save_session
    monkeypatch.setattr(auth, "create_loader", lambda: loader)

    result = auth.authenticate(
        "example",
        session_directory=tmp_path,
        status=lambda _: None,
        password_reader=lambda _: "secret",
    )

    assert result is loader
    loader.login.assert_called_once_with("example", "secret")
    loader.save_session_to_file.assert_called_once_with(str(tmp_path / "session-example"))
    assert (tmp_path / "session-example").stat().st_mode & 0o777 == 0o600
    assert tmp_path.stat().st_mode & 0o777 == 0o700


def test_authenticate_completes_two_factor_login(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    loader = Mock()
    loader.login.side_effect = instaloader.TwoFactorAuthRequiredException("2FA")

    def save_session(filename: str) -> None:
        Path(filename).touch()

    loader.save_session_to_file.side_effect = save_session
    monkeypatch.setattr(auth, "create_loader", lambda: loader)

    auth.authenticate(
        "example",
        session_directory=tmp_path,
        status=lambda _: None,
        input_reader=lambda _: "123456",
        password_reader=lambda _: "secret",
    )

    loader.two_factor_login.assert_called_once_with("123456")


def test_authenticate_replaces_corrupt_session(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    session_path = tmp_path / "session-example"
    session_path.write_bytes(b"invalid")
    stale_loader = Mock()
    stale_loader.load_session_from_file.side_effect = pickle.UnpicklingError()
    fresh_loader = Mock()

    def save_session(filename: str) -> None:
        Path(filename).touch()

    fresh_loader.save_session_to_file.side_effect = save_session
    loaders = iter([stale_loader, fresh_loader])
    monkeypatch.setattr(auth, "create_loader", lambda: next(loaders))

    result = auth.authenticate(
        "example",
        session_directory=tmp_path,
        status=lambda _: None,
        password_reader=lambda _: "secret",
    )

    assert result is fresh_loader
    fresh_loader.login.assert_called_once_with("example", "secret")
