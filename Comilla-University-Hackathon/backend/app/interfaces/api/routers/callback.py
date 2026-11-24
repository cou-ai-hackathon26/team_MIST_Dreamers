"""POST /api/v1/callback: "Call me" (FR-CALL-07, FR-APP-06, SRS 8).

Registered in main.py already. Errors use the shared error JSON (interfaces/api/errors.py):
422 INVALID_PHONE, 429 RATE_LIMITED (called in the last 60 s), 500 when Twilio refuses the call.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.application.use_cases.start_callback import StartCallback
from app.interfaces.api.deps import get_container

router = APIRouter(prefix="/api/v1", tags=["callback"])


class CallbackRequest(BaseModel):
    phone: str = Field(examples=["01712345678"], description="Bangladeshi mobile: 01..., 8801... or +8801...")


class CallbackResponse(BaseModel):
    call_sid: str


def get_start_callback(request: Request) -> StartCallback:
    return get_container(request).start_callback


@router.post("/callback", response_model=CallbackResponse)
def callback(
    body: CallbackRequest, start: Annotated[StartCallback, Depends(get_start_callback)]
) -> CallbackResponse:
    """FR-CALL-07: Ek Call phones the citizen; when they answer, the normal call flow starts."""
    return CallbackResponse(call_sid=start.execute(body.phone))
