"""Pure set-based relationship analysis."""

from __future__ import annotations


def find_non_followers(following: set[str], followers: set[str]) -> set[str]:
    """Return accounts that are followed but do not follow back."""
    return following - followers


def find_not_followed_back(following: set[str], followers: set[str]) -> set[str]:
    """Return followers that the target account does not follow back."""
    return followers - following


def find_mutual_follows(following: set[str], followers: set[str]) -> set[str]:
    """Return accounts present in both relationship sets."""
    return following & followers

