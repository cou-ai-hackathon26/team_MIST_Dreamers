"""The retrained router keeps v1's labels in the same order (sprint T1B), so services.yaml ids match.

Skips when data/models/router_v2 is missing (it is git-ignored and only exists after training).
"""

import json
from pathlib import Path

import pytest

MODELS = Path(__file__).resolve().parents[2] / "data" / "models"


def _labels(folder: str) -> list[str]:
    return json.loads((MODELS / folder / "labels.json").read_text(encoding="utf-8"))


@pytest.mark.skipif(not (MODELS / "router_v2" / "labels.json").exists(), reason="router_v2 not trained here")
def test_v2_labels_equal_v1_labels_in_the_same_order() -> None:
    assert (MODELS / "router" / "labels.json").exists()
    assert _labels("router_v2") == _labels("router")
