"""SynthesizeSpeech use case and the gTTS adapter's error handling (FR-APP-04). No network."""

import threading

import pytest

from app.application.use_cases.speech import SynthesizeSpeech
from app.infrastructure.tts import gtts_tts
from app.infrastructure.tts.gtts_tts import GttsTts, TtsFailed
from tests.fakes import FakeTts


class CountingTts(FakeTts):
    def __init__(self) -> None:
        self.texts: list[str] = []

    def synthesize(self, text: str) -> bytes:
        self.texts.append(text)
        return super().synthesize(text)


def test_returns_the_audio() -> None:
    assert SynthesizeSpeech(FakeTts()).execute("নমস্কার") == b"ID3fake-mp3:" + "নমস্কার".encode()


def test_same_text_is_synthesized_once() -> None:
    tts = CountingTts()
    speak = SynthesizeSpeech(tts)
    speak.execute("বয়স্ক ভাতা")
    speak.execute("  বয়স্ক   ভাতা ")  # same words, other spacing
    assert tts.texts == ["বয়স্ক ভাতা"]


def test_cache_keeps_only_the_newest() -> None:
    tts = CountingTts()
    speak = SynthesizeSpeech(tts, cache_size=2)
    for text in ("এক", "দুই", "তিন", "এক"):
        speak.execute(text)
    assert tts.texts == ["এক", "দুই", "তিন", "এক"]  # "এক" was dropped, so it is made again


def test_failure_is_not_cached() -> None:
    class FlakyTts(CountingTts):
        def synthesize(self, text: str) -> bytes:
            if not self.texts:
                self.texts.append(text)
                raise TtsFailed("down")
            return super().synthesize(text)

    speak = SynthesizeSpeech(FlakyTts())
    with pytest.raises(TtsFailed):
        speak.execute("হ্যালো")
    assert speak.execute("হ্যালো").startswith(b"ID3")


# ---------------------------------------------------------------- GttsTts without the network


class FakeGtts:
    behaviour = "ok"
    release = threading.Event()

    def __init__(self, text: str, lang: str) -> None:
        self.text, self.lang = text, lang

    def write_to_fp(self, fp) -> None:  # type: ignore[no-untyped-def]
        if FakeGtts.behaviour == "fail":
            raise RuntimeError("blocked")
        if FakeGtts.behaviour == "hang":
            FakeGtts.release.wait(2)
        fp.write(b"ID3" + self.lang.encode())


@pytest.fixture
def fake_gtts(monkeypatch: pytest.MonkeyPatch) -> type[FakeGtts]:
    monkeypatch.setattr(gtts_tts, "gTTS", FakeGtts)
    FakeGtts.behaviour = "ok"
    FakeGtts.release.clear()
    return FakeGtts


def test_gtts_returns_bangla_mp3(fake_gtts: type[FakeGtts]) -> None:
    assert GttsTts().synthesize("হ্যালো") == b"ID3bn"


def test_gtts_error_becomes_tts_failed(fake_gtts: type[FakeGtts]) -> None:
    fake_gtts.behaviour = "fail"
    with pytest.raises(TtsFailed):
        GttsTts().synthesize("হ্যালো")


def test_gtts_timeout_becomes_tts_failed(fake_gtts: type[FakeGtts]) -> None:
    fake_gtts.behaviour = "hang"
    tts = GttsTts(timeout_s=0.1)
    with pytest.raises(TtsFailed):
        tts.synthesize("হ্যালো")
    fake_gtts.release.set()
    tts.close()
