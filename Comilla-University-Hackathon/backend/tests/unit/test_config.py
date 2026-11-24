import re

import pytest
from pydantic import ValidationError

from app.config import BACKEND_DIR, Settings


def make(**overrides) -> Settings:
    """Settings that ignore the developer's real .env and environment."""
    return Settings(_env_file=None, **overrides)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove any real env vars that would leak into the tests."""
    for name in list(Settings.model_fields):
        monkeypatch.delenv(name.upper(), raising=False)


def test_defaults_work_offline() -> None:
    s = make()
    assert s.router_backend == "tfidf"
    assert s.sms_backend == "console"
    assert s.database_url.startswith("sqlite:///")
    assert s.router_confidence_threshold == 0.7
    assert s.frontend_origin_list == ["http://localhost:5173"]


def test_comma_separated_lists_are_split_and_trimmed() -> None:
    s = make(gemini_api_keys="k1, k2 ,,k3", frontend_origins="http://a , http://b")
    assert s.gemini_key_list == ["k1", "k2", "k3"]
    assert s.frontend_origin_list == ["http://a", "http://b"]


@pytest.mark.parametrize(
    ("field", "bad"),
    [("llm_backend", "openai"), ("router_backend", "bert"), ("sms_backend", "email"), ("app_env", "prod")],
)
def test_unknown_choices_are_rejected(field: str, bad: str) -> None:
    with pytest.raises(ValidationError):
        make(**{field: bad})


@pytest.mark.parametrize("bad", [0, 1, 1.5, -0.2])
def test_thresholds_must_be_between_0_and_1(bad: float) -> None:
    with pytest.raises(ValidationError):
        make(router_confidence_threshold=bad)
    with pytest.raises(ValidationError):
        make(retrieval_min_score=bad)


def test_secrets_are_hidden_in_repr() -> None:
    s = make(twilio_auth_token="super-secret-token", gemini_api_keys="AIza-secret")
    text = repr(s) + str(s)
    assert "super-secret-token" not in text and "AIza-secret" not in text


def test_warnings_for_missing_keys() -> None:
    warnings = make(llm_backend="gemini").config_warnings()
    assert any("GEMINI_API_KEYS" in w for w in warnings)
    assert any("PHONE_HASH_SALT" in w for w in warnings)


def test_ollama_backend_needs_no_gemini_key() -> None:
    warnings = make(llm_backend="ollama", phone_hash_salt="x").config_warnings()
    assert warnings == []


def test_demo_mode_warns_about_open_admin_and_signature_check() -> None:
    warnings = make(app_env="demo", llm_backend="ollama", phone_hash_salt="x").config_warnings()
    assert any("ADMIN_TOKEN" in w for w in warnings)
    assert any("VALIDATE_TWILIO_SIGNATURE" in w for w in warnings)


def test_env_example_is_a_valid_env_file() -> None:
    s = Settings(_env_file=BACKEND_DIR / ".env.example")
    assert s.llm_backend == "gemini"
    assert s.gemini_key_list == []  # inline comment is not read as a key
    assert s.stt_language == "bn-BD"
    assert s.validate_twilio_signature is False


def test_env_example_lists_every_setting() -> None:
    text = (BACKEND_DIR / ".env.example").read_text(encoding="utf-8")
    documented = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]+)=", text, flags=re.MULTILINE))
    # Paths with good defaults may stay undocumented.
    optional = {"ROUTER_MODEL_DIR", "TFIDF_MODEL_PATH", "CHROMA_DIR", "EMBED_CACHE_DIR", "SERVICES_FILE"}
    missing = {name.upper() for name in Settings.model_fields} - documented - optional
    assert not missing, f".env.example is missing: {sorted(missing)}"
