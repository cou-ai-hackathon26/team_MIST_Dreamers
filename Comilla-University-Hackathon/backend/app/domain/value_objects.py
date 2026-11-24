"""Small immutable values used everywhere: Channel, AnswerStatus, RouterSource, PhoneNumber."""

import re
from dataclasses import dataclass
from enum import StrEnum

from app.domain.errors import InvalidPhone


class Channel(StrEnum):
    VOICE = "voice"
    APP = "app"
    SMS = "sms"


class AnswerStatus(StrEnum):
    ANSWERED = "answered"
    FOLLOW_UP = "follow_up"
    FALLBACK = "fallback"
    ERROR = "error"


class Role(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class RouterSource(StrEnum):
    BANGLABERT = "banglabert"
    TFIDF = "tfidf"
    LLM = "llm"
    CONTEXT = "context"
    SITUATION = "situation"  # decided by the `understand` step (FR-AGT-19)


# Bangladeshi mobile in E.164: +880 1 [3-9] + 8 more digits (SRS 6.1).
_E164_BD_MOBILE = re.compile(r"^\+8801[3-9]\d{8}$")


@dataclass(frozen=True)
class PhoneNumber:
    """A valid Bangladeshi mobile number, always stored as E.164 (+8801XXXXXXXXX)."""

    e164: str

    def __post_init__(self) -> None:
        if not _E164_BD_MOBILE.match(self.e164):
            raise InvalidPhone(f"not a Bangladeshi mobile number: {self.e164!r}")

    @classmethod
    def parse(cls, raw: str) -> "PhoneNumber":
        """Accepts 01XXXXXXXXX, 8801XXXXXXXXX or +8801XXXXXXXXX (spaces and dashes allowed)."""
        cleaned = re.sub(r"[\s\-()]", "", raw or "")
        if cleaned.startswith("+"):
            candidate = cleaned
        elif cleaned.startswith("880"):
            candidate = "+" + cleaned
        elif cleaned.startswith("0"):
            candidate = "+88" + cleaned
        else:
            raise InvalidPhone(f"unrecognised phone format: {raw!r}")
        return cls(candidate)

    def __str__(self) -> str:
        return self.e164
