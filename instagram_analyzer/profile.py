"""Instagram profile resolution and relationship collection."""

from __future__ import annotations

from collections.abc import Callable, Iterable

import instaloader
from tqdm import tqdm


def resolve_profile(
    loader: instaloader.Instaloader, username: str
) -> instaloader.Profile:
    """Resolve an Instagram profile by username."""
    return instaloader.Profile.from_username(loader.context, username)


ProgressCallback = Callable[[int, int | None], None]


def collect_following(
    profile: instaloader.Profile,
    *,
    progress: ProgressCallback | None = None,
    show_progress: bool = True,
) -> set[str]:
    """Collect usernames followed by the target profile."""
    return _collect_usernames(
        profile.get_followees(),
        description="Following",
        total=profile.followees,
        progress=progress,
        show_progress=show_progress,
    )


def collect_followers(
    profile: instaloader.Profile,
    *,
    progress: ProgressCallback | None = None,
    show_progress: bool = True,
) -> set[str]:
    """Collect usernames following the target profile."""
    return _collect_usernames(
        profile.get_followers(),
        description="Followers",
        total=profile.followers,
        progress=progress,
        show_progress=show_progress,
    )


def _collect_usernames(
    profiles: Iterable[instaloader.Profile],
    *,
    description: str,
    total: int | None,
    progress: ProgressCallback | None,
    show_progress: bool,
) -> set[str]:
    usernames: set[str] = set()
    for count, related_profile in enumerate(
        tqdm(
            profiles,
            desc=description,
            total=total,
            unit="account",
            dynamic_ncols=True,
            disable=not show_progress,
        ),
        start=1,
    ):
        usernames.add(related_profile.username.lower())
        if progress is not None:
            progress(count, total)
    return usernames
