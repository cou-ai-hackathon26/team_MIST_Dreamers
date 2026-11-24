"""Reads official documents (data/raw_docs/<service_id>/*.md) and checks them (FR-DATA-02).

Used by scripts/check_docs.py now and by the ingest step (D1-T2) later.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import yaml

REQUIRED_FIELDS = ("title", "source_url", "office", "collected_on")
_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)


@dataclass(frozen=True)
class SourceDocument:
    service_id: str
    path: Path
    title: str
    source_url: str
    office: str
    collected_on: date
    body: str

    @property
    def word_count(self) -> int:
        return len(self.body.split())


class DocumentError(ValueError):
    """A document file is not usable; the message says why."""


def parse_document(path: Path, service_id: str) -> SourceDocument:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = _FRONT_MATTER.match(text)
    if not match:
        raise DocumentError("missing front matter (the file must start with --- ... ---)")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        raise DocumentError(f"front matter is not valid YAML: {exc}") from exc

    # `office:` with nothing after it is None in YAML, so check for None before str().
    missing = [f for f in REQUIRED_FIELDS if meta.get(f) is None or not str(meta[f]).strip()]
    if missing:
        raise DocumentError(f"front matter is missing {missing}")
    url = str(meta["source_url"]).strip()
    if not url.startswith(("http://", "https://")) or url.endswith("..."):
        raise DocumentError(f"source_url is not a real link: {url!r}")
    collected = meta["collected_on"]
    if not isinstance(collected, date):
        try:
            collected = date.fromisoformat(str(collected))
        except ValueError as exc:
            raise DocumentError(f"collected_on must be YYYY-MM-DD, got {collected!r}") from exc

    body = _COMMENT.sub("", match.group(2)).strip()
    if len(body.split()) < 20:
        raise DocumentError("body is empty or too short (paste the official text)")
    if not re.search(r"^## ", body, flags=re.MULTILINE):
        raise DocumentError("body has no '## ' headings (use যোগ্যতা, কাগজপত্র, ফি ...)")
    if re.search(r"^\.\.\.$", body, flags=re.MULTILINE):
        raise DocumentError("body still contains template '...' placeholders")

    return SourceDocument(
        service_id=service_id, path=path, title=str(meta["title"]).strip(), source_url=url,
        office=str(meta["office"]).strip(), collected_on=collected, body=body,
    )  # fmt: skip


def document_paths(raw_docs_dir: Path) -> list[tuple[str, Path]]:
    """(service_id, path) for every *.md in a service folder; files starting with '_' are skipped."""
    return [
        (path.parent.name, path)
        for path in sorted(raw_docs_dir.glob("*/*.md"))
        if not path.name.startswith("_")
    ]


def load_documents(raw_docs_dir: Path, service_ids: Iterable[str]) -> tuple[list[SourceDocument], list[str]]:
    """All valid documents, plus one problem line per file that is not usable."""
    known = set(service_ids)
    docs: list[SourceDocument] = []
    problems: list[str] = []
    for service_id, path in document_paths(raw_docs_dir):
        rel = path.relative_to(raw_docs_dir).as_posix()
        if service_id not in known:
            problems.append(f"{rel}: folder '{service_id}' is not a service id")
            continue
        try:
            docs.append(parse_document(path, service_id))
        except DocumentError as exc:
            problems.append(f"{rel}: {exc}")
    return docs, problems
