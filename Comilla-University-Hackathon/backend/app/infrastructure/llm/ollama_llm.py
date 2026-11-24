"""LLM adapter: a local model served by Ollama (FR-AGT-18, C-06).

POST {OLLAMA_URL}/api/chat with stream=false. For JSON, our JSON schema goes in `format`, so Ollama
forces the reply into that shape. `keep_alive` keeps the model in memory between calls (the first
call loads it, about 10 s). Connection errors, timeouts and bad replies raise LLMUnavailable.
Ollama runs one model, so `role` is ignored.
"""

import logging
import time
from collections.abc import Mapping
from typing import Any

import httpx

from app.application.ports.llm import ModelRole
from app.domain.errors import LLMUnavailable
from app.infrastructure.llm.common import LLMStats, parse_json_object

log = logging.getLogger(__name__)


class OllamaLLM:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_s: float = 60.0,
        keep_alive: str = "30m",
        client: httpx.Client | None = None,
    ) -> None:
        self._model = model
        self._keep_alive = keep_alive
        self._http = client or httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout_s)
        self.stats = LLMStats()

    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        role: ModelRole = ModelRole.MAIN,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        return parse_json_object(self._chat(prompt, temperature, dict(schema) or "json"))

    def generate_text(self, prompt: str, role: ModelRole = ModelRole.FAST) -> str:
        return self._chat(prompt, 0.2, None).strip()

    def check(self) -> bool:
        """True when Ollama answers and has OLLAMA_MODEL downloaded (no generation)."""
        try:
            response = self._http.get("/api/tags", timeout=3.0)
            response.raise_for_status()
            names = {m.get("name") for m in response.json().get("models", [])}
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("Ollama check failed: %s", type(exc).__name__)
            return False
        return self._model in names or f"{self._model}:latest" in names

    def _chat(self, prompt: str, temperature: float, fmt: dict[str, Any] | str | None) -> str:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "keep_alive": self._keep_alive,
            "options": {"temperature": temperature},
        }
        if fmt is not None:
            body["format"] = fmt
        started = time.perf_counter()
        try:
            response = self._http.post("/api/chat", json=body)
            response.raise_for_status()
            content = response.json()["message"]["content"]
        except httpx.HTTPStatusError as exc:
            self.stats.record(time.perf_counter() - started, ok=False)
            raise LLMUnavailable(f"Ollama returned HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
            self.stats.record(time.perf_counter() - started, ok=False)
            raise LLMUnavailable(f"Ollama is not reachable or replied badly ({type(exc).__name__})") from exc
        elapsed = time.perf_counter() - started
        self.stats.record(elapsed, ok=True)
        log.info("ollama call %.2fs", elapsed)
        return str(content)

    def close(self) -> None:
        self._http.close()
