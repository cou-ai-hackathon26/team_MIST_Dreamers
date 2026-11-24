"""Answer-cache key (FR-AGT-15): normalised question text + service + channel.

Normalising means: trimmed, lower case, punctuation removed, Bangla digits turned into 0-9,
spaces collapsed. So "বয়স্ক ভাতা কত টাকা?" and "বয়স্ক ভাতা কত টাকা" share one cache entry.
"""

import re
import unicodedata

from app.domain.value_objects import Channel

_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_PUNCTUATION = re.compile(r"[।॥?!.,;:'\"()\[\]{}\-_/\\|*+=<>@#%&^~`]+")
_SPACES = re.compile(r"\s+")


def normalize_question(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "").lower().translate(_BANGLA_DIGITS)
    return _SPACES.sub(" ", _PUNCTUATION.sub(" ", text)).strip()


def cache_key(question: str, service_id: str, channel: Channel) -> str:
    return f"{normalize_question(question)}|{service_id}|{channel.value}"
