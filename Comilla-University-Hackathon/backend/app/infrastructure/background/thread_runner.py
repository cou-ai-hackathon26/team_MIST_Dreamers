"""BackgroundRunner adapter: a small thread pool (FR-SMS-04, used by SMS, call-back and async voice).

submit() returns at once, so the caller (a spoken answer, an HTTP response) is never delayed.
Work with delay_s > 0 waits on a timer thread first, so a waiting job never blocks a worker.
Exceptions in submitted work are logged and swallowed: background work can never crash a request.
"""

import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

log = logging.getLogger(__name__)


class ThreadPoolRunner:
    def __init__(self, max_workers: int = 4) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="background")
        self._timers: set[threading.Timer] = set()
        self._lock = threading.Lock()
        self._closed = False

    def submit(self, fn: Callable[..., Any], *args: Any, delay_s: float = 0) -> None:
        if self._closed:
            log.warning("background runner is closed; dropped %s", _name(fn))
            return
        if delay_s <= 0:
            self._pool.submit(self._run, fn, args)
            return
        timer = threading.Timer(delay_s, self._start_after_delay, args=(fn, args))
        timer.daemon = True
        timer.name = f"delay-{_name(fn)}"
        with self._lock:
            self._timers.add(timer)
        timer.start()

    def _start_after_delay(self, fn: Callable[..., Any], args: tuple[Any, ...]) -> None:
        with self._lock:
            self._timers.discard(threading.current_thread())  # type: ignore[arg-type]
        if self._closed:
            return
        try:
            self._pool.submit(self._run, fn, args)
        except RuntimeError:  # pool shut down in the meantime
            log.warning("background runner closed before %s could start", _name(fn))

    @staticmethod
    def _run(fn: Callable[..., Any], args: tuple[Any, ...]) -> None:
        try:
            fn(*args)
        except Exception:
            log.exception("background job %s failed", _name(fn))

    def close(self, wait: bool = True) -> None:
        """Cancels jobs still waiting for their delay; with wait=True, finishes the running ones."""
        self._closed = True
        with self._lock:
            timers, self._timers = self._timers, set()
        for timer in timers:
            timer.cancel()
        self._pool.shutdown(wait=wait)


def _name(fn: Callable[..., Any]) -> str:
    return getattr(fn, "__qualname__", None) or getattr(fn, "__name__", None) or repr(fn)
