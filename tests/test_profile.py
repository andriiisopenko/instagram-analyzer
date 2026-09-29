from types import SimpleNamespace

import pytest

from instagram_analyzer.profile import (
    IncompleteRelationshipDataError,
    collect_followers,
    collect_following,
)


def test_positive_count_with_empty_relationship_list_fails() -> None:
    profile = SimpleNamespace(
        followees=136,
        get_followees=lambda: iter(()),
    )

    with pytest.raises(IncompleteRelationshipDataError, match="0 entries in the following list, but the profile reports 136"):
        collect_following(profile, show_progress=False)


def test_partially_collected_relationship_list_fails() -> None:
    profile = SimpleNamespace(
        followers=3,
        get_followers=lambda: iter(
            (SimpleNamespace(username="Alice"), SimpleNamespace(username="Bob"))
        ),
    )

    with pytest.raises(IncompleteRelationshipDataError, match="2 entries in the followers list, but the profile reports 3"):
        collect_followers(profile, show_progress=False)


def test_genuinely_empty_relationship_list_succeeds() -> None:
    profile = SimpleNamespace(
        followers=0,
        get_followers=lambda: iter(()),
    )

    assert collect_followers(profile, show_progress=False) == set()
