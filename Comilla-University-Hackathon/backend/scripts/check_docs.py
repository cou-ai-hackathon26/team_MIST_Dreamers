"""Checks the official documents before ingest (FR-DATA-02).

Run from backend/:   python -m scripts.check_docs
Exit code 0 = every service has at least one valid document.
"""

import sys
from collections import defaultdict

from app.config import BACKEND_DIR, get_settings
from app.infrastructure.catalog.yaml_services import load_services
from app.infrastructure.retrieval.documents import SourceDocument, load_documents

RAW_DOCS = BACKEND_DIR / "data" / "raw_docs"


def main() -> int:
    service_ids = [s.id for s in load_services(get_settings().services_file) if s.id != "other"]
    docs, problems = load_documents(RAW_DOCS, service_ids)
    good: dict[str, list[SourceDocument]] = defaultdict(list)
    for doc in docs:
        good[doc.service_id].append(doc)

    print(f"{'service':24} {'docs':>4} {'words':>6}")
    for sid in service_ids:
        docs = good.get(sid, [])
        mark = "OK  " if docs else "NONE"
        print(f"{mark} {sid:19} {len(docs):>4} {sum(d.word_count for d in docs):>6}")
    if problems:
        print("\nProblems:")
        for p in problems:
            print("  -", p)

    missing = [sid for sid in service_ids if not good.get(sid)]
    if missing:
        print(f"\n{len(missing)} service(s) still need a document: {', '.join(missing)}")
    ok = not problems and not missing
    print("\nRESULT:", "all good" if ok else "not ready yet")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
