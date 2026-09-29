import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from pytest import MonkeyPatch

import instagram_analyzer.browser_relationships as browser_relationships
from instagram_analyzer.browser_relationships import (
    BrowserRelationshipError,
    _check_list_size,
    _display_count,
    _parse_page,
)


def test_browser_page_parses_accounts_and_completion_flag() -> None:
    usernames, has_more = _parse_page(
        {"users": [{"username": "Alice"}, {"username": "bob"}], "has_more": False},
        "following",
    )

    assert usernames == {"alice", "bob"}
    assert has_more is False


def test_browser_page_requires_completion_flag() -> None:
    with pytest.raises(BrowserRelationshipError, match="unexpected followers page"):
        _parse_page({"users": []}, "followers")


def test_browser_count_allows_one_account_of_display_lag() -> None:
    assert _display_count("Стежить: 136") == 136
    _check_list_size("following", 135, 136)

    with pytest.raises(BrowserRelationshipError, match="No report was saved"):
        _check_list_size("following", 12, 136)

    with pytest.raises(BrowserRelationshipError, match="No report was saved"):
        _check_list_size("following", 0, 1)


def test_incomplete_first_pass_collects_missing_accounts_on_second_pass(
    monkeypatch: MonkeyPatch,
) -> None:
    calls = 0

    async def collect_page(*args: object) -> None:
        nonlocal calls
        usernames = args[-1]
        assert isinstance(usernames, set)
        if calls == 0:
            usernames.update(f"account{index}" for index in range(133))
        else:
            usernames.update({"account133", "account134"})
        calls += 1

    monkeypatch.setattr(browser_relationships, "_collect_list", collect_page)
    monkeypatch.setattr(browser_relationships, "_wait_for_counters", AsyncMock())
    monkeypatch.setattr(browser_relationships.asyncio, "sleep", AsyncMock())
    dialog = Mock(wait_for=AsyncMock())
    page = Mock()
    page.keyboard.press = AsyncMock()
    page.reload = AsyncMock()
    page.get_by_role.return_value = dialog

    usernames = asyncio.run(
        browser_relationships._collect_with_retries(
            page, Mock(), "following", 136, None
        )
    )

    assert len(usernames) == 135
    assert calls == 2
    assert page.keyboard.press.await_count == 2


def test_one_account_shortfall_gets_a_second_pass(
    monkeypatch: MonkeyPatch,
) -> None:
    calls = 0

    async def collect_page(*args: object) -> None:
        nonlocal calls
        usernames = args[-1]
        assert isinstance(usernames, set)
        usernames.add("alice")
        if calls:
            usernames.add("bob")
        calls += 1

    monkeypatch.setattr(browser_relationships, "_collect_list", collect_page)
    monkeypatch.setattr(browser_relationships, "_wait_for_counters", AsyncMock())
    monkeypatch.setattr(browser_relationships.asyncio, "sleep", AsyncMock())
    dialog = Mock(wait_for=AsyncMock())
    page = Mock()
    page.keyboard.press = AsyncMock()
    page.reload = AsyncMock()
    page.get_by_role.return_value = dialog

    usernames = asyncio.run(
        browser_relationships._collect_with_retries(page, Mock(), "following", 2, None)
    )

    assert usernames == {"alice", "bob"}
    assert calls == 2


def test_duplicate_page_does_not_repeat_progress() -> None:
    first_response = Mock(
        url="https://www.instagram.com/api/v1/friendships/1/following/",
        status=200,
        json=AsyncMock(return_value={"users": [{"username": "Alice"}], "has_more": True}),
    )
    final_response = Mock(
        url="https://www.instagram.com/api/v1/friendships/1/following/",
        status=200,
        json=AsyncMock(return_value={"users": [{"username": "Alice"}], "has_more": False}),
    )
    listeners = []
    page = Mock()
    page.on.side_effect = lambda event, callback: listeners.append(callback)
    page.get_by_role.return_value = Mock(wait_for=AsyncMock())

    async def click() -> None:
        listeners[0](first_response)
        listeners[0](final_response)

    control = Mock(click=click)
    progress = Mock()
    usernames: set[str] = set()

    asyncio.run(
        browser_relationships._collect_list(
            page, control, "following", 2, progress, usernames
        )
    )

    assert usernames == {"alice"}
    progress.assert_called_once_with("following", 1, 2)
