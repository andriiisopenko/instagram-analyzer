"""Manual Playwright authentication integrated with Instaloader."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import instaloader

from instagram_analyzer.browser_auth import (
    BrowserAuthenticationError,
    BrowserLaunchError,
    BrowserOption,
    NoSupportedBrowserError,
    SavedSessionExpiredError,
    detect_installed_browsers,
    load_saved_browser_session,
    perform_manual_browser_login,
)


StatusWriter = Callable[[str], None]
InputReader = Callable[[str], str]
CookieData = dict[str, Any]


class AuthenticationCancelledError(BrowserAuthenticationError):
    """Raised when the user cancels browser authentication."""

    def __init__(self) -> None:
        super().__init__("Authentication cancelled.")


class SessionIntegrationError(BrowserAuthenticationError):
    """Raised when Playwright state cannot authenticate Instaloader."""

    def __init__(self) -> None:
        super().__init__(
            "Instagram authentication could not be transferred to the analyzer."
        )


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
    *,
    session_path: Path = Path("sessions/instagram_storage_state.json"),
    status: StatusWriter = print,
    input_reader: InputReader = input,
) -> instaloader.Instaloader:
    """Reuse a Playwright state or launch one manual browser login."""
    session_path.parent.mkdir(parents=True, exist_ok=True)
    session_path.parent.chmod(0o700)
    browsers = detect_installed_browsers()

    status("Checking saved session...")
    if session_path.is_file():
        status("Saved session found.")
        status("Validating session...")
        if not browsers:
            raise NoSupportedBrowserError
        try:
            cookies = load_saved_browser_session(browsers[0], session_path)
            loader, authenticated_username = _create_authenticated_loader(cookies)
        except (SavedSessionExpiredError, SessionIntegrationError):
            status("Session expired.")
            session_path.unlink(missing_ok=True)
        except BrowserLaunchError as error:
            status(str(error))
            status("No valid saved session found.")
        else:
            status("Session is valid.")
            status(f"Authenticated as @{authenticated_username}.")
            return loader
    else:
        status("No valid saved session found.")

    if not browsers:
        raise NoSupportedBrowserError

    browser_option = _choose_browser(browsers, input_reader, status)
    cookies = perform_manual_browser_login(
        browser_option,
        session_path,
        status=status,
    )
    try:
        loader, authenticated_username = _create_authenticated_loader(cookies)
    except SessionIntegrationError:
        session_path.unlink(missing_ok=True)
        raise
    finally:
        cookies.clear()

    status(f"Authenticated as @{authenticated_username}.")
    return loader


def _create_authenticated_loader(
    cookies: list[CookieData],
) -> tuple[instaloader.Instaloader, str]:
    loader = create_loader()
    instagram_cookie_values = {
        str(cookie["name"]): str(cookie["value"])
        for cookie in cookies
        if _is_instagram_domain(str(cookie.get("domain", "")))
    }
    if not instagram_cookie_values:
        raise SessionIntegrationError

    loader.context.update_cookies(instagram_cookie_values)
    authenticated_username = loader.test_login()
    if not authenticated_username:
        raise SessionIntegrationError
    loader.context.username = authenticated_username
    return loader, authenticated_username


def _choose_browser(
    browsers: list[BrowserOption],
    input_reader: InputReader,
    status: StatusWriter,
) -> BrowserOption:
    status("")
    status("Choose browser:")
    status("")
    for index, browser in enumerate(browsers, start=1):
        status(f"{index}. {browser.display_name}")
    status("0. Cancel")

    while True:
        choice = input_reader("\n> ").strip()
        if choice == "0":
            raise AuthenticationCancelledError
        if choice.isdigit() and 1 <= int(choice) <= len(browsers):
            return browsers[int(choice) - 1]
        status("Invalid choice. Enter a number shown in the menu.")


def _is_instagram_domain(domain: str) -> bool:
    normalized_domain = domain.lstrip(".").casefold()
    return normalized_domain == "instagram.com" or normalized_domain.endswith(
        ".instagram.com"
    )
