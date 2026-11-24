import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import BACKEND_DIR, Settings
from app.infrastructure.catalog.yaml_services import load_services
from app.main import create_app

SERVICES_FILE = BACKEND_DIR / "data" / "services.yaml"
SRS_PATH = Path(__file__).resolve().parents[3] / "docs" / "SRS.md"


def srs_labels() -> dict[str, str]:
    """{id: Bangla name} from the SRS 1.2 table."""
    section = SRS_PATH.read_text(encoding="utf-8").split("### 1.2", 1)[1].split("### 1.3", 1)[0]
    return dict(re.findall(r"^\| `(\w+)` \| [^|]+\| ([^|]+?) \|$", section, flags=re.MULTILINE))


def test_services_file_has_exactly_the_9_srs_labels_with_the_same_bangla_names() -> None:
    services = load_services(SERVICES_FILE)
    assert {s.id: s.name_bn for s in services} == srs_labels()
    assert len(services) == 9


def test_missing_field_is_reported(tmp_path: Path) -> None:
    bad = tmp_path / "services.yaml"
    bad.write_text("- id: x\n  name_bn: ক\n  name_en: X\n  office_bn: অফিস\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sms_name"):
        load_services(bad)


def test_empty_field_is_reported_not_read_as_none(tmp_path: Path) -> None:
    bad = tmp_path / "services.yaml"
    bad.write_text("- id: x\n  name_bn: ক\n  name_en: X\n  office_bn: অফিস\n  sms_name:\n", encoding="utf-8")
    with pytest.raises(ValueError, match="sms_name"):
        load_services(bad)


def test_duplicate_ids_are_reported(tmp_path: Path) -> None:
    entry = "- id: x\n  name_bn: ক\n  name_en: X\n  office_bn: অফিস\n  sms_name: ক\n"
    bad = tmp_path / "services.yaml"
    bad.write_text(entry * 2, encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_services(bad)


def test_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_services(tmp_path / "nope.yaml")


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(_env_file=None, database_url="sqlite://"))) as c:
        yield c


def test_services_endpoint_lists_all_9_in_bangla(client: TestClient) -> None:
    r = client.get("/api/v1/services")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 9
    old_age = next(s for s in body if s["id"] == "old_age_allowance")
    assert old_age == {
        "id": "old_age_allowance", "name_bn": "বয়স্ক ভাতা", "name_en": "Old Age Allowance",
        "office_bn": "উপজেলা সমাজসেবা অফিস", "sms_name": "বয়স্ক ভাতা",
    }  # fmt: skip
