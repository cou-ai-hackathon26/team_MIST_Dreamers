"""grounding_guard and the two-service answer (sprint T5, FR-AGT-22). Plain code, no network.

The sprint's most important tests: a rule can never be blended across services, conflicts need a
grounded side from each service, and "can I get both?" is never answered without a document.
"""

from typing import Any

from app.application.agent import multi
from app.application.agent.grounding import grounding_guard
from app.domain.messages_bn import COMBINE_UNKNOWN, CONFLICT_NOTE, MULTI_INTRO

OLD, WIDOW = "old_age_allowance", "widow_allowance"
PASSAGES = {"P1": OLD, "P2": OLD, "P3": WIDOW, "P4": WIDOW}
SERVICES = [OLD, WIDOW]


def claim(text: str, sid: str, ids: list[str], core: bool = True) -> dict[str, Any]:
    return {"text": text, "service_id": sid, "passage_ids": ids, "core": core}


def section(sid: str, claims: list[dict[str, Any]]) -> dict[str, Any]:
    return {"service_id": sid, "speech_text": "নিয়ম", "checklist": {}, "claims": claims}


def side(sid: str, rule: str, ids: list[str]) -> dict[str, Any]:
    return {"service_id": sid, "rule_bn": rule, "passage_ids": ids}


def draft(**extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "no_answer": False,
        "sections": [
            section(OLD, [claim("বয়স ৬৫", OLD, ["P1"]), claim("এনআইডি", OLD, ["P2"], core=False)]),
            section(WIDOW, [claim("স্বামী মৃত", WIDOW, ["P3"])]),
        ],
        "conflicts": [],
        "asks_combine": True,
        "combine_rule": {"stated": False, "text_bn": None, "passage_ids": []},
    }
    return {**base, **extra}


def guard(d: dict[str, Any]) -> Any:
    return grounding_guard(d, PASSAGES, mode="multi", primary=OLD, services=SERVICES)


def kept_texts(result: Any, sid: str) -> list[str]:
    sec = next(s for s in result.draft["sections"] if s["service_id"] == sid)
    return [c["text"] for c in sec["claims"]]


# ---------------------------------------------------------------- claims


def test_clean_draft_passes_unchanged() -> None:
    result = guard(draft())
    assert not result.dropped_core and result.dropped == []
    assert kept_texts(result, OLD) == ["বয়স ৬৫", "এনআইডি"] and kept_texts(result, WIDOW) == ["স্বামী মৃত"]


def test_claim_of_one_service_citing_the_other_services_passage_is_dropped() -> None:
    d = draft()
    d["sections"][0]["claims"].append(claim("বিধবার কাগজ", OLD, ["P3"], core=False))  # blended rule
    result = guard(d)
    assert "বিধবার কাগজ" not in kept_texts(result, OLD)
    assert not result.dropped_core  # it was not core


def test_claim_citing_both_services_is_dropped() -> None:
    d = draft()
    d["sections"][0]["claims"][1] = claim("A, B আর C", OLD, ["P2", "P4"], core=False)
    assert kept_texts(guard(d), OLD) == ["বয়স ৬৫"]


def test_claim_tagged_with_another_service_inside_a_section_is_dropped() -> None:
    d = draft()
    d["sections"][0]["claims"].append(claim("স্বামী", WIDOW, ["P3"], core=False))
    assert kept_texts(guard(d), OLD) == ["বয়স ৬৫", "এনআইডি"]


def test_claim_citing_an_unknown_passage_is_dropped() -> None:
    d = draft()
    d["sections"][0]["claims"][1] = claim("ফি নেই", OLD, ["P2", "P9"], core=False)
    assert kept_texts(guard(d), OLD) == ["বয়স ৬৫"]


def test_dropping_a_core_claim_sets_dropped_core() -> None:
    d = draft()
    d["sections"][1]["claims"] = [claim("স্বামী মৃত", WIDOW, ["P1"])]  # core, cites old age
    result = guard(d)
    assert result.dropped_core and kept_texts(result, WIDOW) == []


def test_section_for_a_service_not_asked_for_is_dropped() -> None:
    d = draft()
    d["sections"].append(section("e_passport", [claim("পাসপোর্ট", "e_passport", ["P1"])]))
    assert [s["service_id"] for s in guard(d).draft["sections"]] == [OLD, WIDOW]


