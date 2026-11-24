"""Shared helpers for the LLM adapters: JSON parsing and call statistics."""

import json
import re
import threading
from dataclasses import dataclass, field
from typing import Any

from app.domain.errors import LLMUnavailable

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


def parse_json_object(text: str) -> dict[str, Any]:
    """The model's reply as a dict. Tolerates ```json fences; anything else raises LLMUnavailable."""
    cleaned = text.strip()
    match = _FENCE.match(cleaned)
    if match:
        cleaned = match.group(1)
    try:
        value = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMUnavailable("the model did not return valid JSON") from exc
    if not isinstance(value, dict):
        raise LLMUnavailable("the model returned JSON that is not an object")
    return value


@dataclass
class LLMStats:
    """Counts and times every call (for logs and llm_calls). Safe to share between threads."""

    calls: int = 0
    failures: int = 0
    seconds: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)

    def record(self, seconds: float, ok: bool) -> None:
        with self._lock:
            self.calls += 1
            self.failures += 0 if ok else 1
            self.seconds += seconds
