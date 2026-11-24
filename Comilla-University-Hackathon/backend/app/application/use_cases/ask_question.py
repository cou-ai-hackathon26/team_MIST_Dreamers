"""Use case: answer one question from any channel (FR-APP-02, FR-CALL-02, FR-SMS-01 to 05, NFR-PRIV-01).

history -> engine -> save messages, checklist and an anonymous log -> (voice only) one SMS checklist.

SMS rules (D1-A4):
- only for a voice call (it has a call SID), only for an `answered` result with a checklist;
- a two-service answer gets one checklist row and one SMS per service (sprint W1, FR-AGT-21);
- at most one SMS per service per call (FR-SMS-02): the checklist is saved with sms_sent=True
  BEFORE the send is queued, so a slow or failed send can never lead to a second SMS;
- the send runs on the BackgroundRunner and never delays the spoken answer (FR-SMS-04);
- a failed send is only logged (FR-SMS-05). Logs never contain the phone number.
The answer cache lives inside the agent (D2-T4), not here.
"""

import logging
import time
from collections.abc import Sequence

from app.application.dto import AskResult
from app.application.formatting import format_sms
from app.application.ports.background import BackgroundRunner
from app.application.ports.engine import AnswerEngine
from app.application.ports.messaging import SmsSender
from app.application.ports.repositories import ChecklistRepo, ConversationRepo, QuestionLogRepo
from app.application.privacy import hash_phone
from app.domain.entities import Answer, Checklist, Message, QuestionLog, Service
from app.domain.errors import DomainError
from app.domain.policies import HISTORY_MESSAGES_TO_LOAD
from app.domain.service_set import ServiceSet
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, Role

log = logging.getLogger(__name__)


class AskQuestion:
    def __init__(
        self,
        engine: AnswerEngine,
        conversations: ConversationRepo,
        checklists: ChecklistRepo,
        question_logs: QuestionLogRepo,
        services: Sequence[Service],
        phone_hash_salt: str,
        sms: SmsSender | None = None,
        runner: BackgroundRunner | None = None,
    ) -> None:
        """Without `sms` and `runner` no SMS is sent (the container always passes both)."""
        self._engine = engine
        self._conversations = conversations
        self._checklists = checklists
        self._logs = question_logs
        self._services = {s.id: s for s in services}
        self._salt = phone_hash_salt
        self._sms = sms
        self._runner = runner

    def execute(self, phone: str, text: str, channel: Channel, call_sid: str | None = None) -> AskResult:
        number = PhoneNumber.parse(phone)  # raises InvalidPhone
        question = " ".join(text.split())
        if not question:
            raise ValueError("empty question")  # interfaces must not send empty text

        conversation_id = self._conversations.get_or_create(number)
        history = self._conversations.recent_messages(number, HISTORY_MESSAGES_TO_LOAD)
        self._conversations.add_message(
            conversation_id, Message(role=Role.USER, channel=channel, text=question), call_sid
        )

        started = time.perf_counter()
        try:
            answer = self._engine.answer(question, history, channel)
        except DomainError:
            latency_ms = _ms_since(started)
            self._log(number, channel, question, None, latency_ms, failed=True)
            log.warning("engine failed after %d ms (channel=%s)", latency_ms, channel)
            raise
        latency_ms = _ms_since(started)

        reply = answer.speech_text if channel is Channel.VOICE else answer.display_text
        self._conversations.add_message(
            conversation_id,
            Message(
                role=Role.ASSISTANT, channel=channel, text=reply,
                service_id=_stored_service(answer), status=answer.status,
            ),  # fmt: skip
            call_sid,
        )
        sms_services: list[str] = []
        if answer.status is AnswerStatus.ANSWERED:
            for checklist in _checklists(answer):  # one per service (FR-AGT-21)
                send_sms = self._sms_due(channel, call_sid, checklist)
                # Saving with sms_sent=True is the "mark first" of FR-SMS-02.
                self._checklists.save(
                    number, checklist, answer.citations, sms_sent=send_sms, call_sid=call_sid
                )
                if send_sms:
                    sms_services.append(checklist.service_id)
                    self._queue_sms(number, checklist)
        self._log(number, channel, question, answer, latency_ms)
        log.info(
            "answered status=%s service=%s latency_ms=%d llm_calls=%d channel=%s",
            answer.status, answer.service_id, latency_ms, answer.llm_calls, channel,
        )  # fmt: skip

        service = self._services.get(answer.service_id) if answer.service_id else None
        ids = answer.service_ids or ((answer.service_id,) if answer.service_id else ())
        services = tuple(self._services[i] for i in ids if i in self._services)
        return AskResult(
            conversation_id, answer, service, latency_ms,
            sms_scheduled=bool(sms_services), sms_services=tuple(sms_services), services=services,
        )  # fmt: skip

    def _sms_due(self, channel: Channel, call_sid: str | None, checklist: Checklist) -> bool:
        """True when this answer is the first one about its service in this call (FR-SMS-01, 02)."""
        if channel is not Channel.VOICE or not call_sid:
            return False
        if self._sms is None or self._runner is None:
            return False
        if checklist.service_id not in self._services:
            log.warning("no SMS: unknown service %s", checklist.service_id)
            return False
        return not self._checklists.sms_already_sent(call_sid, checklist.service_id)

    def _queue_sms(self, number: PhoneNumber, checklist: Checklist) -> None:
        assert self._runner is not None  # checked in _sms_due
        text = format_sms(checklist, self._services[checklist.service_id])
        self._runner.submit(self._send_sms, number, text, checklist.service_id)

    def _send_sms(self, number: PhoneNumber, text: str, service_id: str) -> None:
        """Runs in the background. Never raises; the result is only logged (FR-SMS-05)."""
        assert self._sms is not None
        try:
            ok = self._sms.send(number, text)
        except Exception:  # an adapter must not raise, but a bug in one must not go unnoticed
            log.exception("SMS adapter raised for service=%s", service_id)
            return
        if ok:
            log.info("SMS sent service=%s chars=%d", service_id, len(text))
        else:
            log.warning("SMS not sent service=%s (the call goes on normally)", service_id)

    def _log(
        self,
        number: PhoneNumber,
        channel: Channel,
        question: str,
        answer: Answer | None,
        latency_ms: int,
        failed: bool = False,
    ) -> None:
        self._logs.add(
            QuestionLog(
                phone_hash=hash_phone(number, self._salt),
                channel=channel,
                text=question,
                status=AnswerStatus.ERROR if failed or answer is None else answer.status,
                service_id=answer.service_id if answer else None,
                confidence=answer.confidence if answer else 0.0,
                router_source=answer.router_source if answer else None,
                latency_ms=latency_ms,
                llm_calls=answer.llm_calls if answer else 0,
                llm_backend=answer.llm_backend if answer else None,
            )
        )


def _checklists(answer: Answer) -> tuple[Checklist, ...]:
    """Every checklist of the answer; old single answers only fill `checklist`."""
    if answer.checklists:
        return answer.checklists
    return (answer.checklist,) if answer.checklist is not None else ()


def _stored_service(answer: Answer) -> str | None:
    """Two services are kept as "a,b" so a pending follow-up keeps both (no DB migration)."""
    if len(answer.service_ids) > 1:
        return ServiceSet.format(answer.service_ids)
    return answer.service_id


def _ms_since(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
