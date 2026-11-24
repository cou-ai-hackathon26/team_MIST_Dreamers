import pytest

from app.domain.errors import InvalidPhone
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, RouterSource


@pytest.mark.parametrize(
    "raw",
    [
        "01712345678",
        "8801712345678",
        "+8801712345678",
        "017 1234 5678",
        "+880-1712-345678",
        "  01712345678  ",
    ],
)
def test_all_accepted_formats_normalise_to_e164(raw: str) -> None:
    assert PhoneNumber.parse(raw).e164 == "+8801712345678"


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "abc",
        "1712345678",  # missing the leading 0
        "0171234567",  # one digit short
        "017123456789",  # one digit too long
        "01212345678",  # 012 is not a mobile prefix
        "+14155552671",  # not Bangladesh
        "0171234567a",
    ],
)
def test_bad_numbers_are_rejected(raw: str) -> None:
    with pytest.raises(InvalidPhone):
        PhoneNumber.parse(raw)


def test_constructor_rejects_non_e164_value() -> None:
    with pytest.raises(InvalidPhone):
        PhoneNumber("01712345678")


def test_phone_number_is_immutable_and_comparable() -> None:
    a = PhoneNumber.parse("01712345678")
    b = PhoneNumber.parse("+8801712345678")
    assert a == b
    with pytest.raises(AttributeError):
        a.e164 = "+8801999999999"  # type: ignore[misc]


def test_enum_values_match_the_srs() -> None:
    assert [c.value for c in Channel] == ["voice", "app", "sms"]
    assert [s.value for s in AnswerStatus] == ["answered", "follow_up", "fallback", "error"]
    assert [r.value for r in RouterSource] == ["banglabert", "tfidf", "llm", "context", "situation"]
