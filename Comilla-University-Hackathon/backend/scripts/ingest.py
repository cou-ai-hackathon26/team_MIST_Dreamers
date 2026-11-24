"""Builds the search index from the official documents (FR-DATA-03).

Run from backend/:   python -m scripts.ingest
- reads data/raw_docs/<service_id>/*.md (files that fail check_docs are skipped and listed),
- cuts them into passages, embeds them with e5 ("passage: " prefix),
- replaces the Chroma collection and prints passages per service,
- clears the answer cache, because cached answers came from the old documents (FR-AGT-15).
Exit code 1 if a service ends up with no passages at all.
"""

import logging
import sys
from collections import Counter

from sqlalchemy import delete

from app.config import BACKEND_DIR, get_settings
from app.container import Container
from app.infrastructure.db.models import AnswerCacheRow
from app.infrastructure.retrieval.chroma_retriever import embedding_text
from app.infrastructure.retrieval.chunker import chunk_documents
from app.infrastructure.retrieval.documents import load_documents

RAW_DOCS = BACKEND_DIR / "data" / "raw_docs"


def clear_answer_cache(container: Container) -> int:
    """Old cached answers must not outlive the documents they were written from."""
    container.init_database()
    with container.session_factory() as session:
        removed = session.execute(delete(AnswerCacheRow)).rowcount
        session.commit()
    return int(removed or 0)


def main() -> int:
    logging.basicConfig(level=logging.WARNING)
    container = Container(get_settings())
    service_ids = [s.id for s in container.services if s.id != "other"]

    docs, problems = load_documents(RAW_DOCS, service_ids)
    chunks = chunk_documents(docs)
    print(f"{len(docs)} documents -> {len(chunks)} passages. Embedding (first run loads the model)...")

    stored = container.retriever.rebuild(chunks)

    per_service = Counter(c.service_id for c in chunks)
    print(f"\n{'service':22} {'passages':>8}")
    for sid in service_ids:
        print(f"{sid:22} {per_service.get(sid, 0):>8}")
    cfg = container.settings
    where = f"Chroma server {cfg.chroma_host}:{cfg.chroma_port}" if cfg.chroma_host else cfg.chroma_dir
    print(f"{'total stored':22} {stored:>8}   (in {where})")
    print(f"answer cache cleared: {clear_answer_cache(container)} old answers removed")

    embedder = container.embedder
    too_long = [c.chunk_id for c in chunks if embedder.token_count(embedding_text(c)) > embedder.max_tokens]
    if too_long:
        print(f"\nWARNING: {len(too_long)} passage(s) are longer than the model reads: {', '.join(too_long)}")
    if problems:
        print("\nSkipped (fix with python -m scripts.check_docs):")
        for p in problems:
            print("  -", p)

    empty = [sid for sid in service_ids if not per_service.get(sid)]
    if empty:
        print(f"\nNo passages for: {', '.join(empty)}")
    return 1 if empty else 0


if __name__ == "__main__":
    sys.exit(main())
