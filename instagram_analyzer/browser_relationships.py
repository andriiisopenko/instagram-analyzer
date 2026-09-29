"""Collect relationship lists from Instagram's authenticated browser interface."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Locator, Page, Response, async_playwright

from instagram_analyzer.browser_auth import BrowserOption, detect_installed_browsers
from instagram_analyzer.utils import normalize_username


ProgressCallback = Callable[[str, int, int | None], None]
RELATIONSHIP_PATH = re.compile(r"^/api/v1/friendships/\d+/(following|followers)/$")
USERNAME = re.compile(r"^[A-Za-z0-9._]{1,30}$")
MAX_PAGES = 1_000
PAGE_PAUSE_SECONDS = 0.75
MAX_LIST_PASSES = 3


class BrowserRelationshipError(ValueError):
    """Raised when the browser cannot obtain a complete relationship list."""


def collect_browser_relationships(
    session_path: Path,
    target_username: str,
    *,
    progress: ProgressCallback | None = None,
) -> tuple[set[str], set[str]]:
    """Return (following, followers) using the saved Playwright session."""
    target_username = normalize_username(target_username)
    browsers = detect_installed_browsers()
    if not browsers:
        raise BrowserRelationshipError("No supported browser is available for analysis.")
    browser_option = browsers[0]
    try:
        return asyncio.run(
            _collect_browser_relationships(
                session_path, target_username, browser_option, progress
            )
        )
    except PlaywrightError as error:
        raise BrowserRelationshipError(
            "Instagram's browser lists could not be opened. Check the saved session "
            "and try again later."
        ) from error


async def _collect_browser_relationships(
    session_path: Path,
    target_username: str,
    browser_option: BrowserOption,
    progress: ProgressCallback | None,
) -> tuple[set[str], set[str]]:
    async with async_playwright() as playwright:
        browser_type = getattr(playwright, browser_option.engine)
        launch_options = {"headless": True}
        if browser_option.channel:
            launch_options["channel"] = browser_option.channel
        else:
            launch_options["executable_path"] = str(browser_option.executable_path)
        browser = await browser_type.launch(**launch_options)
        try:
            context = await browser.new_context(storage_state=str(session_path))
            page = await context.new_page()
            response = await page.goto(
                f"https://www.instagram.com/{target_username}/",
                wait_until="domcontentloaded",
                timeout=30_000,
            )
            if response is None or response.status != 200:
                raise BrowserRelationshipError(
                    "Instagram did not open the target profile in the browser."
                )
            if "/accounts/login" in urlparse(page.url).path:
                raise BrowserRelationshipError(
                    "The saved Instagram session has expired. Log in again through the CLI."
                )

            # The two profile counters are the last numeric href="#" links.
            await _wait_for_counters(page)
            controls = page.locator('a[href="#"]')
            control_texts = await controls.all_inner_texts()
            numeric_controls = [
                index
                for index, value in enumerate(control_texts)
                if re.search(r"\d", value)
            ]
            if len(numeric_controls) < 2:
                raise BrowserRelationshipError(
                    "Instagram did not show the follower and following controls."
                )
            follower_index, following_index = numeric_controls[-2:]
            follower_total = _display_count(control_texts[follower_index])
            following_total = _display_count(control_texts[following_index])

            following = await _collect_with_retries(
                page, controls.nth(following_index), "following", following_total, progress
            )
            followers = await _collect_with_retries(
                page, controls.nth(follower_index), "followers", follower_total, progress
            )
            await context.close()
            return following, followers
        finally:
            await browser.close()


async def _collect_with_retries(
    page: Page,
    control: Locator,
    kind: str,
    expected_count: int | None,
    progress: ProgressCallback | None,
) -> set[str]:
    usernames: set[str] = set()
    if progress is not None:
        progress(kind, 0, expected_count)
    for pass_index in range(MAX_LIST_PASSES):
        await _collect_list(page, control, kind, expected_count, progress, usernames)
        await page.keyboard.press("Escape")
        await page.get_by_role("dialog").wait_for(state="hidden", timeout=10_000)
        # A one-account shortfall may be caused by a duplicate across pages.
        # Reopen once and merge before accepting display-count lag.
        retry_one_short = (
            pass_index == 0
            and expected_count is not None
            and len(usernames) == expected_count - 1
        )
        if _list_size_acceptable(len(usernames), expected_count) and not retry_one_short:
            return usernames
        if expected_count is not None and len(usernames) > expected_count + 1:
            break
        if pass_index < MAX_LIST_PASSES - 1:
            await asyncio.sleep(1.5)
            await page.reload(wait_until="domcontentloaded", timeout=30_000)
            await _wait_for_counters(page)
    _check_list_size(kind, len(usernames), expected_count)
    return usernames


async def _wait_for_counters(page: Page) -> None:
    await page.wait_for_function(
        """() => Array.from(document.querySelectorAll('a[href="#"]'))
            .filter(link => /\\d/.test(link.innerText)).length >= 2""",
        timeout=20_000,
    )


async def _collect_list(
    page: Page,
    control: Locator,
    kind: str,
    expected_count: int | None,
    progress: ProgressCallback | None,
    usernames: set[str],
) -> None:
    responses: asyncio.Queue[Response] = asyncio.Queue()

    def receive(response: Response) -> None:
        match = RELATIONSHIP_PATH.fullmatch(urlparse(response.url).path)
        if match and match.group(1) == kind:
            responses.put_nowait(response)

    page.on("response", receive)
    try:
        await control.click()
        dialog = page.get_by_role("dialog")
        await dialog.wait_for(state="visible", timeout=10_000)

        for page_number in range(MAX_PAGES):
            if page_number == 0:
                try:
                    response = await asyncio.wait_for(responses.get(), timeout=15)
                except TimeoutError as error:
                    raise BrowserRelationshipError(
                        f"Instagram did not provide the {kind} list."
                    ) from error
            else:
                response = await _next_page_response(responses, dialog, kind)

            if response.status != 200:
                raise BrowserRelationshipError(
                    f"Instagram rejected the {kind} list (HTTP {response.status})."
                )
            try:
                data = await response.json()
            except (ValueError, PlaywrightError) as error:
                raise BrowserRelationshipError(
                    f"Instagram returned an unreadable {kind} page."
                ) from error
            page_usernames, has_more = _parse_page(data, kind)
            previous_count = len(usernames)
            usernames.update(page_usernames)
            if progress is not None and len(usernames) > previous_count:
                progress(kind, len(usernames), expected_count)
            if not has_more:
                return
        raise BrowserRelationshipError(f"The {kind} list exceeded the page limit.")
    finally:
        page.remove_listener("response", receive)


async def _next_page_response(
    responses: asyncio.Queue[Response], dialog: Locator, kind: str
) -> Response:
    for _ in range(4):
        if not responses.empty():
            return responses.get_nowait()
        await asyncio.sleep(PAGE_PAUSE_SECONDS)
        scrolled = await dialog.evaluate(
            """dialog => {
                const list = Array.from(dialog.querySelectorAll('*')).find(
                    node => node.clientHeight > 50 &&
                            node.scrollHeight > node.clientHeight + 30
                );
                if (!list) return false;
                list.scrollTop = list.scrollHeight;
                return true;
            }"""
        )
        if not scrolled:
            break
        try:
            return await asyncio.wait_for(responses.get(), timeout=3)
        except TimeoutError:
            continue
    raise BrowserRelationshipError(
        f"Instagram stopped loading the {kind} list before the final page."
    )


def _parse_page(data: object, kind: str) -> tuple[set[str], bool]:
    users = data.get("users") if isinstance(data, dict) else None
    has_more = data.get("has_more") if isinstance(data, dict) else None
    if not isinstance(users, list) or not isinstance(has_more, bool):
        raise BrowserRelationshipError(f"Instagram returned an unexpected {kind} page.")
    usernames: set[str] = set()
    for user in users:
        username = user.get("username") if isinstance(user, dict) else None
        if not isinstance(username, str) or not USERNAME.fullmatch(username):
            raise BrowserRelationshipError(
                f"Instagram returned an invalid account in the {kind} list."
            )
        usernames.add(username.casefold())
    return usernames, has_more


def _display_count(label: str) -> int | None:
    """Parse exact counters; abbreviations such as 1.2K cannot be checked."""
    match = re.search(r"\d[\d\s,.]*", label)
    if match is None or re.search(r"[KMB]", label, re.IGNORECASE):
        return None
    return int(re.sub(r"\D", "", match.group()))


def _check_list_size(kind: str, actual: int, expected: int | None) -> None:
    # Instagram's displayed count can lag its list by one as accounts change.
    if not _list_size_acceptable(actual, expected):
        raise BrowserRelationshipError(
            f"Instagram returned {actual} {kind} accounts, but the profile shows "
            f"{expected}. No report was saved because the list may be incomplete."
        )


def _list_size_acceptable(actual: int, expected: int | None) -> bool:
    if expected is None:
        return True
    return not ((expected > 0 and actual == 0) or abs(actual - expected) > 1)
