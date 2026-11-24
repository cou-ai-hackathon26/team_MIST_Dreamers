"""Light text clean-up shared by the TF-IDF router at training and at run time (FR-DATA-06).

It lives in its own module because the saved joblib pipeline refers to `normalize_text` by name.
"""

import re
import unicodedata

_BANGLA_DIGITS = str.maketrans("০১২৩৪৫৬৭৮৯", "0123456789")
_PUNCTUATION = re.compile(r"[।॥?!.,;:'\"()\[\]{}\-_/\\|*+=<>@#%&^~`]+")
_SPACES = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """NFC, lower case, English digits, no punctuation, single spaces."""
    text = unicodedata.normalize("NFC", text or "").lower().translate(_BANGLA_DIGITS)
    text = _PUNCTUATION.sub(" ", text)
    return _SPACES.sub(" ", text).strip()
