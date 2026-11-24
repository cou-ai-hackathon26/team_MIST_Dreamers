"""GET /api/v1/services (FR-DATA-01)."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.application.use_cases.services import ListServices
from app.interfaces.api.deps import get_list_services
from app.interfaces.api.schemas import ServiceOut

router = APIRouter(prefix="/api/v1", tags=["services"])


@router.get("/services", summary="The 8 services Ek Call knows, plus `other`")
def list_services(use_case: Annotated[ListServices, Depends(get_list_services)]) -> list[ServiceOut]:
    return [ServiceOut.of(s) for s in use_case.execute()]
