"""Delete ONE checklist from the history (NFR-PRIV-03): the repository contract on both the fake
and SQLite, and DELETE /api/v1/conversations/{phone}/checklists/{id}."""

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.domain.entities import Checklist
from app.domain.value_objects import PhoneNumber
from app.infrastructure.db import repositories as sql
from app.infrastructure.db.session import init_db, make_engine, make_session_factory
from app.main import create_app
from tests import fakes

A = PhoneNumber.parse("01712345678")
B = PhoneNumber.parse("01812345678")
NO_DIR = Path(__file__).parent / "no_such_dir"


def checklist(service: str) -> Checklist:
    return Checklist(service, "যোগ্যতা", ("এনআইডি",), "বিনামূল্যে", "অফিস", "ধাপ")


@pytest.fixture(params=["fake", "sql"])
def repo(request: pytest.FixtureRequest) -> Any:
    if request.param == "fake":
        return fakes.InMemoryChecklistRepo()
    engine = make_engine("sqlite://")
    init_db(engine)
    return sql.SqlChecklistRepo(make_session_factory(engine))


def test_every_listed_checklist_has_its_own_id(repo: Any) -> None:
    repo.save(A, checklist("nid_correction"), [], sms_sent=False)
    repo.save(A, checklist("old_age_allowance"), [], sms_sent=False)
    ids = [r.id for r in repo.list_for_phone(A, 10)]
    assert all(ids) and len(set(ids)) == 2


def test_delete_one_removes_only_that_checklist(repo: Any) -> None:
    repo.save(A, checklist("nid_correction"), [], sms_sent=False)
    repo.save(A, checklist("old_age_allowance"), [], sms_sent=False)
    newest, older = repo.list_for_phone(A, 10)
    assert repo.delete_one(A, older.id) is True
    assert [r.checklist.service_id for r in repo.list_for_phone(A, 10)] == [newest.checklist.service_id]
    assert repo.delete_one(A, older.id) is False  # already gone


def test_another_numbers_checklist_is_never_deleted(repo: Any) -> None:
    repo.save(B, checklist("nid_correction"), [], sms_sent=False)
    (theirs,) = repo.list_for_phone(B, 10)
    assert repo.delete_one(A, theirs.id) is False
    assert len(repo.list_for_phone(B, 10)) == 1


@pytest.mark.parametrize("bad_id", ["", "abc", "-1", "1; DROP TABLE checklists", "999999"])
def test_unknown_or_odd_ids_delete_nothing(repo: Any, bad_id: str) -> None:
    repo.save(A, checklist("nid_correction"), [], sms_sent=False)
    assert repo.delete_one(A, bad_id) is False
    assert len(repo.list_for_phone(A, 10)) == 1


def test_an_id_is_not_reused_after_a_delete(repo: Any) -> None:
    repo.save(A, checklist("nid_correction"), [], sms_sent=False)
    (first,) = repo.list_for_phone(A, 10)
    repo.delete_one(A, first.id)
    repo.save(A, checklist("old_age_allowance"), [], sms_sent=False)
    (second,) = repo.list_for_phone(A, 10)
    assert second.id != first.id


# ---------------------------------------------------------------- API


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(_env_file=None, database_url="sqlite://", chroma_dir=NO_DIR)
    with TestClient(create_app(settings)) as c:
        container = c.app.state.container  # type: ignore[attr-defined]
        container.checklists.save(A, checklist("nid_correction"), [], sms_sent=False)
        container.checklists.save(A, checklist("old_age_allowance"), [], sms_sent=True)
        container.checklists.save(B, checklist("birth_registration"), [], sms_sent=False)
        yield c


def history(client: TestClient, phone: str) -> list[dict[str, Any]]:
    response = client.get(f"/api/v1/conversations/{phone}")
    assert response.status_code == 200
    return response.json()["checklists"]  # type: ignore[no-any-return]


def test_history_shows_ids_and_one_can_be_deleted(client: TestClient) -> None:
    newest, older = history(client, "01712345678")
    assert newest["id"] and older["id"]
    response = client.delete(f"/api/v1/conversations/01712345678/checklists/{older['id']}")
    assert response.status_code == 200
    assert response.json() == {"deleted": True}
    assert [c["id"] for c in history(client, "01712345678")] == [newest["id"]]


def test_deleting_twice_or_another_numbers_checklist_is_404(client: TestClient) -> None:
    (theirs,) = history(client, "01812345678")
    assert client.delete(f"/api/v1/conversations/01712345678/checklists/{theirs['id']}").status_code == 404
    assert len(history(client, "01812345678")) == 1

    mine = history(client, "01712345678")[0]["id"]
    assert client.delete(f"/api/v1/conversations/01712345678/checklists/{mine}").status_code == 200
    assert client.delete(f"/api/v1/conversations/01712345678/checklists/{mine}").status_code == 404


def test_a_bad_phone_number_is_422(client: TestClient) -> None:
    assert client.delete("/api/v1/conversations/12345/checklists/1").status_code == 422
