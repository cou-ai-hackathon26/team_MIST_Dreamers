"""Router that asks the LLM (ROUTER_BACKEND=llm, FR-AGT-02). Slower and uses quota; no model file needed.

It reuses the agent's `llm_classify` prompt. The chosen label gets the LLM's confidence and the
rest share what is left, so the result has the same shape as the local routers.
"""

from collections.abc import Mapping

from app.application.agent import prompts
from app.application.ports.llm import LLM, ModelRole
from app.domain.entities import Service
from app.domain.value_objects import RouterSource

OTHER = "other"


class LLMClassifier:
    def __init__(self, llm: LLM, services: Mapping[str, Service]) -> None:
        self._llm = llm
        self._services = dict(services)

    @property
    def source(self) -> RouterSource:
        return RouterSource.LLM

    def classify(self, text: str) -> list[tuple[str, float]]:
        labels = list(self._services)
        data = self._llm.generate_json(
            prompts.build_classify_prompt(text, self._services),
            prompts.classify_schema(labels),
            role=ModelRole.FAST,
            temperature=0.0,
        )
        chosen = data.get("service_id") if data.get("service_id") in self._services else OTHER
        try:
            confidence = min(1.0, max(0.0, float(data.get("confidence", 0.0))))
        except (TypeError, ValueError):
            confidence = 0.0
        rest = (1.0 - confidence) / max(1, len(labels) - 1)
        scores = [(label, confidence if label == chosen else rest) for label in labels]
        return sorted(scores, key=lambda pair: pair[1], reverse=True)
