"""Retriever adapter: Chroma store + our own embedder (FR-AGT-05, FR-DATA-03).

The store is the Chroma server when `host` is given (docker-compose.yml), else the files in `path`.

search(): top-k passages for the chosen service. If fewer than `min_filtered` of them score at least
`min_score`, it also searches all services and merges, so a wrong router guess can still find the
right passage. score = 1 - cosine distance (vectors are normalised, so 1.0 = same direction).

Errors while searching (missing collection, broken store, model load failure) are logged and give an
empty list: the agent then says it has no answer, instead of the call crashing.
"""

import logging
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.application.ports.retrieval import Embedder, Passage
from app.domain import policies
from app.infrastructure.retrieval.chunker import Chunk

log = logging.getLogger(__name__)

COLLECTION = "ek_call_docs"
_ADD_BATCH = 64


class ChromaRetriever:
    def __init__(
        self,
        path: Path,
        embedder: Embedder,
        min_score: float = policies.RETRIEVAL_MIN_SCORE,
        min_filtered: int = policies.MIN_FILTERED_RESULTS,
        collection: str = COLLECTION,
        host: str = "",
        port: int = 8000,
    ) -> None:
        self._path = path
        self._host = host
        self._port = port
        self._embedder = embedder
        self._min_score = min_score
        self._min_filtered = min_filtered
        self._collection_name = collection
        self._client: Any = None
        self._lock = threading.Lock()

    # ---------------------------------------------------------------- store

    @property
    def client(self) -> Any:
        if self._client is None:
            with self._lock:
                if self._client is None:
                    import chromadb
                    from chromadb.config import Settings as ChromaSettings

                    settings = ChromaSettings(anonymized_telemetry=False)
                    if self._host:
                        self._client = chromadb.HttpClient(
                            host=self._host, port=self._port, settings=settings
                        )
                    else:
                        self._client = chromadb.PersistentClient(path=str(self._path), settings=settings)
        return self._client

    def _collection(self) -> Any:
        return self.client.get_collection(self._collection_name)

    def count(self) -> int:
        """Stored passages; 0 when the collection does not exist yet."""
        from chromadb.errors import NotFoundError

        try:
            return int(self._collection().count())
        except NotFoundError:
            return 0

    def rebuild(self, chunks: Sequence[Chunk]) -> int:
        """Replaces the whole collection with `chunks` (FR-DATA-03: re-running replaces it).

        The new index is built under a temporary name and swapped in at the end, so a server that
        is answering questions meanwhile keeps using the old index instead of finding nothing.
        """
        from chromadb.errors import NotFoundError

        building = f"{self._collection_name}_building"
        try:
            self.client.delete_collection(building)  # left over from a crashed run
        except NotFoundError:
            pass
        collection = self.client.create_collection(building, configuration={"hnsw": {"space": "cosine"}})
        for start in range(0, len(chunks), _ADD_BATCH):
            batch = list(chunks[start : start + _ADD_BATCH])
            collection.add(
                ids=[c.chunk_id for c in batch],
                embeddings=self._embedder.embed_passages([embedding_text(c) for c in batch]),
                documents=[c.text for c in batch],
                metadatas=[
                    {
                        "chunk_id": c.chunk_id,
                        "service_id": c.service_id,
                        "title": c.title,
                        "source_url": c.source_url,
                        "heading": c.heading,
                    }
                    for c in batch
                ],
            )
        try:
            self.client.delete_collection(self._collection_name)
        except NotFoundError:
            pass
        collection.modify(name=self._collection_name)  # the swap: a few milliseconds
        return int(self._collection().count())

    # ---------------------------------------------------------------- search (Retriever port)

    def search(self, query: str, service_id: str | None, k: int) -> list[Passage]:
        try:
            vector = self._embedder.embed_query(query)
            found = self._query(vector, service_id, k)
            if service_id is not None:
                good = [p for p in found if p.score >= self._min_score]
                if len(good) < self._min_filtered:
                    found = _merge(found, self._query(vector, None, k), k)
            return found
        except Exception:  # adapter boundary: never crash the caller, see module docstring
            log.exception("retrieval failed (service=%s)", service_id)
            return []

    def _query(self, vector: list[float], service_id: str | None, k: int) -> list[Passage]:
        result = self._collection().query(
            query_embeddings=[vector],
            n_results=k,
            where={"service_id": service_id} if service_id else None,
            include=["documents", "metadatas", "distances"],
        )
        passages = []
        for doc, meta, dist in zip(
            result["documents"][0], result["metadatas"][0], result["distances"][0], strict=True
        ):
            passages.append(
                Passage(
                    chunk_id=str(meta["chunk_id"]),
                    service_id=str(meta["service_id"]),
                    title=str(meta["title"]),
                    source_url=str(meta["source_url"]),
                    text=str(doc),
                    score=round(1.0 - float(dist), 4),
                )
            )
        return passages


def embedding_text(chunk: Chunk) -> str:
    """What gets embedded: the document title gives each passage its topic."""
    return f"{chunk.title}\n{chunk.text}"


def _merge(first: list[Passage], second: list[Passage], k: int) -> list[Passage]:
    best: dict[str, Passage] = {}
    for p in [*first, *second]:
        if p.chunk_id not in best or p.score > best[p.chunk_id].score:
            best[p.chunk_id] = p
    return sorted(best.values(), key=lambda p: p.score, reverse=True)[:k]
