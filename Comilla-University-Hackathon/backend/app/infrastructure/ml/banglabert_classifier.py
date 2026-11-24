"""Fine-tuned BanglaBERT router (D2-T1, FR-AGT-01, FR-AGT-02, NFR-PERF-03).

Loads `ROUTER_MODEL_DIR` (made by `ml/train_router.py`: model, tokenizer, labels.json) once, on
first use. Text gets the same csebuetnlp normaliser as in training. CPU inference in
`torch.inference_mode()`, about 20 to 60 ms per question.
"""

import json
import logging
import threading
from pathlib import Path
from typing import Any

from app.domain.errors import ClassifierUnavailable
from app.domain.value_objects import RouterSource

log = logging.getLogger(__name__)

MAX_LENGTH = 64  # same as training


class BanglaBertClassifier:
    def __init__(self, model_dir: Path) -> None:
        self._dir = Path(model_dir)
        self._loaded: tuple[Any, Any, list[str], Any] | None = None  # model, tokenizer, labels, normalize
        self._lock = threading.Lock()

    @property
    def source(self) -> RouterSource:
        return RouterSource.BANGLABERT

    @property
    def available(self) -> bool:
        return (self._dir / "labels.json").exists() and (self._dir / "config.json").exists()

    def _load(self) -> tuple[Any, Any, list[str], Any]:
        if self._loaded is None:
            with self._lock:
                if self._loaded is None:
                    if not self.available:
                        raise ClassifierUnavailable(f"{self._dir.name}/ not found: run ml/train_router.py")
                    try:
                        from normalizer import normalize  # csebuetnlp BanglaBERT normaliser
                        from transformers import AutoModelForSequenceClassification, AutoTokenizer

                        labels = json.loads((self._dir / "labels.json").read_text(encoding="utf-8"))
                        tokenizer = AutoTokenizer.from_pretrained(self._dir)
                        model = AutoModelForSequenceClassification.from_pretrained(self._dir)
                        model.eval()
                    except Exception as exc:
                        log.exception("could not load the BanglaBERT router")
                        raise ClassifierUnavailable("the BanglaBERT router could not be loaded") from exc
                    self._loaded = (model, tokenizer, labels, normalize)
        return self._loaded

    def classify(self, text: str) -> list[tuple[str, float]]:
        import torch

        model, tokenizer, labels, normalize = self._load()
        inputs = tokenizer(normalize(text or ""), max_length=MAX_LENGTH, truncation=True, return_tensors="pt")
        with torch.inference_mode():
            probs = torch.softmax(model(**inputs).logits[0], dim=-1).tolist()
        pairs = [(str(label), float(p)) for label, p in zip(labels, probs, strict=True)]
        return sorted(pairs, key=lambda pair: pair[1], reverse=True)
