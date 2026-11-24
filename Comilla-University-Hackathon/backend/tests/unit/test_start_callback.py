"""Call-back and missed call use cases (FR-CALL-07, 08)."""

from datetime import UTC, datetime, timedelta

import pytest

from app.application.use_cases.start_callback import HandleMissedCall, StartCallback
from app.domain.errors import InvalidPhone, RateLimited
from app.domain.value_objects import PhoneNumber
from tests.fakes import FakeCallPlacer, FakeRunner, InMemoryCallRepo

PHONE = "01712345678"
E164 = "+8801712345678"


class Clock:
    def __init__(self) -> None:
        self.moment = datetime.now(UTC)  # the in-memory repo stores real times

    def __call__(self) -> datetime:
        return self.moment


class Setup:
    def __init__(self) -> None:
        self.placer = FakeCallPlacer()
        self.calls = InMemoryCallRepo()
        self.clock = Clock()
        self.callback = StartCallback(self.placer, self.calls, cooldown_s=60, now=self.clock)


@pytest.fixture
def setup() -> Setup:
    return Setup()


def stored_at(setup: Setup, call_sid: str, moment: datetime) -> None:
    setup.calls.calls[call_sid]["started_at"] = moment


def test_places_the_call_and_stores_it_as_outbound(setup: Setup) -> None:
    call_sid = setup.callback.execute(PHONE)
    assert call_sid == "CA_fake_1"
    assert setup.placer.calls == [PhoneNumber(E164)]
    assert setup.calls.calls[call_sid]["direction"] == "outbound-api"


def test_second_call_within_a_minute_is_rate_limited(setup: Setup) -> None:
    first = setup.callback.execute(PHONE)
    stored_at(setup, first, setup.clock.moment)
    setup.clock.moment += timedelta(seconds=30)
    with pytest.raises(RateLimited):
        setup.callback.execute("+8801712345678")  # same number, other format
    assert len(setup.placer.calls) == 1


def test_allowed_again_after_the_cooldown(setup: Setup) -> None:
    first = setup.callback.execute(PHONE)
    stored_at(setup, first, setup.clock.moment)
    setup.clock.moment += timedelta(seconds=61)
    assert setup.callback.execute(PHONE) == "CA_fake_2"


def test_other_numbers_are_not_limited(setup: Setup) -> None:
    setup.callback.execute(PHONE)
    assert setup.callback.execute("01812345678") == "CA_fake_2"


def test_invalid_number_is_refused(setup: Setup) -> None:
    with pytest.raises(InvalidPhone):
        setup.callback.execute("+15005550006")
    assert setup.placer.calls == []


def test_twilio_failure_stores_nothing(setup: Setup) -> None:
    def refuse(_phone: PhoneNumber) -> str:
        raise RuntimeError("refused")

    setup.placer.call = refuse  # type: ignore[method-assign]
    with pytest.raises(RuntimeError):
        setup.callback.execute(PHONE)
    assert setup.calls.calls == {}


def test_run_quietly_never_raises(setup: Setup) -> None:
    setup.callback.run_quietly(PHONE)
    setup.callback.run_quietly(PHONE)  # rate limited: logged only
    setup.callback.run_quietly("not a number")
    assert len(setup.placer.calls) == 1


def test_missed_call_schedules_a_call_back_after_a_delay(setup: Setup) -> None:
    runner = FakeRunner()
    missed = HandleMissedCall(setup.callback, runner, delay_s=3)
    assert missed.execute(E164) is True
    assert runner.submitted == [("run_quietly", 3)]
    assert setup.placer.calls == [PhoneNumber(E164)]


def test_missed_call_from_a_foreign_number_is_not_called_back(setup: Setup) -> None:
    runner = FakeRunner()
    assert HandleMissedCall(setup.callback, runner).execute("+15005550006") is False
    assert runner.submitted == []
