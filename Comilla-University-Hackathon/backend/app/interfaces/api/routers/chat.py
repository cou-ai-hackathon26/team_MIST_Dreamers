"""POST /api/v1/chat (FR-APP-02, SRS 8)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.use_cases.ask_question import AskQuestion
from app.domain.value_objects import Channel
from app.interfaces.api.deps import get_ask_question
from app.interfaces.api.schemas import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post("/chat", summary="Ask Ek Call a question (web app)")
def chat(body: ChatRequest, use_case: Annotated[AskQuestion, Depends(get_ask_question)]) -> ChatResponse:
    result = use_case.execute(phone=body.phone, text=body.message, channel=Channel.APP)
    return ChatResponse.of(result)
