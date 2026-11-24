"""POST /api/v1/tts: answer audio for the app (FR-APP-04, SRS 8).

Registered in main.py already. Returns audio/mpeg. Errors use the shared error JSON
(interfaces/api/errors.py): 422 BAD_REQUEST for empty or too long text, 400 TTS_FAILED when the
speech service gives no audio; the app then falls back to the browser's own Bangla voice.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.application.use_cases.speech import SynthesizeSpeech
from app.interfaces.api.deps import get_container

router = APIRouter(prefix="/api/v1", tags=["tts"])

MAX_TTS_CHARS = 2000  # an answer's speech_text is a few hundred characters


class TtsRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=MAX_TTS_CHARS,
        pattern=r"\S",
        examples=["পুরুষদের ৬৫ বছর হলে আবেদন করা যায়, আর আবেদন সম্পূর্ণ বিনামূল্যে।"],
    )


def get_synthesize_speech(request: Request) -> SynthesizeSpeech:
    return get_container(request).synthesize_speech


@router.post("/tts", response_class=Response, responses={200: {"content": {"audio/mpeg": {}}}})
def tts(body: TtsRequest, speak: Annotated[SynthesizeSpeech, Depends(get_synthesize_speech)]) -> Response:
    """FR-APP-04: the answer's speech_text as Bangla MP3."""
    return Response(content=speak.execute(body.text), media_type="audio/mpeg")
