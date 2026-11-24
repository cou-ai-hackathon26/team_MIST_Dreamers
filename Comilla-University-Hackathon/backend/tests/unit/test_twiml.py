"""TwiML snapshots for the call flow (SRS 3.1, FR-CALL-01, 03, 04)."""

from app.domain import messages_bn
from app.interfaces.voice import twiml

CFG = twiml.VoiceConfig(stt_language="bn-BD", tts_voice="Google.bn-IN-Standard-A", tts_language="bn-IN")

XML = '<?xml version="1.0" encoding="UTF-8"?>'
GATHER = (
    f'<Gather action="/voice/respond" actionOnEmptyResult="true" hints="{twiml.SPEECH_HINTS}" '
    'input="speech" language="bn-BD" method="POST" speechTimeout="2">'
)


def say(text: str) -> str:
    return f'<Say language="bn-IN" voice="Google.bn-IN-Standard-A">{text}</Say>'


def test_greet_says_greeting_inside_gather() -> None:
    assert twiml.greet(CFG) == f"{XML}<Response>{GATHER}{say(messages_bn.GREETING)}</Gather></Response>"


def test_answer_and_listen_adds_continue_inside_the_same_gather() -> None:
    expected = f"{XML}<Response>{GATHER}{say('উত্তর')}{say(messages_bn.CONTINUE)}</Gather></Response>"
    assert twiml.answer_and_listen(CFG, "উত্তর") == expected


def test_reprompt_listens_again() -> None:
    assert twiml.reprompt(CFG) == f"{XML}<Response>{GATHER}{say(messages_bn.REPROMPT)}</Gather></Response>"


def test_goodbye_hangs_up_without_listening() -> None:
    assert twiml.goodbye(CFG) == f"{XML}<Response>{say(messages_bn.GOODBYE)}<Hangup /></Response>"


def test_answer_text_is_xml_escaped() -> None:
    assert "&lt;b&gt; &amp;" in twiml.answer_and_listen(CFG, "<b> &")


def test_config_comes_from_settings() -> None:
    from app.config import Settings

    settings = Settings(_env_file=None, stt_language="bn-IN", public_url="https://x.ngrok-free.dev/")
    cfg = twiml.VoiceConfig.from_settings(settings)
    assert cfg.stt_language == "bn-IN"
    assert cfg.respond_url == "https://x.ngrok-free.dev/voice/respond"
    assert 'action="https://x.ngrok-free.dev/voice/respond"' in twiml.greet(cfg)
