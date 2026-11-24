"""GET /health: status of the database, LLM, vector DB and router (NFR-REL-02)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.container import Container
from app.interfaces.api.deps import get_container

router = APIRouter(tags=["health"])


@router.get("/health", summary="Is every part of Ek Call working?")
def health(container: Annotated[Container, Depends(get_container)]) -> JSONResponse:
    report = container.health()
    # 503 lets a monitor (or a quick curl) see a problem without reading the body.
    return JSONResponse(status_code=200 if report["status"] == "ok" else 503, content=report)
