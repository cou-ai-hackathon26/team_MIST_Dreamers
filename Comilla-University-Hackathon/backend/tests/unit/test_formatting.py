from app.application.formatting import ELLIPSIS, format_sms, limit_sentences, trim_speech
from app.domain.entities import Checklist, Service

SERVICE = Service(
    id="old_age_allowance",
    name_bn="বয়স্ক ভাতা",
    name_en="Old Age Allowance",
    office_bn="উপজেলা সমাজসেবা অফিস",
    sms_name="বয়স্ক ভাতা",
)
CHECKLIST = Checklist(
    service_id="old_age_allowance",
    who="পুরুষ ৬৫+, নারী ৬২+, স্থায়ী বাসিন্দা",
    papers=("এনআইডি/জন্ম নিবন্ধন",),
    fee="বিনামূল্যে",
    where="অনলাইনে বা উপজেলা সমাজসেবা অফিস",
    decision="স্থানীয় বাছাই কমিটি",
)


# ---------- format_sms ----------


def test_sms_matches_srs_example() -> None:
    sms = format_sms(CHECKLIST, SERVICE, source="সমাজসেবা অধিদফতর")
    assert sms == (
        "এক কল: বয়স্ক ভাতা\n"
        "কারা: পুরুষ ৬৫+, নারী ৬২+, স্থায়ী বাসিন্দা\n"
        "লাগবে: এনআইডি/জন্ম নিবন্ধন\n"
        "ফি: বিনামূল্যে\n"
        "কোথায়: অনলাইনে বা উপজেলা সমাজসেবা অফিস\n"
        "সূত্র: সমাজসেবা অধিদফতর"
    )


def test_source_defaults_to_service_office() -> None:
    assert format_sms(CHECKLIST, SERVICE).endswith("সূত্র: উপজেলা সমাজসেবা অফিস")


def test_long_sms_is_cut_to_300_chars_keeping_title_and_fee() -> None:
    long_papers = tuple(f"কাগজ নম্বর {i} এর সত্যায়িত ফটোকপি" for i in range(30))
    checklist = Checklist(**{**CHECKLIST.__dict__, "papers": long_papers})
    sms = format_sms(checklist, SERVICE)
    assert len(sms) <= 300
    assert sms.startswith("এক কল: বয়স্ক ভাতা\n")
    assert "ফি: বিনামূল্যে" in sms
    assert ELLIPSIS in sms


def test_lines_are_shortened_at_word_boundaries() -> None:
    long_papers = tuple(f"কাগজ{i}" for i in range(200))
    checklist = Checklist(**{**CHECKLIST.__dict__, "papers": long_papers})
    papers_line = next(line for line in format_sms(checklist, SERVICE).split("\n") if line.startswith("লাগবে"))
    # Every kept item is a whole word ("কাগজN"), never a broken one like "কাগ".
    items = papers_line.removeprefix("লাগবে: ").removesuffix(ELLIPSIS).split(", ")
    assert all(item.startswith("কাগজ") and item[4:].isdigit() for item in items)


def test_empty_lines_are_skipped() -> None:
    checklist = Checklist(**{**CHECKLIST.__dict__, "papers": ()})
    assert "লাগবে" not in format_sms(checklist, SERVICE)


# ---------- trim_speech ----------


def test_short_speech_is_unchanged() -> None:
    text = "পুরুষদের ৬৫ বছর হলে আবেদন করা যায়। আবেদন বিনামূল্যে।"
    assert trim_speech(text) == text


def test_long_speech_stops_at_a_sentence_end() -> None:
    first = " ".join(["শব্দ"] * 29) + " শেষ।"  # 30 words, ends with a danda
    second = " ".join(["আরও"] * 30) + "।"  # pushes the total past 45
    result = trim_speech(f"{first} {second}")
    assert result == first
    assert len(result.split()) <= 45


def test_long_speech_without_early_sentence_end_is_cut_at_the_limit() -> None:
    text = " ".join(["শব্দ"] * 100)
    result = trim_speech(text)
    assert len(result.split()) == 45
    assert result.endswith("।")


def test_extra_spaces_are_collapsed() -> None:
    assert trim_speech("  আবেদন   বিনামূল্যে।  ") == "আবেদন বিনামূল্যে।"


def test_limit_sentences_keeps_the_first_three_and_leaves_short_text_alone() -> None:
    five = "এক। দুই। তিন। চার। পাঁচ।"
    assert limit_sentences(five) == "এক। দুই। তিন।"
    assert limit_sentences("এক। দুই?") == "এক। দুই?"
    assert limit_sentences("কোনো দাঁড়ি নেই") == "কোনো দাঁড়ি নেই"
