"""Sprint contract (T0): the new fields are additive, old answers behave exactly as before."""

from pathlib import Path

import pytest

from app.application.dto import AskResult
from app.config import Settings
from app.domain import policies
from app.domain.entities import (
    Answer,
    Checklist,
    Citation,
    Conflict,
    ConflictSide,
    Service,
    SituationProfile,
)
from app.domain.service_set import ServiceSet
from app.domain.value_objects import AnswerStatus, RouterSource
from app.infrastructure.catalog.yaml_services import load_services
from app.interfaces.api.schemas import ChatResponse

SERVICES_FILE = Path(__file__).resolve().parents[2] / "data" / "services.yaml"
OLD_AGE = Service("old_age_allowance", "বয়স্ক ভাতা", "Old Age Allowance", "অফিস", "বয়স্ক ভাতা")
WIDOW = Service("widow_allowance", "বিধবা ভাতা", "Widow Allowance", "অফিস", "বিধবা ভাতা")


def _checklist(service_id: str) -> Checklist:
    return Checklist(service_id, "৬৫ বছর", ("এনআইডি",), "বিনামূল্যে", "অফিস", "অফিস")


def _citation() -> Citation:
    return Citation("নীতিমালা", "https://dss.gov.bd", "…", "c1")


def _old_style_answer() -> Answer:
    return Answer(
        status=AnswerStatus.ANSWERED, speech_text="উত্তর", display_text="উত্তর",
        service_id="old_age_allowance", confidence=0.9, router_source=RouterSource.BANGLABERT,
        checklist=_checklist("old_age_allowance"), citations=(_citation(),),
    )  # fmt: skip


# ---------------------------------------------------------------- ServiceSet


@pytest.mark.parametrize("ids", [("old_age_allowance",), ("old_age_allowance", "widow_allowance"), ()])
def test_service_set_round_trip(ids: tuple[str, ...]) -> None:
    assert ServiceSet.parse(ServiceSet.format(ids)) == ids


def test_service_set_keeps_order_and_drops_repeats() -> None:
    assert ServiceSet.format(["widow_allowance", "old_age_allowance", "widow_allowance", " "]) == (
        "widow_allowance,old_age_allowance"
    )


@pytest.mark.parametrize("text", [None, "", ",", " , "])
def test_service_set_parse_empty(text: str | None) -> None:
    assert ServiceSet.parse(text) == ()


def test_old_single_id_parses_as_one_service() -> None:
    assert ServiceSet.parse("land_mutation") == ("land_mutation",)


# ---------------------------------------------------------------- Answer


def test_answer_defaults_keep_old_behaviour() -> None:
    answer = _old_style_answer()
    assert answer.mode == "single"
    assert answer.service_ids == () and answer.checklists == () and answer.conflicts == ()
    assert answer.situation is None


def test_answer_rejects_unknown_mode() -> None:
    with pytest.raises(ValueError):
        Answer(status=AnswerStatus.FALLBACK, speech_text="x", display_text="x", mode="both")


def test_router_source_situation_exists() -> None:
    assert RouterSource("situation") is RouterSource.SITUATION


# ---------------------------------------------------------------- ChatResponse


def test_chat_response_validates_an_old_style_answer() -> None:
    response = ChatResponse.of(AskResult("conv", _old_style_answer(), OLD_AGE, 120))
    data = response.model_dump()
    assert data["mode"] == "single" and data["situation"] is None and data["conflicts"] == []
    assert [s["id"] for s in data["services"]] == ["old_age_allowance"]
    assert data["checklists"][0]["service_id"] == "old_age_allowance"
    assert data["checklist"]["who"] == "৬৫ বছর"  # the old field is unchanged


def test_chat_response_multi_fields() -> None:
    conflict = Conflict(
        "বয়সের শর্ত",
        (
            ConflictSide("old_age_allowance", "৬৫ বছর", "c1", "নীতিমালা ক", "https://a"),
            ConflictSide("widow_allowance", "১৮ বছর", "c4", "নীতিমালা খ", "https://b"),
        ),
    )
    answer = Answer(
        status=AnswerStatus.ANSWERED, speech_text="দুটি", display_text="দুটি",
        service_id="old_age_allowance", checklist=_checklist("old_age_allowance"),
        citations=(_citation(),), service_ids=("old_age_allowance", "widow_allowance"),
        checklists=(_checklist("old_age_allowance"), _checklist("widow_allowance")),
        conflicts=(conflict,), situation=SituationProfile("বিধবা, বয়স ৬৬", (("age", "৬৬"),)),
        mode="multi", router_source=RouterSource.SITUATION,
    )  # fmt: skip
    result = AskResult("conv", answer, OLD_AGE, 10, services=(OLD_AGE, WIDOW))
    data = ChatResponse.of(result).model_dump()
    assert data["mode"] == "multi" and data["router"] == "situation"
    assert data["situation"] == {"summary_bn": "বিধবা, বয়স ৬৬", "facts": {"age": "৬৬"}}
    assert [s["id"] for s in data["services"]] == ["old_age_allowance", "widow_allowance"]
    assert [c["service_id"] for c in data["checklists"]] == ["old_age_allowance", "widow_allowance"]
    assert data["conflicts"][0]["sides"][1]["source_url"] == "https://b"


def test_ask_result_sms_count() -> None:
    answer = _old_style_answer()
    assert AskResult("c", answer, OLD_AGE, 1).sms_count == 0
    assert AskResult("c", answer, OLD_AGE, 1, sms_scheduled=True).sms_count == 1
    two = AskResult("c", answer, OLD_AGE, 1, sms_scheduled=True, sms_services=("a", "b"))
    assert two.sms_count == 2


# ---------------------------------------------------------------- config + catalog


def test_settings_defaults_come_from_policies() -> None:
    s = Settings(_env_file=None)
    assert s.situation_mode is policies.SITUATION_MODE
    assert s.multi_service_min_prob == policies.MULTI_SERVICE_MIN_PROB
    assert s.max_services_per_question == 2 and s.query_expansion is True
    assert s.max_speech_words_multi == 60


def test_every_real_service_has_search_terms() -> None:
    services = load_services(SERVICES_FILE)
    missing = [s.id for s in services if s.id != "other" and not s.search_terms_bn]
    assert missing == []
