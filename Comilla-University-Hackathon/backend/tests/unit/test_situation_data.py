"""Situation test data (D1, FR-DATA-10): file shapes and the "no service name" rule."""

import csv
from pathlib import Path

import pytest

from app.infrastructure.catalog.yaml_services import load_services

BACKEND = Path(__file__).resolve().parents[2]
QUESTIONS = BACKEND / "data" / "questions"
LABELS = {s.id for s in load_services(BACKEND / "data" / "services.yaml")}
# Words that name a service outright. A situational question describes the life situation instead.
SERVICE_NAME_WORDS = (
    "বয়স্ক ভাতা", "বিধবা ভাতা", "প্রতিবন্ধী ভাতা", "জন্ম নিবন্ধন", "এনআইডি", "পাসপোর্ট",
    "নামজারি", "ট্রেড লাইসেন্স",
)  # fmt: skip


def _rows(name: str) -> list[dict[str, str]]:
    with (QUESTIONS / name).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_check_set_is_appendix_c() -> None:
    rows = _rows("situation_check.csv")
    assert len(rows) == 18
    assert [r["label"] for r in rows[-2:]] == ["other", "vague"]
    assert {r["label"] for r in rows[:16]} == LABELS - {"other"}
    assert all("expected" not in r["text"] for r in rows)


@pytest.mark.parametrize("name", ["situation_check.csv", "situation_test.csv"])
def test_situational_rows_never_name_the_service(name: str) -> None:
    for row in _rows(name):
        assert row["label"] in LABELS | {"vague"}, row
        named = [w for w in SERVICE_NAME_WORDS if w in row["text"]]
        assert not named, f"{row['text']!r} names {named}"


def test_mixed_test_rows_are_well_formed() -> None:
    for row in _rows("mixed_test.csv"):
        labels = row["labels"].split(";")
        assert len(labels) == 2 and len(set(labels)) == 2, row
        assert set(labels) <= LABELS - {"other"}, row
        assert row["expects_conflict"] in ("yes", "no"), row
