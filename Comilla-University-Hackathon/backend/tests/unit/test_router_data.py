"""Augmentation rules (FR-DATA-05) and the shared text clean-up (FR-DATA-06). No network."""

from typing import Any

from app.application.ports.llm import ModelRole
from app.infrastructure.ml.text import normalize_text
from scripts import augment_questions as aug
from tests.fakes import FakeLLM


def seeds(per_label: int = 15) -> list[dict[str, str]]:
    return [
        {"text": f"{label} question {i}", "label": label}
        for label in ("old_age_allowance", "other")
        for i in range(per_label)
    ]


def test_split_is_by_seed_per_label_and_repeatable() -> None:
    train, val = aug.split_seeds(seeds())
    assert len(val) == 4 and len(train) == 26  # 2 val seeds per label (15 * 10% rounded up)
    assert {r["label"] for r in val} == {"old_age_allowance", "other"}
    assert not {r["text"] for r in train} & {r["text"] for r in val}
    assert aug.split_seeds(seeds()) == (train, val)


def test_build_rows_drops_duplicates_test_questions_and_foreign_scripts() -> None:
    seed = {"text": "বয়স্ক ভাতা কত টাকা?", "label": "old_age_allowance"}
    cache = {
        seed["text"]: [
            "বয়স্ক ভাতা কত টাকা",  # same as the seed without "?"
            "boyosko vata koto taka",  # Banglish: kept
            "ভাতা কত দেয়",  # equals a test question: dropped
            "ভোটারআইডিਕਾਰ্ড",  # Gurmukhi letters: dropped
        ]
    }
    rows = aug.build_rows([seed], cache, blocked={aug.norm_key("ভাতা কত দেয়?")})
    assert [r["text"] for r in rows] == [seed["text"], "boyosko vata koto taka"]
    assert {r["label"] for r in rows} == {"old_age_allowance"}


def test_ask_variants_maps_ids_and_ignores_bad_items() -> None:
    reply: dict[str, Any] = {
        "items": [
            {"id": 0, "variants": ["এক", "  ", "দুই"]},
            {"id": 7, "variants": ["out of range"]},
            {"id": "1", "variants": ["wrong id type"]},
        ]
    }
    llm = FakeLLM([reply])
    result = aug.ask_variants(llm, ["প্রথম", "দ্বিতীয়"])
    assert result == {0: ["এক", "দুই"]}
    assert llm.roles == [ModelRole.FAST]


def test_normalize_text_unifies_digits_case_punctuation_and_spaces() -> None:
    assert normalize_text("  আমার বয়স ৬৭।  Boyosko   VATA? ") == "আমার বয়স 67 boyosko vata"
    assert normalize_text("") == ""
