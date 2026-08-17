"""Playwright browser discovery and manual Instagram authentication."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    async_playwright,
)


INSTAGRAM_LOGIN_URL = "https://www.instagram.com/accounts/login/"
INSTAGRAM_SESSION_CHECK_URL = "https://www.instagram.com/accounts/edit/"
DEFAULT_LOGIN_TIMEOUT_SECONDS = 600
LOGIN_POLL_INTERVAL_MILLISECONDS = 1_000

StatusWriter = Callable[[str], None]
CookieData = dict[str, Any]


class BrowserAuthenticationError(Exception):
    """Base class for expected Playwright authentication failures."""


class NoSupportedBrowserError(BrowserAuthenticationError):
    """Raised when no supported macOS browser is installed."""

    def __init__(self) -> None:
        super().__init__(
            "No supported browser was found.\n\n"
            "Install one of:\n"
            "- Google Chrome\n"
            "- Chromium\n"
            "- Firefox\n"
            "- Brave Browser\n"
            "- Microsoft Edge\n\n"
            "Or install Playwright Chromium with:\n"
            "python -m playwright install chromium"
        )


class BrowserLaunchError(BrowserAuthenticationError):
    """Raised when Playwright cannot launch an installed browser."""

    def __init__(self, browser_name: str) -> None:
        super().__init__(
            f"Unable to launch {browser_name}.\n"
            "Verify that the browser is installed and can be controlled by Playwright."
        )


class BrowserClosedError(BrowserAuthenticationError):
    """Raised when the user closes the login browser too early."""

    def __init__(self) -> None:
        super().__init__(
            "Browser was closed before authentication completed.\n"
            "Authentication cancelled."
        )


class LoginTimeoutError(BrowserAuthenticationError):
    """Raised when manual browser login exceeds the allowed time."""

    def __init__(self) -> None:
        super().__init__(
            "Instagram login timed out before authentication was confirmed."
        )


class SavedSessionExpiredError(BrowserAuthenticationError):
    """Raised when a saved Playwright state is no longer authenticated."""


@dataclass(frozen=True, slots=True)
class BrowserOption:
    """A locally installed browser that Playwright can attempt to launch."""

    key: str
    display_name: str
    engine: str
    executable_path: Path
    channel: str | None = None


BROWSER_CANDIDATES: tuple[BrowserOption, ...] = (
    BrowserOption(
        key="chrome",
        display_name="Google Chrome",
        engine="chromium",
        executable_path=Path(
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        ),
        channel="chrome",
    ),
    BrowserOption(
        key="chromium",
        display_name="Chromium",
        engine="chromium",
        executable_path=Path(
            "/Applications/Chromium.app/Contents/MacOS/Chromium"
        ),
    ),
    BrowserOption(
        key="firefox",
        display_name="Firefox",
        engine="firefox",
        executable_path=Path(
            "/Applications/Firefox.app/Contents/MacOS/firefox"
        ),
    ),
    BrowserOption(
        key="edge",
        display_name="Microsoft Edge",
        engine="chromium",
        executable_path=Path(
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"
        ),
        channel="msedge",
    ),
    BrowserOption(
        key="brave",
        display_name="Brave Browser",
        engine="chromium",
        executable_path=Path(
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser"
        ),
    ),
)


def detect_installed_browsers() -> list[BrowserOption]:
    """Return supported browsers found in standard macOS app locations."""
    installed: list[BrowserOption] = []
    for browser in BROWSER_CANDIDATES:
        executable_path = _find_browser_executable(browser.executable_path)
        if executable_path is not None:
            installed.append(
                BrowserOption(
                    key=browser.key,
                    display_name=browser.display_name,
                    engine=browser.engine,
                    executable_path=executable_path,
                    channel=(
                        browser.channel
                        if executable_path == browser.executable_path
                        else None
                    ),
                )
            )
    if not any(browser.key == "chromium" for browser in installed):
        managed_chromium = _find_playwright_chromium()
        if managed_chromium is not None:
            installed.append(
                BrowserOption(
                    key="chromium",
                    display_name="Chromium (Playwright)",
                    engine="chromium",
                    executable_path=managed_chromium,
                )
            )
    return installed


def load_saved_browser_session(
    browser_option: BrowserOption,
    session_path: Path,
) -> list[CookieData]:
    """Load a saved Playwright state and return validated Instagram cookies."""
    return asyncio.run(_load_saved_browser_session(browser_option, session_path))


async def _load_saved_browser_session(
    browser_option: BrowserOption,
    session_path: Path,
) -> list[CookieData]:
    try:
        async with async_playwright() as playwright:
            browser: Browser | None = None
            context: BrowserContext | None = None
            page: Page | None = None
            try:
                browser = await _launch_browser(
                    playwright, browser_option, headless=True
                )
                context = await browser.new_context(storage_state=str(session_path))
                page = await context.new_page()
                if not await _validate_authenticated_context(context, page):
                    raise SavedSessionExpiredError
                return await _instagram_cookies(context)
            except SavedSessionExpiredError:
                raise
            except PlaywrightError:
                raise SavedSessionExpiredError from None
            finally:
                await _close_playwright_resources(context, browser)
    except SavedSessionExpiredError:
        raise
    except PlaywrightError:
        raise BrowserLaunchError(browser_option.display_name) from None


def perform_manual_browser_login(
    browser_option: BrowserOption,
    session_path: Path,
    *,
    status: StatusWriter = print,
    timeout_seconds: int = DEFAULT_LOGIN_TIMEOUT_SECONDS,
) -> list[CookieData]:
    """Launch a headed browser and wait for the user to authenticate manually."""
    return asyncio.run(
        _perform_manual_browser_login(
            browser_option,
            session_path,
            status=status,
            timeout_seconds=timeout_seconds,
        )
    )


async def _perform_manual_browser_login(
    browser_option: BrowserOption,
    session_path: Path,
    *,
    status: StatusWriter,
    timeout_seconds: int,
) -> list[CookieData]:
    try:
        async with async_playwright() as playwright:
            browser: Browser | None = None
            context: BrowserContext | None = None
            page: Page | None = None
            try:
                browser = await _launch_browser(
                    playwright, browser_option, headless=False
                )
                context = await browser.new_context(no_viewport=True)
                page = await context.new_page()
                await page.goto(
                    INSTAGRAM_LOGIN_URL,
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                status("Browser opened.")
                status("")
                status("Log in to Instagram manually in the browser.")
                status(
                    "Complete any 2FA, security check, checkpoint, or confirmation "
                    "requested by Instagram."
                )
                status("")
                status("Waiting for successful Instagram login...")

                await _wait_for_successful_login(
                    browser,
                    context,
                    page,
                    timeout_seconds=timeout_seconds,
                )
                status("Instagram login successful.")
                status("Saving session...")
                session_path.parent.mkdir(parents=True, exist_ok=True)
                session_path.parent.chmod(0o700)
                await context.storage_state(path=str(session_path))
                session_path.chmod(0o600)
                cookies = await _instagram_cookies(context)
                status("Session saved.")
                return cookies
            finally:
                await _close_playwright_resources(context, browser)
    except (BrowserClosedError, LoginTimeoutError):
        raise
    except PlaywrightError:
        raise BrowserLaunchError(browser_option.display_name) from None


async def _launch_browser(
    playwright: Playwright,
    browser_option: BrowserOption,
    *,
    headless: bool,
) -> Browser:
    browser_type = getattr(playwright, browser_option.engine)
    launch_options: dict[str, Any] = {"headless": headless}
    if browser_option.channel:
        launch_options["channel"] = browser_option.channel
    else:
        launch_options["executable_path"] = str(browser_option.executable_path)
    return await browser_type.launch(**launch_options)


async def _wait_for_successful_login(
    browser: Browser,
    context: BrowserContext,
    page: Page,
    *,
    timeout_seconds: int,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            if not browser.is_connected() or page.is_closed():
                raise BrowserClosedError

            has_session = await _has_instagram_session_cookie(context)
            if has_session and _is_authenticated_url(page.url):
                if await _validate_authenticated_context(context, page):
                    return

            await page.wait_for_timeout(LOGIN_POLL_INTERVAL_MILLISECONDS)
        except BrowserClosedError:
            raise
        except PlaywrightError:
            raise BrowserClosedError from None

    raise LoginTimeoutError


async def _validate_authenticated_context(
    context: BrowserContext,
    page: Page,
) -> bool:
    if not await _has_instagram_session_cookie(context):
        return False
    try:
        await page.goto(
            INSTAGRAM_SESSION_CHECK_URL,
            wait_until="domcontentloaded",
            timeout=30_000,
        )
    except PlaywrightError:
        return False
    return _is_authenticated_url(page.url) and await _has_instagram_session_cookie(
        context
    )


async def _instagram_cookies(context: BrowserContext) -> list[CookieData]:
    return [
        cookie
        for cookie in await context.cookies(["https://www.instagram.com/"])
        if _is_instagram_domain(str(cookie.get("domain", "")))
    ]


async def _has_instagram_session_cookie(context: BrowserContext) -> bool:
    return any(
        cookie.get("name") == "sessionid" and cookie.get("value")
        for cookie in await _instagram_cookies(context)
    )


def _is_authenticated_url(url: str) -> bool:
    unauthenticated_paths = (
        "/accounts/login",
        "/accounts/signup",
        "/challenge/",
        "/checkpoint/",
        "/auth_platform/",
    )
    normalized_url = url.casefold()
    return "instagram.com" in normalized_url and not any(
        path in normalized_url for path in unauthenticated_paths
    )


def _is_instagram_domain(domain: str) -> bool:
    normalized_domain = domain.lstrip(".").casefold()
    return normalized_domain == "instagram.com" or normalized_domain.endswith(
        ".instagram.com"
    )


def _find_browser_executable(system_path: Path) -> Path | None:
    if system_path.is_file():
        return system_path
    try:
        relative_path = system_path.relative_to("/Applications")
    except ValueError:
        return None
    user_path = Path.home() / "Applications" / relative_path
    return user_path if user_path.is_file() else None


def _find_playwright_chromium() -> Path | None:
    return asyncio.run(_find_playwright_chromium_async())


async def _find_playwright_chromium_async() -> Path | None:
    try:
        async with async_playwright() as playwright:
            executable_path = Path(playwright.chromium.executable_path)
    except PlaywrightError:
        return None
    return executable_path if executable_path.is_file() else None


async def _close_playwright_resources(
    context: BrowserContext | None,
    browser: Browser | None,
) -> None:
    if context is not None:
        await _close_resource(context)
    if browser is not None and browser.is_connected():
        await _close_resource(browser)


async def _close_resource(resource: BrowserContext | Browser) -> None:
    try:
        await resource.close()
    except PlaywrightError as error:
        if type(error).__name__ != "TargetClosedError":
            raise
