"""Admin login with short-lived session tokens (FR-ADM-05, hardened).

The admin password is ADMIN_TOKEN from .env. It never reaches the browser app:
the officer types it once, and the app gets back a signed session token that expires.

    token = "<expiry unix seconds>.<HMAC-SHA256 hex>"

- Stateless: nothing is stored. The signing key is derived from ADMIN_TOKEN, so changing
  ADMIN_TOKEN logs every session out at once.
- Wrong passwords are limited per client (default 5 per minute), against guessing.
- No ADMIN_TOKEN: the admin area is closed for everybody (never open by accident).
Only the Python standard library is used.
"""

import hashlib
import hmac
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock

SECONDS_PER_HOUR = 3600


class AdminLoginError(Exception):
    """Base class; the interfaces layer turns these into HTTP answers."""


class WrongPassword(AdminLoginError):
    pass


class TooManyAttempts(AdminLoginError):
    def __init__(self, retry_after_s: int) -> None:
        super().__init__(f"too many wrong passwords, retry after {retry_after_s} s")
        self.retry_after_s = retry_after_s


class AdminDisabled(AdminLoginError):
    """ADMIN_TOKEN is not set, so nobody can sign in."""


@dataclass(frozen=True)
class AdminSession:
    token: str
    expires_at: int  # unix seconds


class AdminAuth:
    def __init__(
        self,
        admin_password: str,
        session_hours: float = 8,
        max_failures: int = 5,
        failure_window_s: int = 60,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._password = admin_password
        self._ttl_s = int(session_hours * SECONDS_PER_HOUR)
        self._max_failures = max_failures
        self._window_s = failure_window_s
        self._clock = clock
        # Separate key for signing, so a leaked session token says nothing about the password.
        self._key = hashlib.sha256(f"ekcall-admin-session:{admin_password}".encode()).digest()
        self._failures: dict[str, deque[float]] = {}
        self._lock = Lock()

    # ---------------------------------------------------------------- state

    @property
    def configured(self) -> bool:
        """False when ADMIN_TOKEN is empty: then the admin area is closed."""
        return bool(self._password)

    # ---------------------------------------------------------------- login

    def login(self, password: str, client: str) -> AdminSession:
        """Raises WrongPassword, TooManyAttempts or AdminDisabled."""
        if not self._password:
            raise AdminDisabled("ADMIN_TOKEN is not set")
        self._check_not_blocked(client)
        if not hmac.compare_digest(password.encode(), self._password.encode()):
            self._record_failure(client)
            raise WrongPassword("wrong admin password")
        self._clear_failures(client)
        return self._issue()

    def _issue(self) -> AdminSession:
        expires_at = int(self._clock()) + self._ttl_s
        return AdminSession(f"{expires_at}.{self._sign(expires_at)}", expires_at)

    def _sign(self, expires_at: int) -> str:
        return hmac.new(self._key, str(expires_at).encode(), hashlib.sha256).hexdigest()

    # ---------------------------------------------------------------- checks

    def session_valid(self, token: str | None) -> bool:
        """True for an unexpired token signed with the current password."""
        if not token or "." not in token:
            return False
        expiry_text, _, signature = token.partition(".")
        if not expiry_text.isdigit():
            return False
        expires_at = int(expiry_text)
        if expires_at <= self._clock():
            return False
        return hmac.compare_digest(signature, self._sign(expires_at))

    def password_valid(self, password: str | None) -> bool:
        """The old X-Admin-Token header (Swagger and scripts): the password itself."""
        if not self._password:
            return False
        return hmac.compare_digest((password or "").encode(), self._password.encode())

    def allowed(self, bearer: str | None, header_password: str | None) -> bool:
        """The rule every admin endpoint uses. No password configured: nobody is allowed."""
        if not self._password:
            return False
        return self.session_valid(bearer) or self.password_valid(header_password)

    # ---------------------------------------------------------------- wrong-password limit

    def _recent(self, client: str) -> deque[float]:
        window_start = self._clock() - self._window_s
        attempts = self._failures.setdefault(client, deque())
        while attempts and attempts[0] <= window_start:
            attempts.popleft()
        return attempts

    def _check_not_blocked(self, client: str) -> None:
        with self._lock:
            attempts = self._recent(client)
            if len(attempts) >= self._max_failures:
                retry_after = int(attempts[0] + self._window_s - self._clock()) + 1
                raise TooManyAttempts(max(retry_after, 1))

    def _record_failure(self, client: str) -> None:
        with self._lock:
            self._recent(client).append(self._clock())

    def _clear_failures(self, client: str) -> None:
        with self._lock:
            self._failures.pop(client, None)
