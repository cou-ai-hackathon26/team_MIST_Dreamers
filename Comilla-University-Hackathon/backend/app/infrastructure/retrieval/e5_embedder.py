"""Embedder adapter: intfloat/multilingual-e5-small via sentence-transformers (FR-AGT-05, FR-DATA-03).

e5 was trained with prefixes: questions get "query: ", stored text gets "passage: ".
Vectors are normalised, so cosine similarity = dot product.
The model (about 470 MB) is loaded on first use, not at import, and kept in `cache_dir`
(backend/data/models/e5, git-ignored). After the first download it works offline.
"""

import logging
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

QUERY_PREFIX = "query: "
PASSAGE_PREFIX = "passage: "


class E5Embedder:
    def __init__(self, model_name: str, cache_dir: Path, batch_size: int = 16) -> None:
        self._model_name = model_name
        self._cache_dir = cache_dir
        self._batch_size = batch_size
        self._model: Any = None
        self._lock = threading.Lock()

    @property
    def model(self) -> Any:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    from sentence_transformers import SentenceTransformer  # heavy import, only when needed

                    log.info("loading embedding model %s", self._model_name)
                    self._model = SentenceTransformer(self._model_name, cache_folder=str(self._cache_dir))
        return self._model

    @property
    def max_tokens(self) -> int:
        return int(self.model.max_seq_length)

    def token_count(self, text: str, prefix: str = PASSAGE_PREFIX) -> int:
        """Tokens the model sees for `text` (anything above `max_tokens` is cut off)."""
        return len(self.model.tokenizer(prefix + text)["input_ids"])

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(
            texts, batch_size=self._batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        return [[float(x) for x in row] for row in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self._encode([QUERY_PREFIX + text])[0]

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._encode([PASSAGE_PREFIX + t for t in texts])
