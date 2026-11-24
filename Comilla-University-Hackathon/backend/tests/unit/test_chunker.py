from datetime import date
from pathlib import Path

import pytest

from app.infrastructure.retrieval.chunker import chunk_documents, split_long_text, split_sections
from app.infrastructure.retrieval.documents import SourceDocument


def doc(body: str, service_id: str = "old_age_allowance", name: str = "a.md") -> SourceDocument:
    return SourceDocument(
        service_id=service_id,
        path=Path(service_id) / name,
        title="বয়স্ক ভাতা",
        source_url="https://example.gov.bd/x",
        office="অফিস",
        collected_on=date(2026, 11, 20),
        body=body,
    )


def words(n: int, word: str = "শব্দ") -> str:
    return " ".join(f"{word}{i}" for i in range(n))


def test_split_sections_uses_level_2_headings_and_keeps_intro_text() -> None:
    body = "ভূমিকা লেখা\n\n## যোগ্যতা\nবয়স ৬৫\n\n## ফি\nকোনো ফি নেই\n### ছোট শিরোনাম থাকে লেখার ভিতরে"
    assert split_sections(body) == [
        ("", "ভূমিকা লেখা"),
        ("যোগ্যতা", "বয়স ৬৫"),
        ("ফি", "কোনো ফি নেই\n### ছোট শিরোনাম থাকে লেখার ভিতরে"),
    ]


def test_small_sections_of_one_document_are_packed_together() -> None:
    chunks = chunk_documents([doc("## যোগ্যতা\nবয়স ৬৫\n\n## ফি\nকোনো ফি নেই")], max_words=50, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].heading == "যোগ্যতা | ফি"
    assert "## যোগ্যতা" in chunks[0].text and "## ফি" in chunks[0].text


def test_sections_are_not_packed_past_the_limit() -> None:
    body = f"## এক\n{words(30)}\n\n## দুই\n{words(30)}"
    chunks = chunk_documents([doc(body)], max_words=40, overlap=5)
    assert [c.heading for c in chunks] == ["এক", "দুই"]


def test_long_section_is_cut_with_its_heading_repeated_and_overlap() -> None:
    paragraphs = "\n\n".join(words(20, f"p{i}-") for i in range(6))  # 120 words in 6 paragraphs
    chunks = chunk_documents([doc(f"## কাগজপত্র\n{paragraphs}")], max_words=50, overlap=10)
    assert len(chunks) >= 3
    assert all(c.text.startswith("## কাগজপত্র") for c in chunks)
    assert all(c.word_count <= 50 for c in chunks)
    first_tail = chunks[0].text.split()[-10:]
    assert chunks[1].text.split()[2:12] == first_tail  # after "## কাগজপত্র", the overlap repeats


def test_one_huge_paragraph_is_cut_into_word_windows() -> None:
    pieces = split_long_text(words(100), max_words=40, overlap=10)
    assert [len(p.split()) for p in pieces] == [40, 40, 40]
    assert pieces[1].split()[:10] == pieces[0].split()[-10:]


def test_no_piece_is_only_the_repeated_overlap() -> None:
    pieces = split_long_text(f"{words(30)}\n\n{words(30, 'x')}", max_words=40, overlap=10)
    assert len(pieces) == 2
    assert pieces[1].split()[-1] == "x29"


def test_chunk_ids_count_per_service_in_path_order() -> None:
    docs = [
        doc("## খ\nলেখা দুই", name="b.md"),
        doc("## ক\nলেখা এক", name="a.md"),
        doc("## গ\nঅন্য সেবা", service_id="e_passport"),
    ]
    chunks = chunk_documents(docs, max_words=4, overlap=0)  # each section fits, two do not
    ids = [c.chunk_id for c in chunks]
    assert ids == ["e_passport-001", "old_age_allowance-001", "old_age_allowance-002"]
    assert chunks[1].heading == "ক"  # a.md comes before b.md
    assert {c.source_url for c in chunks} == {"https://example.gov.bd/x"}


def test_bad_overlap_is_rejected() -> None:
    with pytest.raises(ValueError):
        chunk_documents([doc("লেখা")], max_words=10, overlap=10)
