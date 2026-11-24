"""Composition root (AR-05): the ONLY place that builds adapters and hands them to use cases.

Everything is built lazily on first use and then reused, so a missing model or service only
breaks the feature that needs it, not the whole app. Later steps add adapters and use cases here.
"""

import logging
import threading
import time
from collections.abc import Callable
from functools import cached_property

from sqlalchemy import Engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.application.agent.steps import AgentDeps
from app.application.ports.background import BackgroundRunner
from app.application.ports.classifier import ServiceClassifier
from app.application.ports.clustering import Clusterer
from app.application.ports.engine import AnswerEngine
from app.application.ports.llm import LLM
from app.application.ports.messaging import SmsSender
from app.application.ports.repositories import (
    AnswerCache,
    CallRepo,
    ChecklistRepo,
    ClusterRepo,
    ConversationRepo,
    QuestionLogRepo,
)
from app.application.use_cases.admin import GetAdminStats, ListQuestions
from app.application.use_cases.admin_auth import AdminAuth
from app.application.use_cases.ask_question import AskQuestion
from app.application.use_cases.clusters import ListClusters, RebuildClusters
from app.application.use_cases.history import DeleteHistory, GetHistory
from app.application.use_cases.services import ListServices
from app.config import Settings
from app.domain.entities import Service
from app.infrastructure.agent.langgraph_engine import LangGraphAnswerEngine
from app.infrastructure.agent.stub_engine import StubAnswerEngine
from app.infrastructure.background.thread_runner import ThreadPoolRunner
from app.infrastructure.cache.answer_cache import SqlAnswerCache
from app.infrastructure.catalog.yaml_services import load_services
from app.infrastructure.db.repositories import (
    SqlCallRepo,
    SqlChecklistRepo,
    SqlClusterRepo,
    SqlConversationRepo,
    SqlQuestionLogRepo,
)
from app.infrastructure.db.session import init_db, make_engine, make_session_factory
from app.infrastructure.llm.gemini_llm import GeminiLLM
from app.infrastructure.llm.ollama_llm import OllamaLLM
from app.infrastructure.llm.routed_llm import RoutedLLM
from app.infrastructure.ml.banglabert_classifier import BanglaBertClassifier
from app.infrastructure.ml.kmeans_clusterer import KMeansClusterer
from app.infrastructure.ml.llm_classifier import LLMClassifier
from app.infrastructure.ml.tfidf_classifier import TfidfClassifier
from app.infrastructure.retrieval.chroma_retriever import ChromaRetriever
from app.infrastructure.retrieval.e5_embedder import E5Embedder
from app.infrastructure.sms.console_sms import ConsoleSms
from app.infrastructure.sms.textbee_sms import TextbeeSms

log = logging.getLogger(__name__)

