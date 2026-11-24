"""ThreadPoolRunner: background work that never blocks or crashes the caller (D1-A4, FR-SMS-04)."""

import logging
import threading
import time

import pytest

from app.application.ports.background import BackgroundRunner
from app.infrastructure.background.thread_runner import ThreadPoolRunner


@pytest.fixture
def runner():
    r = ThreadPoolRunner(max_workers=2)
    yield r
    r.close(wait=True)


def test_implements_the_port(runner: ThreadPoolRunner) -> None:
    assert isinstance(runner, BackgroundRunner)


def test_submit_returns_before_the_work_finishes(runner: ThreadPoolRunner) -> None:
    release = threading.Event()
    done = threading.Event()

    def slow() -> None:
        release.wait(2)
        done.set()

    started = time.perf_counter()
    runner.submit(slow)
    assert time.perf_counter() - started < 0.2  # did not wait for the work
    assert not done.is_set()
    release.set()
    assert done.wait(2)


def test_arguments_are_passed(runner: ThreadPoolRunner) -> None:
    got: list[tuple[int, str]] = []
    done = threading.Event()

    def work(a: int, b: str) -> None:
        got.append((a, b))
        done.set()

    runner.submit(work, 7, "সাত")
    assert done.wait(2)
    assert got == [(7, "সাত")]


def test_delayed_work_waits_and_does_not_block_other_work(runner: ThreadPoolRunner) -> None:
    order: list[str] = []
    later_done = threading.Event()
    now_done = threading.Event()

    def later() -> None:
        order.append("later")
        later_done.set()

    def now() -> None:
        order.append("now")
        now_done.set()

    started = time.perf_counter()
    runner.submit(later, delay_s=0.3)
    runner.submit(now)
    assert now_done.wait(2)
    assert later_done.wait(2)
    assert time.perf_counter() - started >= 0.3
    assert order == ["now", "later"]


def test_an_exception_is_logged_not_raised(
    runner: ThreadPoolRunner, caplog: pytest.LogCaptureFixture
) -> None:
    done = threading.Event()

    def broken() -> None:
        try:
            raise ValueError("boom")
        finally:
            done.set()

    with caplog.at_level(logging.ERROR):
        runner.submit(broken)  # no exception here
        assert done.wait(2)
        runner.close(wait=True)  # make sure the log line is written
    assert any("broken" in r.getMessage() and "failed" in r.getMessage() for r in caplog.records)


def test_close_cancels_work_still_waiting_for_its_delay() -> None:
    r = ThreadPoolRunner()
    ran = threading.Event()
    r.submit(ran.set, delay_s=0.3)
    r.close(wait=True)
    time.sleep(0.5)
    assert not ran.is_set()


def test_submit_after_close_is_ignored() -> None:
    r = ThreadPoolRunner()
    r.close()
    r.submit(lambda: None)  # no exception
