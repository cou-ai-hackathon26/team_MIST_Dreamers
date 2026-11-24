from datetime import date
from pathlib import Path

import pytest

from app.config import BACKEND_DIR
from app.infrastructure.retrieval.documents import (
    DocumentError,
    document_paths,
    load_documents,
    parse_document,
)

BODY = "## যোগ্যতা\n" + "পুরুষদের বয়স ৬৫ বছর এবং নারীদের বয়স ৬২ বছর হতে হবে। " * 4 + "\n\n## ফি\nবিনামূল্যে।\n"
META = (
    "title: বয়স্ক ভাতা\nsource_url: https://dss.gov.bd/page\n"
    "office: উপজেলা সমাজসেবা অফিস\ncollected_on: 2026-11-21\n"
)
DOTS_URL = "https://dss.gov.bd/..."


def write(tmp_path: Path, text: str, folder: str = "old_age_allowance", name: str = "doc.md") -> Path:
    path = tmp_path / folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_load_documents_keeps_good_files_and_explains_the_rest(tmp_path: Path) -> None:
    write(tmp_path, f"---\n{META}---\n{BODY}")
    write(tmp_path, f"---\n{META.replace('https://dss.gov.bd/page', DOTS_URL)}---\n{BODY}", name="b.md")
    write(tmp_path, f"---\n{META}---\n{BODY}", folder="weather")
    docs, problems = load_documents(tmp_path, ["old_age_allowance"])
    assert [d.path.name for d in docs] == ["doc.md"]
    assert len(problems) == 2
    assert any("b.md" in p and "not a real link" in p for p in problems)
    assert any("'weather' is not a service id" in p for p in problems)


def test_valid_document_is_parsed(tmp_path: Path) -> None:
    doc = parse_document(write(tmp_path, f"---\n{META}---\n{BODY}"), "old_age_allowance")
    assert doc.title == "বয়স্ক ভাতা"
    assert doc.collected_on == date(2026, 11, 21)
    assert doc.body.startswith("## যোগ্যতা")
    assert doc.word_count > 20


def test_windows_line_endings_are_fine(tmp_path: Path) -> None:
    text = f"---\n{META}---\n{BODY}".replace("\n", "\r\n")
    assert parse_document(write(tmp_path, text), "old_age_allowance").title == "বয়স্ক ভাতা"


@pytest.mark.parametrize(
    ("text", "reason"),
    [
        (BODY, "missing front matter"),
        (f"---\n{META.replace('office: উপজেলা সমাজসেবা অফিস', 'office:')}---\n{BODY}", "office"),
        (f"---\n{META.replace('https://dss.gov.bd/page', DOTS_URL)}---\n{BODY}", "source_url"),
        (f"---\n{META.replace('2026-11-21', '21/11/2026')}---\n{BODY}", "collected_on"),
        (f"---\n{META}---\n## যোগ্যতা\nছোট\n", "too short"),
        (f"---\n{META}---\n" + "শুধু লেখা কোনো শিরোনাম নেই। " * 10, "headings"),
        (f"---\n{META}---\n{BODY}\n## সময়\n...\n", "placeholders"),
    ],
)
def test_bad_documents_explain_what_is_wrong(tmp_path: Path, text: str, reason: str) -> None:
    with pytest.raises(DocumentError, match=reason):
        parse_document(write(tmp_path, text), "old_age_allowance")


def test_html_comments_are_not_counted_as_content(tmp_path: Path) -> None:
    text = f"---\n{META}---\n<!-- " + "নির্দেশনা " * 50 + "-->\n## ফি\nবিনামূল্যে।\n"
    with pytest.raises(DocumentError, match="too short"):
        parse_document(write(tmp_path, text), "old_age_allowance")


def test_document_paths_skip_underscore_files_and_loose_files(tmp_path: Path) -> None:
    write(tmp_path, "x", "old_age_allowance", "eligibility.md")
    write(tmp_path, "x", "old_age_allowance", "_draft.md")
    (tmp_path / "_TEMPLATE.md").write_text("x", encoding="utf-8")
    assert [(sid, p.name) for sid, p in document_paths(tmp_path)] == [("old_age_allowance", "eligibility.md")]


def test_the_shipped_template_is_skipped_and_fails_on_purpose() -> None:
    template = BACKEND_DIR / "data" / "raw_docs" / "_TEMPLATE.md"
    assert template.exists()
    with pytest.raises(DocumentError):  # placeholders must be replaced before use
        parse_document(template, "old_age_allowance")
