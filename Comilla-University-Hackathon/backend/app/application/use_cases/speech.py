"""Use cases for speech: one spoken turn of a phone call, and answer audio for the app.

HandleVoiceTurn (SRS 3.1; FR-CALL-02, 05, 06, 09, 11; FR-SMS-01) decides what the caller hears next.
Framework-free: the voice router turns a VoiceReply into TwiML.

Rules, in order:
1. A goodbye phrase ends the call, unless a follow-up question is pending (then a short
   "হ্যাঁ" / "না" is the answer to it and goes to the agent).
2. Otherwise the text goes to AskQuestion with channel=voice. A two-service answer is spoken as
   built by the agent (at most MAX_SPEECH_WORDS_MULTI words) and says TWO_SMS instead of SMS_SENT.
3. The last allowed turn (MAX_TURNS_PER_CALL) gets its answer, then GOODBYE.
4. Any failure speaks ERROR and keeps the call alive.

SynthesizeSpeech (FR-APP-04) turns an answer into MP3 for the app's play button.
"""

import logging
import threading
import time
import unicodedata
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass

from app.application.dto import AskResult
from app.application.ports.messaging import TextToSpeech
from app.application.ports.repositories import CallRepo, ConversationRepo
from app.domain import messages_bn
from app.domain.entities import Answer
from app.domain.errors import InvalidPhone
from app.domain.policies import MAX_TURNS_PER_CALL
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, Role

log = logging.getLogger(__name__)

# Caller input that means "I am done". An utterance is a goodbye when it is short, every word is
# in GOODBYE_WORDS, and at least one word is a clear closing word (so "ঠিক আছে" alone is not one).
GOODBYE_WORDS = frozenset(
    "না নেই নাই আর কিছু লাগবে জানতে জানার চাই জি জ্বি ঠিক আছে আচ্ছা ধন্যবাদ শুকরিয়া "
    "বাই আল্লাহ খোদা হাফেজ রাখি রাখছি থ্যাংক থ্যাঙ্ক ইউ".split()
)
CLOSING_WORDS = frozenset("না নেই নাই ধন্যবাদ শুকরিয়া বাই হাফেজ রাখি রাখছি থ্যাংক থ্যাঙ্ক".split())
MAX_GOODBYE_WORDS = 6
FOLLOW_UP_LOOKBACK = 4  # messages read to find the last assistant turn

AskFn = Callable[[str, str, Channel, str | None], AskResult]


@dataclass(frozen=True)
class VoiceReply:
    """What the caller hears next. hang_up=False means: say these, then listen again."""

    say: tuple[str, ...]
    hang_up: bool = False
    status: str = "answered"  # for logs: answered | follow_up | fallback | error | goodbye


def is_goodbye(text: str) -> bool:
    words = _strip_punctuation(text).split()
    if not words or len(words) > MAX_GOODBYE_WORDS:
        return False
    return all(w in GOODBYE_WORDS for w in words) and any(w in CLOSING_WORDS for w in words)


