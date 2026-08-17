"""Input normalization helpers."""

from __future__ import annotations

import re
from urllib.parse import urlparse


USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_](?:[A-Za-z0-9._]{0,28}[A-Za-z0-9_])?$")
RESERVED_PATHS = {
    "about",
    "accounts",
    "developer",
    "directory",
    "explore",
    "legal",
    "p",
    "reel",
    "reels",
    "stories",
}


def normalize_username(value: str) -> str:
    """Return a normalized Instagram username from a URL or username-like input.

    Raises:
        ValueError: If the input is empty, malformed, or not a profile reference.
    """
    candidate = value.strip()
    if not candidate:
        raise ValueError("Instagram profile cannot be empty.")

    if candidate.startswith("@"):
        candidate = candidate[1:]
    elif "://" in candidate:
        candidate = _username_from_url(candidate)
    elif "/" in candidate or "?" in candidate or "#" in candidate:
        raise ValueError("Enter an Instagram profile URL or username.")

    if not USERNAME_PATTERN.fullmatch(candidate):
        raise ValueError(
            "Invalid Instagram username. Use 1-30 letters, numbers, periods, or underscores."
        )

    return candidate.lower()


def _username_from_url(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Instagram URL must use http or https.")

    hostname = (parsed.hostname or "").lower()
    if hostname not in {"instagram.com", "www.instagram.com"}:
        raise ValueError("URL must point to instagram.com.")

    path_parts = [part for part in parsed.path.split("/") if part]
    if len(path_parts) != 1 or path_parts[0].lower() in RESERVED_PATHS:
        raise ValueError("URL must point directly to an Instagram profile.")

    return path_parts[0]

