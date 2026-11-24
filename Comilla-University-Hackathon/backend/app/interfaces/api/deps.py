"""FastAPI dependencies: how routers get the container and the use cases."""

from fastapi import Request

from app.application.use_cases.ask_question import AskQuestion
from app.application.use_cases.history import DeleteHistory, GetHistory
from app.application.use_cases.services import ListServices
from app.container import Container


def get_container(request: Request) -> Container:
    return request.app.state.container


def get_list_services(request: Request) -> ListServices:
    return get_container(request).list_services


def get_ask_question(request: Request) -> AskQuestion:
    return get_container(request).ask_question


def get_get_history(request: Request) -> GetHistory:
    return get_container(request).get_history


def get_delete_history(request: Request) -> DeleteHistory:
    return get_container(request).delete_history