class HandleVoiceTurn:
    def __init__(
        self,
        ask: AskFn,
        calls: CallRepo,
        conversations: ConversationRepo,
        max_turns: int = MAX_TURNS_PER_CALL,
    ) -> None:
        self._ask = ask
        self._calls = calls
        self._conversations = conversations
        self._max_turns = max_turns

    def execute(self, call_sid: str, phone: str, text: str, direction: str = "inbound") -> VoiceReply:
        started = time.perf_counter()
        try:
            reply = self._turn(call_sid, phone, " ".join(text.split()), direction)
        except Exception:  # FR-CALL-09: never drop the call on an internal error
            log.exception("voice turn failed call_sid=%s", call_sid)
            reply = VoiceReply(say=(messages_bn.ERROR,), status="error")
        log.info(
            "voice turn call_sid=%s status=%s total_ms=%d hang_up=%s",
            call_sid, reply.status, int((time.perf_counter() - started) * 1000), reply.hang_up,
        )  # fmt: skip
        return reply

    # ------------------------------------------------------------ steps

    def _turn(self, call_sid: str, phone: str, text: str, direction: str) -> VoiceReply:
        try:
            number = PhoneNumber.parse(phone)
        except InvalidPhone:
            log.warning("voice turn with a non-Bangladeshi caller number, call_sid=%s", call_sid)
            return VoiceReply(say=(messages_bn.ERROR,), status="error")

        self._calls.record_start(call_sid, number, direction)  # idempotent: safe after a restart
        if not self._follow_up_pending(number) and is_goodbye(text):
            return VoiceReply(say=(messages_bn.GOODBYE,), hang_up=True, status="goodbye")

        turn = self._calls.record_turn(call_sid)
        result = self._ask(phone, text, Channel.VOICE, call_sid)
        reply = self._speak(result.answer, sms_count=result.sms_count)
        log.info("voice answer call_sid=%s turn=%d agent_ms=%d", call_sid, turn, result.latency_ms)

        if turn >= self._max_turns and not reply.hang_up:  # FR-CALL-06: answer, then end politely
            say = (*_without_continue(reply.say), messages_bn.GOODBYE)
            return VoiceReply(say=say, hang_up=True, status=reply.status)
        return reply

    def _follow_up_pending(self, number: PhoneNumber) -> bool:
        """SRS 3.1 exception: the previous assistant turn asked a follow-up question."""
        for message in reversed(self._conversations.recent_messages(number, FOLLOW_UP_LOOKBACK)):
            if message.role is Role.ASSISTANT:
                return message.status is AnswerStatus.FOLLOW_UP
        return False

    @staticmethod
    def _speak(answer: Answer, sms_count: int) -> VoiceReply:
        if answer.status is AnswerStatus.FOLLOW_UP:
            return VoiceReply(say=(answer.speech_text,), status="follow_up")  # the question itself
        if answer.status is AnswerStatus.ERROR:
            return VoiceReply(say=(messages_bn.ERROR,), status="error")
        say = [answer.speech_text]
        if sms_count >= 2:  # a two-service answer queued one SMS per service (sprint V1)
            say.append(messages_bn.TWO_SMS)
        elif sms_count == 1:
            say.append(messages_bn.SMS_SENT)
        say.append(messages_bn.CONTINUE)
        return VoiceReply(say=tuple(say), status=str(answer.status))


def _strip_punctuation(text: str) -> str:
    """Replaces punctuation (।,.!? ...) with spaces; keeps Bangla vowel signs, which are not \\w."""
    return "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in text)


def _without_continue(texts: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(t for t in texts if t != messages_bn.CONTINUE)


# ---------------------------------------------------------------- answer audio for the app (FR-APP-04)

TTS_CACHE_SIZE = 64  # the same answers are played again and again (and cached answers repeat)


class SynthesizeSpeech:
    """Bangla MP3 for an answer's speech_text (POST /api/v1/tts).

    Keeps the last TTS_CACHE_SIZE results in memory, so playing an answer again is instant and
    does not call the speech service twice. Errors from the adapter (TtsFailed) pass through.
    """

    def __init__(self, tts: TextToSpeech, cache_size: int = TTS_CACHE_SIZE) -> None:
        self._tts = tts
        self._cache_size = cache_size
        self._cache: OrderedDict[str, bytes] = OrderedDict()
        self._lock = threading.Lock()

    def execute(self, text: str) -> bytes:
        key = " ".join(text.split())
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        started = time.perf_counter()
        audio = self._tts.synthesize(key)
        elapsed_ms = (time.perf_counter() - started) * 1000
        log.info("tts chars=%d bytes=%d ms=%.0f", len(key), len(audio), elapsed_ms)
        with self._lock:
            self._cache[key] = audio
            while len(self._cache) > self._cache_size:
                self._cache.popitem(last=False)
        return audio