def test_single_mode_removes_unknown_ids_but_drops_other_service_claims() -> None:
    single = {"claims": [claim("বয়স", OLD, ["P1", "P9"]), claim("বিধবা", OLD, ["P3"], core=False)]}
    result = grounding_guard(single, PASSAGES, mode="single", primary=OLD)
    assert result.draft["claims"] == [claim("বয়স", OLD, ["P1"])]
    assert not result.dropped_core
    lost = grounding_guard({"claims": [claim("বিধবা", OLD, ["P3"])]}, PASSAGES, primary=OLD)
    assert lost.dropped_core and lost.draft["claims"] == []


# ---------------------------------------------------------------- conflicts


def test_conflict_with_only_one_side_is_dropped() -> None:
    d = draft(conflicts=[{"topic_bn": "বয়স", "sides": [side(OLD, "৬৫ বছর", ["P1"])]}])
    assert guard(d).draft["conflicts"] == []


def test_conflict_where_both_sides_are_the_same_service_is_dropped() -> None:
    sides = [side(OLD, "৬৫ বছর", ["P1"]), side(OLD, "৬২ বছর", ["P2"])]
    assert guard(draft(conflicts=[{"topic_bn": "বয়স", "sides": sides}])).draft["conflicts"] == []


def test_conflict_side_citing_the_other_services_passage_is_dropped() -> None:
    sides = [side(OLD, "৬৫ বছর", ["P1"]), side(WIDOW, "১৮ বছর", ["P2"])]  # widow side cites old age
    assert guard(draft(conflicts=[{"topic_bn": "বয়স", "sides": sides}])).draft["conflicts"] == []


def test_valid_conflict_is_kept() -> None:
    sides = [side(OLD, "৬৫ বছর", ["P1"]), side(WIDOW, "১৮ বছরের বেশি", ["P4"])]
    kept = guard(draft(conflicts=[{"topic_bn": "বয়সের শর্ত", "sides": sides}])).draft["conflicts"]
    assert len(kept) == 1 and [s["service_id"] for s in kept[0]["sides"]] == [OLD, WIDOW]


# ---------------------------------------------------------------- combine rule


def test_combine_rule_stated_without_passages_becomes_not_stated() -> None:
    d = draft(combine_rule={"stated": True, "text_bn": "দুটোই পাবেন", "passage_ids": []})
    assert guard(d).draft["combine_rule"] == {"stated": False, "text_bn": None, "passage_ids": []}
    d = draft(combine_rule={"stated": True, "text_bn": "দুটোই পাবেন", "passage_ids": ["P9"]})
    assert guard(d).draft["combine_rule"]["stated"] is False


def test_combine_rule_with_a_real_passage_is_kept() -> None:
    d = draft(combine_rule={"stated": True, "text_bn": "একসাথে দুটি ভাতা দেওয়া হয় না", "passage_ids": ["P3"]})
    assert guard(d).draft["combine_rule"]["stated"] is True


# ---------------------------------------------------------------- finalize multi: speech


def speech(conflicts: bool, combine: str | None = None, asks: bool = True) -> str:
    long_line = "এই সেবার জন্য " + "অনেক কথা " * 40
    return multi.build_speech(["বয়স্ক ভাতা", "বিধবা ভাতা"], [long_line, long_line], conflicts, combine, asks, 60)


def test_multi_speech_is_at_most_60_words_and_names_both_services() -> None:
    text = speech(conflicts=True)
    assert len(text.split()) <= 60
    assert "বয়স্ক ভাতা" in text and "বিধবা ভাতা" in text
    assert text.startswith(MULTI_INTRO.format(a="বয়স্ক ভাতা", b="বিধবা ভাতা"))


def test_multi_speech_has_conflict_note_only_when_there_are_conflicts() -> None:
    assert CONFLICT_NOTE in speech(conflicts=True)
    assert CONFLICT_NOTE not in speech(conflicts=False)


def test_multi_speech_never_states_a_combine_rule_when_not_stated() -> None:
    text = speech(conflicts=False, combine=None, asks=True)
    assert COMBINE_UNKNOWN in text
    for invented in ("দুটোই পাবেন", "একসাথে পাবেন", "পাবেন না"):
        assert invented not in text
    assert COMBINE_UNKNOWN not in speech(conflicts=False, asks=False)


