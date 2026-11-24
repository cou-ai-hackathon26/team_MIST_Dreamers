"""Smoke test for the LLM adapters (D1-T3 done-check).

Run from backend/:
    python -m scripts.llm_smoke                      # uses LLM_BACKEND from .env
    python -m scripts.llm_smoke --backend ollama
    python -m scripts.llm_smoke --backend hybrid
    python -m scripts.llm_smoke --backend gemini --bad-first-key   # proves key rotation
Asks for a small JSON object in Bangla and checks the shape and the Bangla digits (NFR-USE-01).
"""

import argparse
import logging
import re
import sys
import time

from pydantic import SecretStr

from app.application.ports.llm import ModelRole
from app.config import Settings
from app.container import Container
from app.domain.errors import LLMUnavailable

PROMPT = """তুমি বাংলাদেশের সরকারি সেবা বিষয়ক সহকারী। নিচের তথ্য থেকে উত্তর দাও।
তথ্য: বয়স্ক ভাতা পেতে পুরুষের বয়স সর্বনিম্ন 65 বছর এবং মহিলাদের সর্বনিম্ন 62 বছর হতে হবে।
প্রশ্ন: আমার বয়স 67, আমি কি বয়স্ক ভাতা পাব?
নিয়ম: speech_text সহজ বাংলায় এক বা দুই বাক্যে লেখো। সব সংখ্যা বাংলা অঙ্কে লেখো (যেমন ৬৫, 65 নয়)।
শুধু JSON দাও।"""

SCHEMA = {
    "type": "object",
    "properties": {
        "service_id": {"type": "string", "enum": ["old_age_allowance", "other"]},
        "eligible": {"type": "boolean"},
        "speech_text": {"type": "string"},
    },
    "required": ["service_id", "eligible", "speech_text"],
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["gemini", "ollama", "hybrid"], default=None)
    parser.add_argument("--bad-first-key", action="store_true", help="put an invalid key first")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    for noisy in ("httpx", "google_genai", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    overrides: dict[str, object] = {}
    if args.backend:
        overrides["llm_backend"] = args.backend
    settings = Settings(**overrides)  # type: ignore[arg-type]
    if args.bad_first_key:
        keys = ",".join(["this-is-not-a-valid-key", *settings.gemini_key_list])
        settings = Settings(**overrides, gemini_api_keys=SecretStr(keys))  # type: ignore[arg-type]

    container = Container(settings)
    print(f"LLM_BACKEND = {settings.llm_backend}")
    print(f"health llm  = {container.check_llm()}")

    ok = True
    for role in (ModelRole.FAST, ModelRole.MAIN):
        started = time.perf_counter()
        try:
            result = container.llm.generate_json(PROMPT, SCHEMA, role=role, temperature=0.1)
        except LLMUnavailable as exc:
            print(f"\n[{role.value}] FAILED: {exc}")
            ok = False
            continue
        elapsed = time.perf_counter() - started
        speech = str(result.get("speech_text", ""))
        has_fields = set(SCHEMA["required"]) <= result.keys()
        shape_ok = has_fields and result.get("service_id") == "old_age_allowance"
        latin_digits = re.findall(r"[0-9]", speech)
        print(f"\n[{role.value}] {elapsed:.1f}s  {result}")
        print(f"  shape ok: {shape_ok}   Bangla digits only in speech_text: {not latin_digits}")
        ok = ok and shape_ok
    container.close()
    print("\nRESULT:", "OK" if ok else "FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
