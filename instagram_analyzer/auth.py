"""Saved-account selection and Playwright authentication orchestration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import instaloader

from instagram_analyzer.accounts import AccountStore, SavedAccount
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
LEGACY_SESSION_PATH = Path("sessions/instagram_storage_state.json")


@dataclass(frozen=True, slots=True)
class AuthenticatedAccount:
    """An authenticated Instaloader and its Instagram username."""

    loader: instaloader.Instaloader
    username: str


class SessionIntegrationError(BrowserAuthenticationError):
    """Raised when Playwright state cannot authenticate Instaloader."""

    def __init__(self) -> None:
        super().__init__(
            "Instagram authentication could not be transferred to the analyzer."
        )


class AccountMismatchError(BrowserAuthenticationError):
    """Raised when re-authentication uses a different Instagram account."""

    def __init__(self, expected_username: str, actual_username: str) -> None:
        super().__init__(
            f"The browser session belongs to @{actual_username}, but @{expected_username} "
            "was selected. Log in with the selected account and try again."
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


def select_authenticated_account(
    account_store: AccountStore,
    *,
    status: StatusWriter = print,
    input_reader: InputReader = input,
) -> AuthenticatedAccount | None:
    """Select, add, delete, or exit from the reusable account menu."""
    _migrate_legacy_session(account_store, status=status)

    while True:
        accounts = account_store.list_accounts()
        if not accounts:
            status("No saved Instagram accounts.")
            status("")
            status("1. Login with a new account")
            status("0. Exit")
            choice = input_reader("\n> ").strip()
            if choice == "0":
                return None
            if choice == "1":
                authenticated = _authenticate_manually(
                    account_store,
                    status=status,
                    input_reader=input_reader,
                )
                if authenticated is not None:
                    return authenticated
                continue
            status("Invalid choice. Enter 0 or 1.")
            continue

        _print_account_menu(accounts, status)
        choice = input_reader("\n> ").strip()
        normalized_choice = choice.casefold()
        if choice == "0":
            return None
        if normalized_choice == "a":
            authenticated = _authenticate_manually(
                account_store,
                status=status,
                input_reader=input_reader,
            )
            if authenticated is not None:
                return authenticated
            continue
        if normalized_choice == "d":
            _delete_account_menu(
                account_store,
                accounts,
                status=status,
                input_reader=input_reader,
            )
            continue
        if choice.isdigit() and 1 <= int(choice) <= len(accounts):
            account = accounts[int(choice) - 1]
            authenticated = _use_saved_account(
                account_store,
                account,
                status=status,
                input_reader=input_reader,
            )
            if authenticated is not None:
                return authenticated
            continue
        status("Invalid choice. Select an account, A, D, or 0.")


def _use_saved_account(
    account_store: AccountStore,
    account: SavedAccount,
    *,
    status: StatusWriter,
    input_reader: InputReader,
) -> AuthenticatedAccount | None:
    status(f"Using @{account.username}")
    status("")
    status("Checking saved session...")
    session_path = account_store.session_path(account)
    browsers = detect_installed_browsers()

    if session_path.is_file() and browsers:
        try:
            cookies = load_saved_browser_session(browsers[0], session_path)
            try:
                loader, authenticated_username = _create_authenticated_loader(cookies)
            finally:
                cookies.clear()
        except (SavedSessionExpiredError, SessionIntegrationError):
            status("Session expired.")
        except BrowserLaunchError as error:
            status(str(error))
        else:
            if authenticated_username.casefold() == account.username.casefold():
                account_store.mark_used(account.id)
                status("Session is valid.")
                return AuthenticatedAccount(loader, authenticated_username)
            status("Saved session belongs to a different Instagram account.")
    elif not session_path.is_file():
        status("Saved session file is missing.")
    else:
        raise NoSupportedBrowserError

    status(f"Log in again as @{account.username} to update the session.")
    return _authenticate_manually(
        account_store,
        expected_account=account,
        status=status,
        input_reader=input_reader,
    )


def _authenticate_manually(
    account_store: AccountStore,
    *,
    expected_account: SavedAccount | None = None,
    status: StatusWriter,
    input_reader: InputReader,
) -> AuthenticatedAccount | None:
    browsers = detect_installed_browsers()
    if not browsers:
        raise NoSupportedBrowserError
    browser_option = _choose_browser(browsers, input_reader, status)
    if browser_option is None:
        return None

    pending_path = account_store.sessions_directory / f".pending-{uuid4().hex}.json"
    cookies: list[CookieData] = []
    try:
        cookies = perform_manual_browser_login(
            browser_option,
            pending_path,
            status=status,
        )
        loader, authenticated_username = _create_authenticated_loader(cookies)
        if expected_account and (
            authenticated_username.casefold() != expected_account.username.casefold()
        ):
            raise AccountMismatchError(
                expected_account.username, authenticated_username
            )

        existing_account = account_store.get_by_username(authenticated_username)
        final_path = account_store.session_path_for_username(authenticated_username)
        pending_path.replace(final_path)
        final_path.chmod(0o600)
        saved_account = account_store.save_account(
            authenticated_username, final_path.name
        )
        if existing_account is not None:
            previous_path = account_store.session_path(existing_account)
            if previous_path != final_path:
                try:
                    previous_path.unlink(missing_ok=True)
                except OSError:
                    status("The previous session file could not be removed.")
        if expected_account is not None:
            status("Session updated.")
        elif existing_account is not None:
            status(f"@{authenticated_username} is already saved.")
            status("Session updated.")
        else:
            status(f"Logged in as: @{authenticated_username}")
            status("Account saved.")
        account_store.mark_used(saved_account.id)
        return AuthenticatedAccount(loader, authenticated_username)
    finally:
        cookies.clear()
        pending_path.unlink(missing_ok=True)


def _delete_account_menu(
    account_store: AccountStore,
    accounts: list[SavedAccount],
    *,
    status: StatusWriter,
    input_reader: InputReader,
) -> None:
    status("")
    status("Choose account to delete:")
    status("")
    for index, account in enumerate(accounts, start=1):
        status(f"{index}. @{account.username}")
    status("0. Back")

    while True:
        choice = input_reader("\n> ").strip()
        if choice == "0":
            return
        if choice.isdigit() and 1 <= int(choice) <= len(accounts):
            account = accounts[int(choice) - 1]
            break
        status("Invalid choice. Enter a number shown in the menu.")

    status("")
    status(f"Delete @{account.username}?")
    status("")
    status("1. Yes")
    status("0. No")
    while True:
        confirmation = input_reader("\n> ").strip()
        if confirmation == "0":
            return
        if confirmation == "1":
            break
        status("Invalid choice. Enter 0 or 1.")

    deleted_account = account_store.delete_account(account.id)
    if deleted_account is None:
        status("The selected account no longer exists.")
        return
    session_path = account_store.session_path(deleted_account)
    try:
        session_path.unlink(missing_ok=True)
    except OSError:
        status("Account metadata was removed, but its session file could not be deleted.")
        return
    status(f"@{deleted_account.username} was removed.")


def _print_account_menu(
    accounts: list[SavedAccount],
    status: StatusWriter,
) -> None:
    status("Saved Instagram accounts:")
    status("")
    for index, account in enumerate(accounts, start=1):
        status(f"{index}. @{account.username}")
    status("")
    status("A. Add another account")
    status("D. Delete saved account")
    status("0. Exit")


def _choose_browser(
    browsers: list[BrowserOption],
    input_reader: InputReader,
    status: StatusWriter,
) -> BrowserOption | None:
    status("")
    status("Choose browser:")
    status("")
    for index, browser in enumerate(browsers, start=1):
        status(f"{index}. {browser.display_name}")
    status("0. Back")

    while True:
        choice = input_reader("\n> ").strip()
        if choice == "0":
            return None
        if choice.isdigit() and 1 <= int(choice) <= len(browsers):
            return browsers[int(choice) - 1]
        status("Invalid choice. Enter a number shown in the menu.")


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


def _migrate_legacy_session(
    account_store: AccountStore,
    *,
    status: StatusWriter,
) -> None:
    if account_store.list_accounts() or not LEGACY_SESSION_PATH.is_file():
        return
    browsers = detect_installed_browsers()
    if not browsers:
        return

    status("Checking existing session for migration...")
    cookies: list[CookieData] = []
    try:
        cookies = load_saved_browser_session(browsers[0], LEGACY_SESSION_PATH)
        _, authenticated_username = _create_authenticated_loader(cookies)
        final_path = account_store.session_path_for_username(authenticated_username)
        LEGACY_SESSION_PATH.replace(final_path)
        final_path.chmod(0o600)
        account_store.save_account(authenticated_username, final_path.name)
    except BrowserAuthenticationError:
        status("Existing session could not be migrated.")
    else:
        status(f"Existing session migrated for @{authenticated_username}.")
    finally:
        cookies.clear()


def _is_instagram_domain(domain: str) -> bool:
    normalized_domain = domain.lstrip(".").casefold()
    return normalized_domain == "instagram.com" or normalized_domain.endswith(
        ".instagram.com"
    )
