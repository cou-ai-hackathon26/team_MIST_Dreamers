"""LLM adapter for LLM_BACKEND=hybrid (FR-AGT-18).

FAST jobs (grading, rewriting, classification) go to the local model, so they cost no quota.
MAIN jobs (answer, verification) go to Gemini; if Gemini raises LLMUnavailable, the local model
answers instead, so a quota problem never ends the call.
"""

import logging
from collections.abc import Mapping
from typing import Any

from app.application.ports.llm import LLM, ModelRole
from app.domain.errors import LLMUnavailable

log = logging.getLogger(__name__)


class RoutedLLM:
    def __init__(self, main: LLM, local: LLM) -> None:
        self._main = main
        self._local = local

    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        role: ModelRole = ModelRole.MAIN,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        if role is ModelRole.FAST:
            return self._local.generate_json(prompt, schema, role, temperature)
        try:
            return self._main.generate_json(prompt, schema, role, temperature)
        except LLMUnavailable as exc:
            log.warning("main LLM unavailable (%s); using the local model", exc)
            return self._local.generate_json(prompt, schema, role, temperature)

    def generate_text(self, prompt: str, role: ModelRole = ModelRole.FAST) -> str:
        if role is ModelRole.FAST:
            return self._local.generate_text(prompt, role)
        try:
            return self._main.generate_text(prompt, role)
        except LLMUnavailable as exc:
            log.warning("main LLM unavailable (%s); using the local model", exc)
            return self._local.generate_text(prompt, role)

    def check(self) -> bool:
        """Usable when at least one side works (the local model can cover for Gemini)."""
        return self._local.check() or self._main.check()
