"""Instaloader authentication and local session handling."""

from __future__ import annotations

import getpass
import pickle
from collections.abc import Callable
from pathlib import Path

import instaloader


StatusWriter = Callable[[str], None]
InputReader = Callable[[str], str]
PasswordReader = Callable[[str], str]


def create_loader() -> instaloader.Instaloader:
    """Create an Instaloader configured for metadata queries, not downloads."""
    return instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
        max_connection_attempts=3,
    )


def authenticate(
    login_username: str,
    *,
    session_directory: Path = Path("sessions"),
    status: StatusWriter = print,
    input_reader: InputReader = input,
    password_reader: PasswordReader = getpass.getpass,
) -> instaloader.Instaloader:
    """Load a valid session or authenticate interactively and save a new session."""
    session_directory.mkdir(parents=True, exist_ok=True)
    session_directory.chmod(0o700)
    session_path = session_directory / f"session-{login_username}"
    loader = create_loader()

    status("Checking saved session...")
    if session_path.is_file():
        status("Session found.")
        status("Validating session...")
        try:
            loader.load_session_from_file(login_username, str(session_path))
            authenticated_as = loader.test_login()
        except (OSError, ValueError, EOFError, pickle.UnpicklingError):
            authenticated_as = None

        if authenticated_as and authenticated_as.casefold() == login_username.casefold():
            status("Login successful.")
            return loader

        status("Saved session is invalid or expired. Logging in again.")
        loader = create_loader()
    else:
        status("No saved session found.")

    password = password_reader("Password: ")
    if not password:
        raise ValueError("Password cannot be empty.")

    status("Logging in...")
    try:
        loader.login(login_username, password)
    except instaloader.TwoFactorAuthRequiredException:
        status("Two-factor authentication required.")
        two_factor_code = input_reader("Enter 2FA code: ").strip()
        if not two_factor_code:
            raise ValueError("2FA code cannot be empty.") from None
        loader.two_factor_login(two_factor_code)

    loader.save_session_to_file(str(session_path))
    session_path.chmod(0o600)
    status("Login successful.")
    return loader
