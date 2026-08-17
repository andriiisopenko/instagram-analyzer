"""Conservative delay configuration layered on Instaloader rate limiting."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class DelaySettings:
    """Optional delay range between large logical operations."""

    minimum_seconds: float = 0.75
    maximum_seconds: float = 1.5

    def __post_init__(self) -> None:
        if self.minimum_seconds < 0 or self.maximum_seconds < self.minimum_seconds:
            raise ValueError("Delay range must be non-negative and ordered.")


def pause_between_operations(
    settings: DelaySettings = DelaySettings(),
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Pause once between operations without replacing built-in rate limiting."""
    sleep(random.uniform(settings.minimum_seconds, settings.maximum_seconds))

