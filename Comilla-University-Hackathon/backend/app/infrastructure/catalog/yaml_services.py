"""Loads data/services.yaml into Service entities (FR-DATA-01)."""

from pathlib import Path

import yaml

from app.domain.entities import Service

_FIELDS = ("id", "name_bn", "name_en", "office_bn", "sms_name")


def load_services(path: Path) -> list[Service]:
    """Reads and checks the file: every field present and non-empty, ids unique."""
    if not path.exists():
        raise FileNotFoundError(f"services file not found: {path}")
    entries = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    services: list[Service] = []
    for i, entry in enumerate(entries):
        # `sms_name:` with nothing after it is None in YAML, so check for None before str().
        missing = [f for f in _FIELDS if entry.get(f) is None or not str(entry[f]).strip()]
        if missing:
            raise ValueError(f"{path.name} entry {i}: missing {missing}")
        terms = str(entry.get("search_terms_bn") or "").strip()  # optional (FR-AGT-20)
        services.append(Service(**{f: str(entry[f]).strip() for f in _FIELDS}, search_terms_bn=terms))
    ids = [s.id for s in services]
    duplicates = {x for x in ids if ids.count(x) > 1}
    if duplicates:
        raise ValueError(f"{path.name}: duplicate ids {sorted(duplicates)}")
    return services
