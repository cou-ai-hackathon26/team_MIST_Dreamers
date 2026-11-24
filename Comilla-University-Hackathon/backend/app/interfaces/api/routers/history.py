"""GET / DELETE /api/v1/conversations/{phone} (FR-APP-05, NFR-PRIV-03)."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from app.application.use_cases.history import DeleteHistory, GetHistory
from app.application.use_cases.history_items import DeleteChecklist
from app.interfaces.api.deps import get_container, get_delete_history, get_get_history
from app.interfaces.api.schemas import DeleteResponse, HistoryResponse

router = APIRouter(prefix="/api/v1", tags=["history"])


@router.get("/conversations/{phone}", summary="Messages and checklists for a phone number")
def get_history(
    phone: str,
    use_case: Annotated[GetHistory, Depends(get_get_history)],
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> HistoryResponse:
    return HistoryResponse.of(use_case.execute(phone, limit))


@router.delete("/conversations/{phone}", summary="Delete all history for a phone number")
def delete_history(
    phone: str, use_case: Annotated[DeleteHistory, Depends(get_delete_history)]
) -> DeleteResponse:
    return DeleteResponse(deleted=use_case.execute(phone))


# --- one checklist (Ariful: the app's History page lets the user pick what to delete)
def get_delete_checklist(request: Request) -> DeleteChecklist:
    return get_container(request).delete_checklist


@router.delete("/conversations/{phone}/checklists/{checklist_id}", summary="Delete one checklist")
def delete_checklist(
    phone: str, checklist_id: str, use_case: Annotated[DeleteChecklist, Depends(get_delete_checklist)]
) -> DeleteResponse:
    use_case.execute(phone, checklist_id)  # 404 if this number has no checklist with that id
    return DeleteResponse(deleted=True)
