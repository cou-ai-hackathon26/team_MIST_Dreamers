"""`python -m scripts.ingest` while the server is running must not break the server's search.

The rebuild runs in another process (like the ingest script beside uvicorn). Afterwards the
server's retriever still holds the old index and Chroma says "Nothing found on disk": the
retriever must reopen the index and answer.
"""

import subprocess
import sys
import textwrap
from pathlib import Path

from app.infrastructure.retrieval.chroma_retriever import ChromaRetriever
from tests.integration.test_chroma_retriever import WordEmbedder, chunk

BACKEND = Path(__file__).resolve().parents[2]
CHUNKS = [
    chunk("old_age_allowance-001", "old_age_allowance", "বয়স্ক ভাতা পেতে বয়স ৬৫ বছর লাগে"),
    chunk("old_age_allowance-002", "old_age_allowance", "বয়স্ক ভাতার আবেদন অনলাইনে করা যায়"),
]

REBUILD = textwrap.dedent(
    """
    import sys
    from app.infrastructure.retrieval.chroma_retriever import ChromaRetriever
    from tests.integration.test_chroma_retriever import WordEmbedder
    from tests.integration.test_chroma_reingest_while_running import CHUNKS
    ChromaRetriever(sys.argv[1], WordEmbedder(), min_score=0.0).rebuild(CHUNKS)
    """
)


def rebuild_in_another_process(path: Path) -> None:
    subprocess.run([sys.executable, "-c", REBUILD, str(path)], cwd=BACKEND, check=True, timeout=120)


def test_rebuild_builds_aside_and_swaps_so_the_old_index_answers_until_the_end(tmp_path: Path) -> None:
    store = ChromaRetriever(tmp_path, WordEmbedder(), min_score=0.0)
    store.rebuild(CHUNKS)
    seen_during_build: list[int] = []
    real_embed = store._embedder.embed_passages

    def embed_and_look(texts):  # type: ignore[no-untyped-def]
        seen_during_build.append(len(store.search("বয়স্ক ভাতা", "old_age_allowance", 2)))
        return real_embed(texts)

    store._embedder.embed_passages = embed_and_look  # type: ignore[method-assign]
    assert store.rebuild(CHUNKS[:1]) == 1
    assert seen_during_build and all(n > 0 for n in seen_during_build)  # never empty mid-rebuild
    names = [c.name for c in store.client.list_collections()]
    assert names == ["ek_call_docs"]  # the temporary collection is gone


def test_search_keeps_working_after_the_index_is_rebuilt_by_another_process(tmp_path: Path) -> None:
    server = ChromaRetriever(tmp_path, WordEmbedder(), min_score=0.0)
    server.rebuild(CHUNKS)
    assert server.search("বয়স্ক ভাতা বয়স", "old_age_allowance", 2)

    rebuild_in_another_process(tmp_path)  # the ingest script, while the server keeps running

    found = server.search("বয়স্ক ভাতা বয়স", "old_age_allowance", 2)
    assert [p.chunk_id for p in found][:1] == ["old_age_allowance-001"]
