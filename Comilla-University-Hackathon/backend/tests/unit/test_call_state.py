"""Silence counter per call (FR-CALL-04)."""

from app.interfaces.voice.call_state import SilenceCounter


def test_counts_silences_in_a_row_per_call() -> None:
    counter = SilenceCounter()
    assert counter.silent("CA1") == 1
    assert counter.silent("CA2") == 1
    assert counter.silent("CA1") == 2


def test_speech_resets_the_count() -> None:
    counter = SilenceCounter()
    counter.silent("CA1")
    counter.heard("CA1")
    assert counter.silent("CA1") == 1


def test_forget_drops_the_call() -> None:
    counter = SilenceCounter()
    counter.silent("CA1")
    counter.forget("CA1")
    counter.forget("unknown")  # no error
    assert counter.silent("CA1") == 1