def test_multi_speech_repeats_a_stated_combine_rule() -> None:
    text = speech(conflicts=False, combine="একসাথে দুটি ভাতা দেওয়া হয় না।")
    assert "একসাথে দুটি ভাতা দেওয়া হয় না।" in text and COMBINE_UNKNOWN not in text


def test_service_lines_are_cut_at_sentence_or_comma_never_mid_phrase() -> None:
    two = "বয়স আঠারোর বেশি হতে হবে। বার্ষিক আয় অনূর্ধ্ব ৪৫,০০০ টাকা হতে হবে।"
    assert multi._words(two, 8) == "বয়স আঠারোর বেশি হতে হবে।"
    commas = "মহিলাদের বয়স কমপক্ষে ৬২ বছর, পুরুষের ৬৫ বছর, আর বার্ষিক আয় অনূর্ধ্ব ৪৫,০০০ টাকা হতে হবে।"
    assert multi._words(commas, 9) == "মহিলাদের বয়স কমপক্ষে ৬২ বছর, পুরুষের ৬৫ বছর।"
    assert multi._words("ছোট বাক্য।", 9) == "ছোট বাক্য।"


def test_two_sides_stating_the_same_rule_are_agreement_not_a_conflict() -> None:
    sides = [
        side(OLD, "অন্য কোনোভাবে নিয়মিত সরকারী অনুদান/ভাতা প্রাপ্ত হলে ভাতা পাওয়ার অযোগ্য বলে গণ্য হবে।", ["P1"]),
        side(WIDOW, "অন্য কোনোভাবে নিয়মিত সরকারি অনুদান/ভাতা প্রাপ্ত হলে ভাতা পাওয়ার অযোগ্য বলে গণ্য হবে।", ["P3"]),
    ]
    assert guard(draft(conflicts=[{"topic_bn": "অন্য ভাতা", "sides": sides}])).draft["conflicts"] == []


def test_whole_first_sentences_are_kept_when_they_fit_together() -> None:
    # 13 + 10 words = the 23 words left by the intro and both notes
    long_first = "বিধবা ভাতার জন্য বয়স আঠারোর বেশি ও বার্ষিক আয় অনূর্ধ্ব পঁয়তাল্লিশ হাজার টাকা। আরও কথা।"
    short = "বয়স্ক ভাতার জন্য মহিলাদের বয়স কমপক্ষে ৬২ বছর হতে হবে।"
    text = multi.build_speech(["বিধবা ভাতা", "বয়স্ক ভাতা"], [long_first, short], True, None, True, 60)
    assert "পঁয়তাল্লিশ হাজার টাকা।" in text and short in text and "আরও কথা" not in text
    assert len(text.split()) <= 60


# ---------------------------------------------------------------- direct answer ("which first?")

FIRST = "আগে জন্ম নিবন্ধন করুন, কারণ পাসপোর্টের আবেদনে জন্ম নিবন্ধন সনদ লাগে।"


def test_direct_answer_needs_real_passages() -> None:
    kept = guard(draft(direct_answer={"stated": True, "text_bn": FIRST, "passage_ids": ["P3"]}))
    assert kept.draft["direct_answer"]["stated"] is True
    for ids in ([], ["P9"]):
        dropped = guard(draft(direct_answer={"stated": True, "text_bn": FIRST, "passage_ids": ids}))
        assert dropped.draft["direct_answer"] == {"stated": False, "text_bn": None, "passage_ids": []}


def test_unsupported_direct_answer_is_removed_by_verify() -> None:
    d = guard(draft(direct_answer={"stated": True, "text_bn": FIRST, "passage_ids": ["P3"]})).draft
    items = multi.verify_items(d, {})
    index = next(i for i, item in enumerate(items) if item.kind == "direct")
    verdicts = {i: True for i in range(len(items))}
    assert multi.direct_text(multi.apply_verdicts(d, items, verdicts)) == FIRST
    verdicts[index] = False
    assert multi.direct_text(multi.apply_verdicts(d, items, verdicts)) is None


def test_direct_answer_comes_right_after_the_intro_and_is_never_cut() -> None:
    long = "এই সেবার জন্য " + "অনেক কথা " * 20
    text = multi.build_speech(["জন্ম নিবন্ধন", "ই-পাসপোর্ট"], [long, long], False, None, False, 60, direct=FIRST)
    intro = MULTI_INTRO.format(a="জন্ম নিবন্ধন", b="ই-পাসপোর্ট")
    assert text.startswith(f"{intro} {FIRST}") and len(text.split()) <= 60
