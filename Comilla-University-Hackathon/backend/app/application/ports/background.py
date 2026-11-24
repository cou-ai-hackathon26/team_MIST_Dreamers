"""Port: runs work later or in the background (SMS, call-back, async voice answer)."""

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class BackgroundRunner(Protocol):
    def submit(self, fn: Callable[..., Any], *args: Any, delay_s: float = 0) -> None:
        """Runs fn(*args) after `delay_s` seconds without blocking the caller."""
        ...
