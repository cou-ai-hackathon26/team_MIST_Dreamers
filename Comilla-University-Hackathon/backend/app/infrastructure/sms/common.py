"""Helpers shared by the SMS adapters."""

from app.domain.value_objects import PhoneNumber


def masked(phone: PhoneNumber) -> str:
    """+8801712345678 -> +880171*****78, so logs never hold a full phone number (NFR-PRIV-01)."""
    e164 = phone.e164
    return e164[:7] + "*" * (len(e164) - 9) + e164[-2:]