NOT_CONFIGURED = "not_configured"
EMPTY = "empty"


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ------------------------------------------------------------ database

    @cached_property
    def engine(self) -> Engine:
        return make_engine(self.settings.database_url)

    @cached_property
    def session_factory(self) -> sessionmaker[Session]:
        return make_session_factory(self.engine)

    def init_database(self) -> None:
        init_db(self.engine)

    # ------------------------------------------------------------ repositories (ports -> SQL adapters)

    @cached_property
    def conversations(self) -> ConversationRepo:
        return SqlConversationRepo(self.session_factory)

    @cached_property
    def checklists(self) -> ChecklistRepo:
        return SqlChecklistRepo(self.session_factory)

    @cached_property
    def question_logs(self) -> QuestionLogRepo:
        return SqlQuestionLogRepo(self.session_factory)

    @cached_property
    def calls(self) -> CallRepo:
        return SqlCallRepo(self.session_factory)

    @cached_property
    def clusters(self) -> ClusterRepo:
        return SqlClusterRepo(self.session_factory)

    @cached_property
    def answer_cache(self) -> AnswerCache:
        return SqlAnswerCache(self.session_factory)

    # ------------------------------------------------------------ service catalog

    @cached_property
    def services(self) -> list[Service]:
        return load_services(self.settings.services_file)

    # ------------------------------------------------------------ retrieval (FR-AGT-05)

    @cached_property
    def embedder(self) -> E5Embedder:
        # The model loads on first use, not here.
        return E5Embedder(self.settings.embed_model, self.settings.embed_cache_dir)

    @cached_property
    def retriever(self) -> ChromaRetriever:
        return ChromaRetriever(
            self.settings.chroma_dir,
            self.embedder,
            min_score=self.settings.retrieval_min_score,
            host=self.settings.chroma_host,
            port=self.settings.chroma_port,
        )

    # ------------------------------------------------------------ LLM (FR-AGT-16, FR-AGT-18)

    @cached_property
    def gemini(self) -> GeminiLLM:
        s = self.settings
        return GeminiLLM(
            s.gemini_key_list,
            s.gemini_model_main,
            s.gemini_model_fast,
            fallback_model=s.gemini_model_fallback,
        )

    @cached_property
    def ollama(self) -> OllamaLLM:
        return OllamaLLM(self.settings.ollama_url, self.settings.ollama_model)

    @cached_property
    def llm(self) -> LLM:
        """LLM_BACKEND: gemini | ollama | hybrid (FAST on Ollama, MAIN on Gemini with Ollama fallback)."""
        backend = self.settings.llm_backend
        if backend == "ollama":
            return self.ollama
        if backend == "hybrid":
            return RoutedLLM(main=self.gemini, local=self.ollama)
        return self.gemini

    def check_llm(self) -> str:
        if self.settings.llm_backend == "gemini" and not self.gemini.configured:
            return NOT_CONFIGURED
        try:
            return "ok" if self.llm.check() else "error"
        except Exception:
            log.exception("LLM health check failed")
            return "error"

    # ------------------------------------------------------------ agent

    @cached_property
    def answer_engine(self) -> AnswerEngine:
        """AGENT_ENGINE: langgraph (the real agent, D1-T4) | stub (fixed sample answer, no keys needed)."""
        if self.settings.agent_engine == "stub":
            return StubAnswerEngine()
        return LangGraphAnswerEngine(self.agent_deps)

    # ------------------------------------------------------------ use cases

    @cached_property
    def list_services(self) -> ListServices:
        return ListServices(self.services)

    @cached_property
    def ask_question(self) -> AskQuestion:
        return AskQuestion(
            engine=self.answer_engine,
            conversations=self.conversations,
            checklists=self.checklists,
            question_logs=self.question_logs,
            services=self.services,
            phone_hash_salt=self.settings.phone_hash_salt.get_secret_value(),
            sms=self.sms,
            runner=self.runner,
        )

    @cached_property
    def get_history(self) -> GetHistory:
        return GetHistory(self.conversations, self.checklists)

    @cached_property
    def delete_history(self) -> DeleteHistory:
        return DeleteHistory(self.conversations, self.checklists)

    # ============================================================ team areas (docs/BUILD_PLAN.md Section 0.4)
    # Add new adapters and use cases ONLY inside your own area below, so two pull requests never
    # change the same lines. Changing a line outside your area: agree with its owner first.

    # ------------------------------------------------------------ voice area
    # Planned here: call_placer (Twilio), tts (gTTS), start_callback, handle_call_end, synthesize_speech
    # (steps D1-A3, D1-A5, D2-A1, D2-R2, D2-A2).

    @cached_property
    def silence_counter(self) -> "SilenceCounter":  # noqa: F821 (imported below to keep this area self-contained)
        """FR-CALL-04: empty speech results in a row, per CallSid (one per app)."""
        from app.interfaces.voice.call_state import SilenceCounter

        return SilenceCounter()

    @cached_property
    def handle_voice_turn(self) -> "HandleVoiceTurn":  # noqa: F821 (imported below, see silence_counter)
        """FR-CALL-02, 05, 06, 09: one spoken turn, answered by the same AskQuestion as the app."""
        from app.application.use_cases.speech import HandleVoiceTurn

        return HandleVoiceTurn(self.ask_question.execute, self.calls, self.conversations)

    @cached_property
    def record_call_start(self) -> "RecordCallStart":  # noqa: F821
        """FR-CALL-11: the calls row for /voice/incoming and /voice/start."""
        from app.application.use_cases.handle_call_end import RecordCallStart

        return RecordCallStart(self.calls)

    @cached_property
    def handle_call_end(self) -> "HandleCallEnd":  # noqa: F821
        """FR-CALL-11: end time from the Twilio status callback."""
        from app.application.use_cases.handle_call_end import HandleCallEnd

        return HandleCallEnd(self.calls)

    @cached_property
    def voice_answers(self) -> "VoiceAnswers":  # noqa: F821
        """FR-CALL-10: turns run in the background; slow answers come through /voice/result."""
        from app.application.use_cases.voice_jobs import VoiceAnswers

        return VoiceAnswers(self.handle_voice_turn.execute, self.runner)

    @cached_property
    def call_placer(self) -> "TwilioCallPlacer":  # noqa: F821
        """FR-CALL-07, 08: outbound calls through Twilio; they start at PUBLIC_URL/voice/start."""
        from app.infrastructure.telephony.twilio_call_placer import TwilioCallPlacer

        s = self.settings
        token = s.twilio_auth_token.get_secret_value()
        return TwilioCallPlacer(s.twilio_account_sid, token, s.twilio_number, s.public_url)

    @cached_property
    def start_callback(self) -> "StartCallback":  # noqa: F821
        """FR-CALL-07: "Call me" and missed-call call-backs, one per number per 60 s."""
        from app.application.use_cases.start_callback import StartCallback

        return StartCallback(self.call_placer, self.calls)

    @cached_property
    def handle_missed_call(self) -> "HandleMissedCall":  # noqa: F821
        """FR-CALL-08 (MISSED_CALL_MODE=true): reject the call, call back after a few seconds."""
        from app.application.use_cases.start_callback import HandleMissedCall

        return HandleMissedCall(self.start_callback, self.runner)

    @cached_property
    def tts(self) -> "GttsTts":  # noqa: F821
        """FR-APP-04: Bangla speech for the app's play button (gTTS, free, no key)."""
        from app.infrastructure.tts.gtts_tts import GttsTts

        return GttsTts()

    @cached_property
    def synthesize_speech(self) -> "SynthesizeSpeech":  # noqa: F821
        """FR-APP-04: POST /api/v1/tts, with the last answers kept in memory."""
        from app.application.use_cases.speech import SynthesizeSpeech

        return SynthesizeSpeech(self.tts)

    # ------------------------------------------------------------ SMS, background and admin area
    @cached_property
    def delete_checklist(self) -> "DeleteChecklist":  # noqa: F821 (imported below)
        from app.application.use_cases.history_items import DeleteChecklist

        return DeleteChecklist(self.checklists)

    # sms + runner (D1-A4, also passed into ask_question above); admin use cases (D2-R1).

    @cached_property
    def sms(self) -> SmsSender:
        """SMS_BACKEND: console (prints the SMS, the default) | textbee (real SMS, FR-SMS-03)."""
        s = self.settings
        if s.sms_backend == "textbee":
            return TextbeeSms(s.textbee_api_key.get_secret_value(), s.textbee_device_id)
        return ConsoleSms()

    @cached_property
    def runner(self) -> BackgroundRunner:
        """Background work: SMS (D1-A4), call-back (D2-A1) and async voice answers (D2-A2)."""
        return ThreadPoolRunner(max_workers=4)

    @cached_property
    def get_admin_stats(self) -> GetAdminStats:
        """FR-ADM-01: dashboard KPIs, per service and per channel, calls today."""
        return GetAdminStats(self.question_logs, self.calls, self.services)

    @cached_property
    def list_questions(self) -> ListQuestions:
        """FR-ADM-02: newest questions, e.g. only the unanswered (fallback) ones."""
        return ListQuestions(self.question_logs, self.services)

    @cached_property
    def admin_auth(self) -> AdminAuth:
        """FR-ADM-05: admin login and session tokens. No ADMIN_TOKEN: the admin area is closed."""
        s = self.settings
        return AdminAuth(s.admin_token.get_secret_value(), session_hours=s.admin_session_hours)

    # ------------------------------------------------------------ AI area
    # Planned here: classifier (tfidf | banglabert | llm), the LangGraph engine (replaces answer_engine
    # above), clusterer and cluster use cases (steps D1-R4, D1-T4, D1-T5, D2-T1, D2-T2, D2-T4).

    @cached_property
    def clusterer(self) -> Clusterer:
        return KMeansClusterer()

    @cached_property
    def rebuild_clusters(self) -> RebuildClusters:
        """FR-ADM-03: the same e5 embedder as the search; labels from the LLM, keywords as fallback."""
        return RebuildClusters(self.question_logs, self.embedder, self.clusterer, self.clusters, self.llm)

    @cached_property
    def list_clusters(self) -> ListClusters:
        return ListClusters(self.clusters)

    @cached_property
    def tfidf_classifier(self) -> TfidfClassifier:
        return TfidfClassifier(self.settings.tfidf_model_path)  # loads the joblib on first use

    @cached_property
    def services_by_id(self) -> dict[str, Service]:
        return {s.id: s for s in self.services}

    @cached_property
    def banglabert_classifier(self) -> BanglaBertClassifier:
        return BanglaBertClassifier(self.settings.router_model_dir)  # loads the model on first use

    @cached_property
    def classifier(self) -> ServiceClassifier:
        """ROUTER_BACKEND: banglabert (D2-T1) | tfidf (D1-R4) | llm (D1-T4).

        BanglaBERT without its model folder falls back to TF-IDF, so a laptop that has not
        downloaded the model still routes questions.
        """
        backend = self.settings.router_backend
        if backend == "llm":
            return LLMClassifier(self.llm, self.services_by_id)
        if backend == "banglabert":
            if self.banglabert_classifier.available:
                return self.banglabert_classifier
            log.warning(
                "ROUTER_BACKEND=banglabert but %s has no model; using tfidf", self.settings.router_model_dir
            )
        return self.tfidf_classifier

    def warm_up(self) -> threading.Thread | None:
        """Loads the router, the search model and the agent graph in the background (D2-T4).

        Without this the first question pays for the model loading (15 to 35 s). The server answers
        /health at once; a question that arrives during warm-up waits only for what is still loading.
        """
        if not self.settings.preload_models:
            return None
        thread = threading.Thread(target=self._preload, name="preload-models", daemon=True)
        thread.start()
        return thread

    def _preload(self) -> None:
        started = time.perf_counter()
        loaders: list[tuple[str, Callable[[], object]]] = [
            ("router", lambda: self.classifier.classify("বয়স্ক ভাতা")),
            ("search", lambda: self.retriever.search("বয়স্ক ভাতা", None, 1)),
            ("agent", lambda: self.answer_engine),
        ]
        for name, load in loaders:
            try:
                load()
            except Exception as exc:  # a missing model only means that part stays lazy
                log.warning("warm-up: %s not loaded (%s)", name, type(exc).__name__)
        log.info("warm-up finished in %.1f s", time.perf_counter() - started)

    def check_router(self) -> str:
        """The router in use (banglabert | tfidf | llm, SRS 8), or not_configured / error. Loads nothing."""
        backend = self.settings.router_backend
        if backend == "llm":
            return "llm" if self.check_llm() == "ok" else self.check_llm()
        if backend == "banglabert" and self.banglabert_classifier.available:
            return "banglabert"
        return "tfidf" if self.tfidf_classifier.available else NOT_CONFIGURED

    @cached_property
    def agent_deps(self) -> AgentDeps:
        s = self.settings
        return AgentDeps(
            classifier=self.classifier,
            retriever=self.retriever,
            llm=self.llm,
            services=self.services_by_id,
            confidence_threshold=s.router_confidence_threshold,
            cache=self.answer_cache,
            voice_fast_mode=s.voice_fast_mode,
            llm_backend=s.llm_backend,
            situation_mode=s.situation_mode,  # sprint: situations and mixed questions
            multi_service_min_prob=s.multi_service_min_prob,
            max_services=s.max_services_per_question,
            query_expansion=s.query_expansion,
            max_speech_words_multi=s.max_speech_words_multi,
            hint_classifier=self.hint_classifier,
            hint_min_confidence=s.situation_hint_min_confidence,
        )

    @cached_property
    def hint_classifier(self) -> ServiceClassifier | None:
        """TF-IDF v2 as the situation hint router (T6); None when its file is missing."""
        path = self.settings.situation_hint_model_path
        if not self.settings.situation_mode or not path.exists():
            return None
        return TfidfClassifier(path)

    # ------------------------------------------------------------ health (NFR-REL-02)

    def check_db(self) -> str:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return "ok"
        except Exception:  # any failure means "not usable"; details go to the log
            log.exception("database health check failed")
            return "error"

    def check_vector_db(self) -> str:
        """ok = passages are stored; empty = run `python -m scripts.ingest`. Never loads the model."""
        if not self.settings.chroma_host and not self.settings.chroma_dir.exists():
            return EMPTY  # do not create the folder just by asking
        try:
            return "ok" if self.retriever.count() > 0 else EMPTY
        except Exception:
            log.exception("vector store health check failed")
            return "error"

    def health(self) -> dict[str, str]:
        """Status of each part; not_configured / empty mean "set it up first", not "broken"."""
        parts = {
            "db": self.check_db(),
            "llm": self.check_llm(),
            "vector_db": self.check_vector_db(),
            "router": self.check_router(),
        }
        parts["status"] = "ok" if parts["db"] == "ok" else "error"
        return parts

    # ------------------------------------------------------------ shutdown

    def close(self) -> None:
        if "engine" in self.__dict__:  # only if it was ever built
            self.engine.dispose()
        if "ollama" in self.__dict__:
            self.ollama.close()
