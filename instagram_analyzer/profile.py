"""Instagram profile resolution and relationship collection."""

from __future__ import annotations

from collections.abc import Iterable

import instaloader
from tqdm import tqdm


def resolve_profile(
    loader: instaloader.Instaloader, username: str
) -> instaloader.Profile:
    """Resolve an Instagram profile by username."""
    return instaloader.Profile.from_username(loader.context, username)


def collect_following(profile: instaloader.Profile) -> set[str]:
    """Collect usernames followed by the target profile."""
    return _collect_usernames(
        profile.get_followees(),
        description="Following",
        total=profile.followees,
    )


def collect_followers(profile: instaloader.Profile) -> set[str]:
    """Collect usernames following the target profile."""
    return _collect_usernames(
        profile.get_followers(),
        description="Followers",
        total=profile.followers,
    )


def _collect_usernames(
    profiles: Iterable[instaloader.Profile],
    *,
    description: str,
    total: int | None,
) -> set[str]:
    return {
        related_profile.username.lower()
        for related_profile in tqdm(
            profiles,
            desc=description,
            total=total,
            unit="account",
            dynamic_ncols=True,
        )
    }

