"""AdminAuth: login, session tokens, the wrong-password limit (FR-ADM-05, hardened)."""

import pytest

from app.application.use_cases.admin_auth import AdminAuth, AdminDisabled, TooManyAttempts, WrongPassword

PASSWORD = "correct horse battery staple"


class Clock:
    def __init__(self, now: float = 1_800_000_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def auth(password: str = PASSWORD, clock: Clock | None = None, **kwargs) -> AdminAuth:
    return AdminAuth(password, clock=clock or Clock(), **kwargs)


# ---------------------------------------------------------------- login and tokens


def test_right_password_gives_a_session_that_is_valid() -> None:
    a = auth()
    session = a.login(PASSWORD, "1.2.3.4")
    assert a.session_valid(session.token)
    assert a.allowed(session.token, None)


def test_wrong_password_is_refused() -> None:
    with pytest.raises(WrongPassword):
        auth().login("guess", "1.2.3.4")


def test_session_lasts_the_configured_hours_then_expires() -> None:
    clock = Clock()
    a = auth(clock=clock, session_hours=8)
    session = a.login(PASSWORD, "c")
    assert session.expires_at == int(clock.now) + 8 * 3600
    clock.now += 8 * 3600 - 1
    assert a.session_valid(session.token)
    clock.now += 2
    assert not a.session_valid(session.token)


@pytest.mark.parametrize("token", [None, "", "abc", "123", "x.y", "123.", ".abc", "9999999999.deadbeef"])
def test_malformed_or_forged_tokens_are_refused(token: str | None) -> None:
    assert not auth().session_valid(token)


def test_a_changed_expiry_breaks_the_signature() -> None:
    a = auth()
    expiry, _, signature = a.login(PASSWORD, "c").token.partition(".")
    assert not a.session_valid(f"{int(expiry) + 3600}.{signature}")  # extended by hand


def test_changing_the_password_logs_everyone_out() -> None:
    clock = Clock()
    token = auth(clock=clock).login(PASSWORD, "c").token
    assert not auth("a new password", clock=clock).session_valid(token)


def test_the_token_does_not_contain_the_password() -> None:
    assert PASSWORD not in auth().login(PASSWORD, "c").token


# ---------------------------------------------------------------- X-Admin-Token (Swagger, scripts)


def test_the_password_header_still_works() -> None:
    a = auth()
    assert a.allowed(None, PASSWORD)
    assert not a.allowed(None, "wrong")
    assert not a.allowed(None, None)


# ---------------------------------------------------------------- no ADMIN_TOKEN


def test_without_a_password_nobody_gets_in() -> None:
    a = auth("")
    assert not a.configured
    assert not a.allowed(None, None)
    assert not a.allowed(None, "")
    assert not a.allowed("anything", "anything")
    for password in ["", "anything", PASSWORD]:
        with pytest.raises(AdminDisabled):
            a.login(password, "c")


# ---------------------------------------------------------------- wrong-password limit


def test_five_wrong_passwords_block_the_client_for_a_minute() -> None:
    clock = Clock()
    a = auth(clock=clock)
    for _ in range(5):
        with pytest.raises(WrongPassword):
            a.login("guess", "attacker")
    with pytest.raises(TooManyAttempts) as blocked:
        a.login(PASSWORD, "attacker")  # even the right password waits
    assert 1 <= blocked.value.retry_after_s <= 61
    clock.now += 61
    assert a.session_valid(a.login(PASSWORD, "attacker").token)


def test_the_limit_is_per_client() -> None:
    a = auth()
    for _ in range(5):
        with pytest.raises(WrongPassword):
            a.login("guess", "attacker")
    assert a.session_valid(a.login(PASSWORD, "officer").token)


def test_a_successful_login_resets_the_count() -> None:
    a = auth()
    for _ in range(4):
        with pytest.raises(WrongPassword):
            a.login("guess", "c")
    a.login(PASSWORD, "c")
    for _ in range(4):
        with pytest.raises(WrongPassword):
            a.login("guess", "c")
    a.login(PASSWORD, "c")  # not blocked: the count started again
