"""Twilio voice webhooks: /voice/incoming, /voice/start, /voice/respond, /voice/result, /voice/status.

Filled in steps D1-A3, D1-A5, D2-A1, D2-A2 (FR-CALL-01 to 12, SRS 3.1). Registered in main.py already,
so adding routes here never needs a change in main.py.

Only converts Twilio form fields to use-case calls and VoiceReply to TwiML; the turn rules live in
app/application/use_cases/speech.py.
"""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Query, Request, Response

from app.application.use_cases.handle_call_end import HandleCallEnd, RecordCallStart
from app.application.use_cases.speech import VoiceReply
from app.application.use_cases.start_callback import HandleMissedCall
from app.application.use_cases.voice_jobs import GAVE_UP, Pending, VoiceAnswers
from app.interfaces.api.deps import get_container
from app.interfaces.voice import twiml
from app.interfaces.voice.call_state import SilenceCounter
from app.interfaces.voice.security import verify_twilio_signature

log = logging.getLogger(__name__)

router = APIRouter(
    prefix="/voice",
    tags=["voice"],
    dependencies=[Depends(verify_twilio_signature)],  # FR-CALL-12
)

TWIML_MEDIA_TYPE = "application/xml"
MAX_SILENCES = 2  # SRS 3.1: REPROMPT once, GOODBYE on the second silence
CALL_OVER = {"completed", "busy", "failed", "no-answer", "canceled"}


def get_voice_config(request: Request) -> twiml.VoiceConfig:
    return twiml.VoiceConfig.from_settings(get_container(request).settings)


def get_silence_counter(request: Request) -> SilenceCounter:
    return get_container(request).silence_counter


def get_voice_answers(request: Request) -> VoiceAnswers:
    return get_container(request).voice_answers


def get_record_call_start(request: Request) -> RecordCallStart:
    return get_container(request).record_call_start


def get_handle_call_end(request: Request) -> HandleCallEnd:
    return get_container(request).handle_call_end


def get_missed_call_mode(request: Request) -> bool:
    return get_container(request).settings.missed_call_mode


def get_handle_missed_call(request: Request) -> HandleMissedCall:
    return get_container(request).handle_missed_call


def citizen_number(from_: str, to: str, direction: str) -> str:
    """The citizen is the caller on inbound calls and the called party on our call-backs."""
    return to if direction.startswith("outbound") else from_


def _twiml(xml: str) -> Response:
    return Response(content=xml, media_type=TWIML_MEDIA_TYPE)


Config = Annotated[twiml.VoiceConfig, Depends(get_voice_config)]
Silences = Annotated[SilenceCounter, Depends(get_silence_counter)]
Answers = Annotated[VoiceAnswers, Depends(get_voice_answers)]
CallSid = Annotated[str, Form(alias="CallSid")]
From = Annotated[str, Form(alias="From")]
To = Annotated[str, Form(alias="To")]
Direction = Annotated[str, Form(alias="Direction")]


def _greet(
    cfg: twiml.VoiceConfig, record: RecordCallStart, call_sid: str, phone: str, direction: str
) -> Response:
    try:
        record.execute(call_sid, phone, direction)  # FR-CALL-11; a storage problem never blocks the greeting
    except Exception:
        log.exception("could not store the call start call_sid=%s", call_sid)
    return _twiml(twiml.greet(cfg))


@router.post("/incoming", response_class=Response)
def incoming(
    request: Request,
    cfg: Config,
    record: Annotated[RecordCallStart, Depends(get_record_call_start)],
    call_sid: CallSid = "",
    from_: From = "",
    to: To = "",
    direction: Direction = "inbound",
) -> Response:
    """FR-CALL-01: a citizen called the Twilio number. FR-CALL-08: missed-call mode rejects, calls back."""
    if get_missed_call_mode(request):
        try:
            get_handle_missed_call(request).execute(from_)
        except Exception:
            log.exception("could not schedule the call-back call_sid=%s", call_sid)
        log.info("missed call rejected call_sid=%s", call_sid)
        return _twiml(twiml.reject_busy())
    return _greet(cfg, record, call_sid, citizen_number(from_, to, direction), direction)


@router.post("/start", response_class=Response)
def start(
    cfg: Config,
    record: Annotated[RecordCallStart, Depends(get_record_call_start)],
    call_sid: CallSid = "",
    from_: From = "",
    to: To = "",
    direction: Direction = "outbound-api",
) -> Response:
    """FR-CALL-07: our outbound call (call-back) was answered; the same flow starts."""
    return _greet(cfg, record, call_sid, citizen_number(from_, to, direction), direction)


@router.post("/respond", response_class=Response)
def respond(
    cfg: Config,
    silences: Silences,
    answers: Answers,
    call_sid: CallSid = "",
    speech: Annotated[str, Form(alias="SpeechResult")] = "",
    from_: From = "",
    to: To = "",
    direction: Direction = "inbound",
) -> Response:
    """FR-CALL-02 to 06, 09, 10: one caller turn."""
    text = speech.strip()
    if not text:
        count = silences.silent(call_sid)
        log.info("voice silence call_sid=%s count=%d", call_sid, count)
        if count >= MAX_SILENCES:
            silences.forget(call_sid)
            return _twiml(twiml.goodbye(cfg))
        return _twiml(twiml.reprompt(cfg))

    silences.heard(call_sid)
    log.info("voice heard call_sid=%s text=%s", call_sid, text)
    try:
        outcome = answers.start(call_sid, citizen_number(from_, to, direction), text, direction)
    except Exception:  # NFR-REL-01: a 500 would make Twilio say "application error" and hang up
        log.exception("voice turn crashed call_sid=%s", call_sid)
        outcome = GAVE_UP
    if isinstance(outcome, Pending):
        return _twiml(twiml.wait_for_answer(cfg, outcome.job_id))
    return _speak(cfg, silences, call_sid, outcome)


@router.post("/result", response_class=Response)
def result(
    cfg: Config,
    silences: Silences,
    answers: Answers,
    job: Annotated[str, Query()] = "",
    call_sid: CallSid = "",
) -> Response:
    """FR-CALL-10: the answer of a slow turn, once it is ready (Twilio follows our <Redirect>)."""
    try:
        outcome = answers.result(job)
    except Exception:  # NFR-REL-01, see respond()
        log.exception("voice result crashed call_sid=%s job=%s", call_sid, job)
        outcome = GAVE_UP
    if isinstance(outcome, Pending):
        return _twiml(twiml.keep_waiting(cfg, outcome.job_id))
    return _speak(cfg, silences, call_sid, outcome)


def _speak(cfg: twiml.VoiceConfig, silences: SilenceCounter, call_sid: str, reply: VoiceReply) -> Response:
    if reply.hang_up:
        silences.forget(call_sid)
    return _twiml(twiml.reply(cfg, reply.say, reply.hang_up))


@router.post("/status", status_code=204, response_class=Response)
def status(
    silences: Silences,
    end: Annotated[HandleCallEnd, Depends(get_handle_call_end)],
    call_sid: CallSid = "",
    call_status: Annotated[str, Form(alias="CallStatus")] = "",
) -> Response:
    """Twilio status callback: stores the end time (FR-CALL-11)."""
    log.info("voice status call_sid=%s status=%s", call_sid, call_status)
    if call_status in CALL_OVER:
        silences.forget(call_sid)
        try:
            end.execute(call_sid)
        except Exception:
            log.exception("could not store the call end call_sid=%s", call_sid)
    return Response(status_code=204)
