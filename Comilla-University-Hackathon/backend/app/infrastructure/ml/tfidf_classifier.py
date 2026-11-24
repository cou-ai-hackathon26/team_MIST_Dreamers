"""TF-IDF + logistic regression router (D1-R4, FR-AGT-01, FR-AGT-02, FR-DATA-06).

Loads `data/models/tfidf_router.joblib` (made by `python -m scripts.train_baseline`) on first use.
"""

import logging
import threading
from pathlib import Path
from typing import Any

from app.domain.errors import ClassifierUnavailable
from app.domain.value_objects import RouterSource

log = logging.getLogger(__name__)


class TfidfClassifier:
    def __init__(self, model_path: Path) -> None:
        self._path = Path(model_path)
        self._pipeline: Any = None
        self._lock = threading.Lock()

    @property
    def source(self) -> RouterSource:
        return RouterSource.TFIDF

    @property
    def available(self) -> bool:
        return self._path.exists()

    def _load(self) -> Any:
        if self._pipeline is None:
            with self._lock:
                if self._pipeline is None:
                    if not self._path.exists():
                        raise ClassifierUnavailable(
                            f"{self._path.name} not found: run python -m scripts.train_baseline"
                        )
                    import joblib  # heavy import, only when the router is really used

                    try:
                        self._pipeline = joblib.load(self._path)["pipeline"]
                    except Exception as exc:
                        log.exception("could not load the TF-IDF router")
                        raise ClassifierUnavailable("the TF-IDF router file is broken") from exc
        return self._pipeline

    def classify(self, text: str) -> list[tuple[str, float]]:
        pipeline = self._load()
        probs = pipeline.predict_proba([text])[0]
        pairs = [(str(label), float(p)) for label, p in zip(pipeline.classes_, probs, strict=True)]
        return sorted(pairs, key=lambda pair: pair[1], reverse=True)
