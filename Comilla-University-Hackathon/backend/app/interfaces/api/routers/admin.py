"""Admin API (D2-R1: FR-ADM-01, 02, 05, SRS 8): login, stats and questions.

POST /api/v1/admin/login turns the admin password (ADMIN_TOKEN) into a short-lived session token.
Every other admin endpoint needs `Authorization: Bearer <session token>`. The X-Admin-Token header
with the password itself still works for Swagger and scripts; the web app never holds the password.
No ADMIN_TOKEN set: the admin area is closed (503) for everybody, in every APP_ENV.

`require_admin_token` is the shared admin check: routers/clusters.py uses it too.
Registered in main.py already.
"""

from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app.application.use_cases.admin import AdminQuestion, AdminStats, GetAdminStats, ListQuestions
from app.application.use_cases.admin_auth import AdminAuth, AdminDisabled, TooManyAttempts, WrongPassword
from app.domain.value_objects import AnswerStatus
from app.interfaces.api.deps import get_container


def get_admin_auth(request: Request) -> AdminAuth:
    return get_container(request).admin_auth


def _bearer(authorization: str | None) -> str | None:
    scheme, _, value = (authorization or "").partition(" ")
    return value.strip() if scheme.lower() == "bearer" and value.strip() else None


def no_store(response: Response) -> None:
    """Admin data must not stay in browser or proxy caches."""
    response.headers["Cache-Control"] = "no-store"


def require_admin_token(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    x_admin_token: Annotated[str | None, Header()] = None,
) -> None:
    """FR-ADM-05: a valid session token (web app) or the admin password header (Swagger, scripts)."""
    auth = get_admin_auth(request)
    if not auth.configured:
        raise HTTPException(status_code=503, detail="Admin is disabled: ADMIN_TOKEN is not set.")
    if not auth.allowed(_bearer(authorization), x_admin_token):
        raise HTTPException(status_code=401, detail="Admin login missing, wrong or expired.")


router = APIRouter(prefix="/api/v1/admin", tags=["admin"])
PROTECTED = [Depends(require_admin_token), Depends(no_store)]


# ------------------------------------------------------------------ login


class LoginRequest(BaseModel):
    password: str = Field(max_length=500)


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime


@router.post(
    "/login", summary="Admin password -> session token (8 h by default)", dependencies=[Depends(no_store)]
)
def login(
    body: LoginRequest,
    request: Request,
    auth: Annotated[AdminAuth, Depends(get_admin_auth)],
) -> LoginResponse:
    client = request.client.host if request.client else "unknown"
    try:
        session = auth.login(body.password, client)
    except AdminDisabled as exc:
        raise HTTPException(status_code=503, detail="Admin is disabled: ADMIN_TOKEN is not set.") from exc
    except TooManyAttempts as exc:
        raise HTTPException(
            status_code=429,
            detail=f"Too many wrong passwords. Try again in {exc.retry_after_s} s.",
            headers={"Retry-After": str(exc.retry_after_s)},
        ) from exc
    except WrongPassword as exc:
        raise HTTPException(status_code=401, detail="Wrong admin password.") from exc
    return LoginResponse(token=session.token, expires_at=datetime.fromtimestamp(session.expires_at, UTC))


# ------------------------------------------------------------------ response models


class ServiceCountOut(BaseModel):
    id: str
    name_bn: str
    count: int


class AdminStatsOut(BaseModel):
    total_questions: int
    answered_pct: float
    fallback_pct: float
    avg_latency_ms: int
    calls_today: int
    by_service: list[ServiceCountOut]
    by_channel: dict[str, int]
    by_status: dict[str, int]

    @classmethod
    def of(cls, s: AdminStats) -> "AdminStatsOut":
        return cls(
            total_questions=s.total_questions,
            answered_pct=s.answered_pct,
            fallback_pct=s.fallback_pct,
            avg_latency_ms=s.avg_latency_ms,
            calls_today=s.calls_today,
            by_service=[
                ServiceCountOut(id=c.service_id, name_bn=c.name_bn, count=c.count) for c in s.by_service
            ],
            by_channel=dict(s.by_channel),
            by_status=dict(s.by_status),
        )


class AdminQuestionOut(BaseModel):
    text: str
    status: str
    channel: str
    service_id: str | None
    service_name_bn: str | None
    router: str | None
    latency_ms: int
    is_demo: bool
    created_at: datetime

    @classmethod
    def of(cls, q: AdminQuestion) -> "AdminQuestionOut":
        return cls(
            text=q.text,
            status=q.status.value,
            channel=q.channel.value,
            service_id=q.service_id,
            service_name_bn=q.service_name_bn,
            router=q.router_source.value if q.router_source else None,
            latency_ms=q.latency_ms,
            is_demo=q.is_demo,
            created_at=q.created_at,
        )


class AdminQuestionsOut(BaseModel):
    questions: list[AdminQuestionOut]


# ------------------------------------------------------------------ routes


def get_admin_stats(request: Request) -> GetAdminStats:
    return get_container(request).get_admin_stats


def get_list_questions(request: Request) -> ListQuestions:
    return get_container(request).list_questions


StatusFilter = Literal["answered", "follow_up", "fallback", "error"]


@router.get(
    "/stats",
    summary="KPI numbers, questions per service and per channel, calls today",
    dependencies=PROTECTED,
)
def stats(use_case: Annotated[GetAdminStats, Depends(get_admin_stats)]) -> AdminStatsOut:
    return AdminStatsOut.of(use_case.execute())


@router.get(
    "/questions",
    summary="Newest logged questions; ?status=fallback lists the unanswered ones",
    dependencies=PROTECTED,
)
def questions(
    use_case: Annotated[ListQuestions, Depends(get_list_questions)],
    status: Annotated[StatusFilter | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AdminQuestionsOut:
    rows = use_case.execute(AnswerStatus(status) if status else None, limit)
    return AdminQuestionsOut(questions=[AdminQuestionOut.of(q) for q in rows])
