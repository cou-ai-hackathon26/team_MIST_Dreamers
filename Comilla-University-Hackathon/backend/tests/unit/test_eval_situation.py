"""Metric functions of scripts/eval_situation.py on tiny data (sprint E1)."""

import pytest

from scripts.eval_situation import MixedResult, accuracy, gate, macro_f1, mixed_summary, pct, rate


def test_accuracy() -> None:
    assert accuracy(["a", "b", "a", "c"], ["a", "b", "c", "c"]) == 0.75
    assert accuracy([], []) == 0.0


def test_macro_f1_by_hand() -> None:
    gold = ["a", "a", "b", "b"]
    predicted = ["a", "b", "b", "b"]
    # a: tp 1, fp 0, fn 1 -> 2/3; b: tp 2, fp 1, fn 0 -> 4/5
    assert macro_f1(gold, predicted) == pytest.approx((2 / 3 + 4 / 5) / 2)
    assert macro_f1(["a"], ["b"]) == 0.0  # a label never predicted scores 0
    assert macro_f1(["a", "b"], ["a", "b"]) == 1.0


def test_rate_and_pct() -> None:
    assert rate([True, False, True, True]) == 0.75
    assert rate([]) is None and pct(None) == "n/a" and pct(0.5) == "50.0%"


def result(found: tuple[str, ...], expects: bool, conflicts: int, dropped: int = 0) -> MixedResult:
    return MixedResult(("a", "b"), found, expects, conflicts, dropped, answered=bool(found))


def test_mixed_summary() -> None:
    summary = mixed_summary(
        [
            result(("a", "b"), expects=True, conflicts=1),
            result(("a",), expects=True, conflicts=0, dropped=2),
            result(("c",), expects=False, conflicts=1),
            result((), expects=False, conflicts=0),
        ]
    )
    assert summary["both"] == 0.25
    assert summary["one"] == 0.5
    assert summary["guard_pass"] == 0.75
    assert summary["conflict_when_yes"] == 0.5
    assert summary["fake_conflict_when_no"] == 0.5
    assert summary["answered"] == 0.75


@pytest.mark.parametrize(
    ("v1_test", "v2_test", "v1_sit", "v2_sit", "switch"),
    [
        (0.935, 0.930, 0.50, 0.70, True),  # 0.5 point drop allowed, better on situations
        (0.935, 0.920, 0.50, 0.70, False),  # 1.5 points worse on test.csv
        (0.935, 0.950, 0.70, 0.70, False),  # not better on situations
    ],
)
def test_model_gate(v1_test: float, v2_test: float, v1_sit: float, v2_sit: float, switch: bool) -> None:
    assert gate(v1_test, v2_test, v1_sit, v2_sit) is switch
