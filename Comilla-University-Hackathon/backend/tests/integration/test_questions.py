"""The hand-written question sets (FR-DATA-04): right shape, every label covered, no leaks."""

import csv
import re
from collections import Counter
from pathlib import Path

import pytest

from app.config import BACKEND_DIR
from app.infrastructure.catalog.yaml_services import load_services

QUESTIONS = BACKEND_DIR / "data" / "questions"
LABELS = {s.id for s in load_services(BACKEND_DIR / "data" / "services.yaml")}


def read(name: str) -> list[dict[str, str]]:
    path: Path = QUESTIONS / name
    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf"), f"{name}: keep plain UTF-8 in the repo (no BOM)"
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def norm(text: str) -> str:
    """Same question despite spaces, punctuation or case."""
    return re.sub(r"[\s?।,!.]+", " ", text).strip().lower()


SEED = read("seed.csv")
TEST = read("test.csv")
OUT = read("out_of_scope.csv")


@pytest.mark.parametrize(("rows", "columns"), [(SEED, ["text", "label"]), (TEST, ["text", "label"])])
def test_columns_and_labels_are_valid(rows: list[dict[str, str]], columns: list[str]) -> None:
    assert list(rows[0].keys()) == columns
    assert {r["label"] for r in rows} == LABELS  # every label, nothing else
    assert all(r["text"].strip() for r in rows)


@pytest.mark.parametrize(("rows", "minimum"), [(SEED, 15), (TEST, 12)])
def test_every_label_has_enough_questions(rows: list[dict[str, str]], minimum: int) -> None:
    counts = Counter(r["label"] for r in rows)
    assert min(counts.values()) >= minimum, counts


def test_no_duplicates_inside_a_file() -> None:
    for rows in (SEED, TEST, OUT):
        texts = [norm(r["text"]) for r in rows]
        assert len(texts) == len(set(texts)), [t for t, n in Counter(texts).items() if n > 1]


def test_the_test_set_never_repeats_a_seed_or_out_of_scope_question() -> None:
    seed = {norm(r["text"]) for r in SEED}
    out = {norm(r["text"]) for r in OUT}
    test = {norm(r["text"]) for r in TEST}
    assert not test & seed
    assert not test & out
    assert not seed & out


def test_out_of_scope_has_25_questions_with_topics() -> None:
    assert list(OUT[0].keys()) == ["text", "topic"]
    assert len(OUT) == 25
    assert {"land_dispute", "weather", "cricket", "medical", "bank_loan"} <= {r["topic"] for r in OUT}


def test_some_questions_are_banglish_like_real_users_type() -> None:
    latin = [r for r in SEED + TEST if re.search(r"[a-zA-Z]{3,}", r["text"])]
    assert len(latin) >= 15
