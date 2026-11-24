"""Leak check of the augment script (sprint T1, FR-DATA-10): test lines never reach training data."""

import csv
from pathlib import Path

from scripts.augment_questions import check_leak, find_leaks, leak_key, protected_keys


def _write(path: Path, rows: list[tuple[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["text", "label"])
        writer.writerows(rows)


def test_leak_key_ignores_spaces_danda_and_question_mark() -> None:
    assert leak_key("  বয়স হয়ে গেছে,  কী করবো? ") == leak_key("বয়স হয়ে গেছে, কী করবো।")


def test_find_leaks_reports_the_source_file() -> None:
    protected = {leak_key("স্বামী নেই।"): "situation_test.csv"}
    rows = [{"text": "স্বামী নেই?", "label": "widow_allowance"}, {"text": "অন্য", "label": "other"}]
    assert find_leaks(rows, protected) == [("স্বামী নেই?", "situation_test.csv")]


def test_check_leak_fails_on_overlap_and_passes_when_clean(tmp_path: Path) -> None:
    _write(tmp_path / "situation_check.csv", [("দাদির বয়স আশি।", "old_age_allowance")])
    _write(tmp_path / "val_v2.csv", [("অন্য প্রশ্ন", "other")])
    _write(tmp_path / "train_v2.csv", [("দাদির বয়স আশি", "old_age_allowance")])
    assert set(protected_keys(tmp_path).values()) == {"situation_check.csv"}
    assert check_leak(tmp_path) == 1
    _write(tmp_path / "train_v2.csv", [("নতুন প্রশ্ন", "old_age_allowance")])
    assert check_leak(tmp_path) == 0


def test_check_leak_fails_when_v2_files_are_missing(tmp_path: Path) -> None:
    assert check_leak(tmp_path) == 1
