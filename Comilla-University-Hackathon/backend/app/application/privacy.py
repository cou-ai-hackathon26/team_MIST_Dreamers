"""Privacy helpers (NFR-PRIV-01)."""

import hashlib

from app.domain.value_objects import PhoneNumber


def hash_phone(phone: PhoneNumber, salt: str) -> str:
    """Salted SHA-256 of the E.164 number. Same phone + salt -> same hash; the number cannot be read back."""
    return hashlib.sha256(f"{salt}:{phone.e164}".encode()).hexdigest()
