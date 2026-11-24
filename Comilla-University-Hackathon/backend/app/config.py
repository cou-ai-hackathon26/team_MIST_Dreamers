"""All settings, read from environment variables or backend/.env (SRS Section 9, NFR-SEC-01).

Defaults let the app start offline with no keys: TF-IDF router, console SMS, SQLite.
Secrets are SecretStr, so they never appear in logs or error messages by accident.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain import policies

BACKEND_DIR = Path(__file__).resolve().parents[1]


def _split(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- app
    app_env: Literal["dev", "demo"] = "dev"
    public_url: str = "http://localhost:8000"
    frontend_origins: str = "http://localhost:5173"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'ekcall.db').as_posix()}"

    # --- LLM (FR-AGT-16, FR-AGT-18)
    llm_backend: Literal["gemini", "ollama", "hybrid"] = "gemini"
    gemini_api_keys: SecretStr = SecretStr("")
    gemini_model_main: str = ""
    gemini_model_fast: str = ""
    gemini_model_fallback: str = ""  # tried once when the model is overloaded (503) or out of quota
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    # --- router + retrieval (FR-AGT-02, 03, 05)
    router_backend: Literal["tfidf", "banglabert", "llm"] = "tfidf"
    router_model_dir: Path = BACKEND_DIR / "data" / "models" / "router"
    tfidf_model_path: Path = BACKEND_DIR / "data" / "models" / "tfidf_router.joblib"
    router_confidence_threshold: float = Field(policies.ROUTER_CONFIDENCE_THRESHOLD, gt=0, lt=1)
    retrieval_min_score: float = Field(policies.RETRIEVAL_MIN_SCORE, gt=0, lt=1)
    embed_model: str = "intfloat/multilingual-e5-small"
    embed_cache_dir: Path = BACKEND_DIR / "data" / "models" / "e5"
    chroma_dir: Path = BACKEND_DIR / "data" / "chroma"
    chroma_host: str = ""  # set (e.g. localhost) to use the Chroma server instead of chroma_dir
    chroma_port: int = 8001
    services_file: Path = BACKEND_DIR / "data" / "services.yaml"
    voice_fast_mode: bool = True
    agent_engine: Literal["langgraph", "stub"] = "langgraph"  # stub: fixed answer, no keys needed
    preload_models: bool = False  # True in .env.example: load models in the background at startup
    # Situations and mixed questions (FR-AGT-19 to 22). SITUATION_MODE=false restores the old flow.
    situation_mode: bool = policies.SITUATION_MODE
    multi_service_min_prob: float = Field(policies.MULTI_SERVICE_MIN_PROB, gt=0, lt=1)
    max_services_per_question: int = Field(policies.MAX_SERVICES_PER_QUESTION, ge=1, le=2)
    query_expansion: bool = policies.QUERY_EXPANSION
    max_speech_words_multi: int = Field(policies.MAX_SPEECH_WORDS_MULTI, ge=20, le=120)
    # Second, cheap router trained with situations; missing file = off (tuning: situation_eval.md)
    situation_hint_model_path: Path = BACKEND_DIR / "data" / "models" / "tfidf_router_v2.joblib"
    situation_hint_min_confidence: float = Field(policies.HINT_MIN_CONFIDENCE, ge=0, lt=1)

    # --- Twilio (FR-CALL)
    twilio_account_sid: str = ""
    twilio_auth_token: SecretStr = SecretStr("")
    twilio_number: str = ""
    stt_language: str = "bn-BD"
    tts_voice: str = "Google.bn-IN-Standard-A"
    tts_language: str = "bn-IN"
    missed_call_mode: bool = False
    validate_twilio_signature: bool = False

    # --- SMS (FR-SMS-03)
    sms_backend: Literal["console", "textbee"] = "console"
    textbee_api_key: SecretStr = SecretStr("")
    textbee_device_id: str = ""

    # --- security + privacy (FR-ADM-05, NFR-PRIV-01)
    admin_token: SecretStr = SecretStr("")
    admin_session_hours: float = Field(default=8, gt=0, le=72)  # how long an admin login lasts
    phone_hash_salt: SecretStr = SecretStr("")

    # ------------------------------------------------------------ derived values

    @property
    def frontend_origin_list(self) -> list[str]:
        return _split(self.frontend_origins)

    @property
    def gemini_key_list(self) -> list[str]:
        return _split(self.gemini_api_keys.get_secret_value())

    def config_warnings(self) -> list[str]:
        """Problems worth logging at startup. The app still starts; the affected feature fails politely."""
        warnings: list[str] = []
        if self.llm_backend in ("gemini", "hybrid"):
            if not self.gemini_key_list:
                warnings.append(f"LLM_BACKEND={self.llm_backend} but GEMINI_API_KEYS is empty")
            if not (self.gemini_model_main and self.gemini_model_fast):
                warnings.append("GEMINI_MODEL_MAIN / GEMINI_MODEL_FAST are not set")
        if self.sms_backend == "textbee" and not (
            self.textbee_api_key.get_secret_value() and self.textbee_device_id
        ):
            warnings.append("SMS_BACKEND=textbee but TEXTBEE_API_KEY / TEXTBEE_DEVICE_ID are missing")
        if not self.phone_hash_salt.get_secret_value():
            warnings.append("PHONE_HASH_SALT is empty: phone hashes in question_logs are weak")
        if self.app_env == "demo":
            if not self.admin_token.get_secret_value():
                warnings.append("APP_ENV=demo but ADMIN_TOKEN is empty: the admin dashboard is closed (503)")
            if not self.validate_twilio_signature:
                warnings.append("APP_ENV=demo but VALIDATE_TWILIO_SIGNATURE=false")
        return warnings


@lru_cache
def get_settings() -> Settings:
    """The one Settings object for the running app (read once)."""
    return Settings()
