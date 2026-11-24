"""TextToSpeech adapter: Bangla MP3 from Google Translate's speech service via gTTS (FR-APP-04).

Free and needs no key, but it is a network call: it can be slow or blocked. gTTS has no timeout
of its own, so the request runs in a worker thread and we stop waiting after `timeout_s`.
Every failure becomes TtsFailed; the app then reads the answer with the browser's own voice.
"""

import io
import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout

from gtts import gTTS

from app.domain.errors import DomainError

log = logging.getLogger(__name__)

LANGUAGE = "bn"


class TtsFailed(DomainError):
    """The speech service did not return audio (network error, timeout, blocked)."""

    code = "TTS_FAILED"


class GttsTts:
    def __init__(self, language: str = LANGUAGE, timeout_s: float = 10.0, max_workers: int = 2) -> None:
        self._language = language
        self._timeout_s = timeout_s
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="gtts")

    def synthesize(self, text: str) -> bytes:
        future = self._pool.submit(self._mp3, text)
        try:
            return future.result(timeout=self._timeout_s)
        except FutureTimeout as e:
            log.warning("gTTS gave no audio within %.0f s (%d chars)", self._timeout_s, len(text))
            raise TtsFailed("speech service timed out") from e
        except Exception as e:  # gTTSError, requests errors, "no text to speak" ...
            log.warning("gTTS failed: %s", type(e).__name__)
            raise TtsFailed("speech service failed") from e

    def _mp3(self, text: str) -> bytes:
        buffer = io.BytesIO()
        gTTS(text, lang=self._language).write_to_fp(buffer)
        return buffer.getvalue()

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
