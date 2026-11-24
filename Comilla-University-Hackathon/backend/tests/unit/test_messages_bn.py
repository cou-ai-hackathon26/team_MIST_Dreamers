import re
from pathlib import Path

import pytest

from app.domain import messages_bn
from app.domain.messages_bn import ALL_MESSAGES

SRS_PATH = Path(__file__).resolve().parents[3] / "docs" / "SRS.md"
BANGLA = re.compile(r"[ঀ-৿]")


def srs_appendix_a() -> dict[str, str]:
    """Reads the `| `KEY` | text |` rows of SRS Appendix A."""
    text = SRS_PATH.read_text(encoding="utf-8")
    section = text.split("## Appendix A", 1)[1].split("## Appendix B", 1)[0]
    return dict(re.findall(r"^\| `([A-Z_]+)` \| (.+?) \|$", section, flags=re.MULTILINE))


def test_every_message_matches_the_srs_exactly() -> None:
    assert srs_appendix_a() == ALL_MESSAGES


def test_all_messages_dict_lists_every_constant() -> None:
    constants = {name for name in dir(messages_bn) if name.isupper() and name != "ALL_MESSAGES"}
    assert constants == set(ALL_MESSAGES)


@pytest.mark.parametrize("key", list(ALL_MESSAGES))
def test_message_is_bangla_and_not_empty(key: str) -> None:
    assert BANGLA.search(ALL_MESSAGES[key]), f"{key} has no Bangla text"


def test_safety_messages_point_to_333() -> None:
    assert "৩৩৩" in messages_bn.FALLBACK  # FR-AGT-13
    assert "৩৩৩" in messages_bn.ERROR


def test_greeting_discloses_ai() -> None:
    assert "এআই" in messages_bn.GREETING  # NFR-PRIV-02
