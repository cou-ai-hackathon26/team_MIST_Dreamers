"""In-memory fakes for every port, used by unit tests (no network, no keys, no database)."""

import dataclasses
import hashlib
import uuid
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from app.application.ports.clustering import Cluster
from app.application.ports.llm import ModelRole
from app.application.ports.repositories import OTHER_SERVICE, ChecklistRecord, QuestionStats
from app.application.ports.retrieval import Passage
from app.domain.entities import Answer, Checklist, Citation, Message, QuestionLog
from app.domain.errors import LLMUnavailable, NotFound
from app.domain.value_objects import AnswerStatus, Channel, PhoneNumber, RouterSource

# ---------------------------------------------------------------- AI / ML


class FakeLLM:
    """Returns scripted JSON responses in order (or from `handler`) and records every prompt."""

    def __init__(
        self,
        responses: Sequence[dict[str, Any]] = (),
        handler: Callable[[str, Mapping[str, Any], ModelRole], dict[str, Any]] | None = None,
        fail: bool = False,
        healthy: bool = True,
    ) -> None:
        self._responses = list(responses)
        self._handler = handler
        self.fail = fail
        self.healthy = healthy
        self.prompts: list[str] = []
        self.roles: list[ModelRole] = []

    @property
    def calls(self) -> int:
        return len(self.prompts)

    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, Any],
        role: ModelRole = ModelRole.MAIN,
        temperature: float = 0.2,
    ) -> dict[str, Any]:
        self.prompts.append(prompt)
        self.roles.append(role)
        if self.fail:
            raise LLMUnavailable("FakeLLM set to fail")
        if self._handler is not None:
            return self._handler(prompt, schema, role)
        if not self._responses:
            raise AssertionError("FakeLLM ran out of scripted responses")
        return self._responses.pop(0)

    def generate_text(self, prompt: str, role: ModelRole = ModelRole.FAST) -> str:
        return str(self.generate_json(prompt, {}, role).get("text", ""))

    def check(self) -> bool:
        return self.healthy


class FakeClassifier:
    def __init__(self, scores: Mapping[str, float], source: RouterSource = RouterSource.TFIDF) -> None:
        self._scores = dict(scores)
        self._source = source
        self.texts: list[str] = []

    @property
    def source(self) -> RouterSource:
        return self._source

    def classify(self, text: str) -> list[tuple[str, float]]:
        self.texts.append(text)
        return sorted(self._scores.items(), key=lambda item: item[1], reverse=True)


class FakeEmbedder:
    """Deterministic 8-number vectors from a hash (same text -> same vector)."""

    def _vector(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        return [b / 255 for b in digest[:8]]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)

    def embed_passages(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._vector(t) for t in texts]


class FakeRetriever:
    def __init__(self, passages: Sequence[Passage] = ()) -> None:
        self.passages = list(passages)
        self.searches: list[tuple[str, str | None, int]] = []

    def search(self, query: str, service_id: str | None, k: int) -> list[Passage]:
        self.searches.append((query, service_id, k))
        found = [p for p in self.passages if service_id is None or p.service_id == service_id]
        return sorted(found, key=lambda p: p.score, reverse=True)[:k]


class FakeEngine:
    def __init__(self, answer: Answer) -> None:
        self.answer_to_return = answer
        self.questions: list[tuple[str, list[Message], Channel]] = []

    def answer(self, question: str, history: Sequence[Message], channel: Channel) -> Answer:
        self.questions.append((question, list(history), channel))
        return self.answer_to_return


class FakeClusterer:
    def __init__(self, k: int = 3) -> None:
        self.k = k

    def cluster(self, vectors: Sequence[Sequence[float]]) -> list[int]:
        return [i % self.k for i in range(len(vectors))]


# ---------------------------------------------------------------- messaging


class FakeSms:
    def __init__(self, succeed: bool = True) -> None:
        self.succeed = succeed
        self.sent: list[tuple[PhoneNumber, str]] = []

    def send(self, phone: PhoneNumber, text: str) -> bool:
        self.sent.append((phone, text))
        return self.succeed


class FakeCallPlacer:
    def __init__(self) -> None:
        self.calls: list[PhoneNumber] = []

    def call(self, phone: PhoneNumber) -> str:
        self.calls.append(phone)
        return f"CA_fake_{len(self.calls)}"


class FakeTts:
    def synthesize(self, text: str) -> bytes:
        return b"ID3fake-mp3:" + text.encode("utf-8")


class FakeRunner:
    """Runs submitted work immediately (inline) and records the requested delay."""

    def __init__(self) -> None:
        self.submitted: list[tuple[str, float]] = []

    def submit(self, fn: Callable[..., Any], *args: Any, delay_s: float = 0) -> None:
        self.submitted.append((getattr(fn, "__name__", repr(fn)), delay_s))
        fn(*args)


# ---------------------------------------------------------------- repositories


class InMemoryConversationRepo:
    def __init__(self) -> None:
        self._ids: dict[str, str] = {}
        self._messages: list[tuple[str, Message, str | None]] = []

    def get_or_create(self, phone: PhoneNumber) -> str:
        return self._ids.setdefault(phone.e164, str(uuid.uuid4()))

    def add_message(self, conversation_id: str, message: Message, call_sid: str | None = None) -> None:
        self._messages.append((conversation_id, message, call_sid))

    def recent_messages(self, phone: PhoneNumber, limit: int) -> list[Message]:
        conv_id = self._ids.get(phone.e164)
        mine = [m for cid, m, _ in self._messages if cid == conv_id]
        return mine[-limit:] if limit > 0 else []

    def delete_for_phone(self, phone: PhoneNumber) -> bool:
        conv_id = self._ids.pop(phone.e164, None)
        if conv_id is None:
            return False
        self._messages = [row for row in self._messages if row[0] != conv_id]
        return True


class InMemoryChecklistRepo:
    def __init__(self) -> None:
        self.rows: list[tuple[str, ChecklistRecord]] = []
        self._next_id = 1  # like an autoincrement key: an id is never given out twice

    def save(
        self,
        phone: PhoneNumber,
        checklist: Checklist,
        citations: Sequence[Citation],
        sms_sent: bool,
        call_sid: str | None = None,
    ) -> None:
        record = ChecklistRecord(
            checklist, tuple(citations), sms_sent, call_sid, datetime.now(UTC), id=str(self._next_id)
        )
        self._next_id += 1
        self.rows.append((phone.e164, record))

    def sms_already_sent(self, call_sid: str, service_id: str) -> bool:
        return any(
            r.sms_sent and r.call_sid == call_sid and r.checklist.service_id == service_id
            for _, r in self.rows
        )

    def list_for_phone(self, phone: PhoneNumber, limit: int) -> list[ChecklistRecord]:
        mine = [r for p, r in self.rows if p == phone.e164]
        return list(reversed(mine))[:limit]

    def delete_for_phone(self, phone: PhoneNumber) -> int:
        before = len(self.rows)
        self.rows = [row for row in self.rows if row[0] != phone.e164]
        return before - len(self.rows)

    def delete_one(self, phone: PhoneNumber, checklist_id: str) -> bool:
        before = len(self.rows)
        self.rows = [(p, r) for p, r in self.rows if not (p == phone.e164 and r.id == checklist_id)]
        return len(self.rows) < before


class InMemoryQuestionLogRepo:
    def __init__(self) -> None:
        self.logs: dict[int, QuestionLog] = {}

    def add(self, log: QuestionLog) -> None:
        self.logs[max(self.logs, default=0) + 1] = log  # like an autoincrement id: never reused

    def list_recent(self, status: AnswerStatus | None, limit: int) -> list[QuestionLog]:
        # Newest first; equal times -> the one added later first (same as the SQL repo).
        rows = [(i, log) for i, log in self.logs.items() if status is None or log.status is status]
        rows.sort(key=lambda row: (row[1].created_at, row[0]), reverse=True)
        return [log for _, log in rows][:limit]

    def texts_for_clustering(self) -> list[tuple[int, str]]:
        return [(log_id, log.text) for log_id, log in self.logs.items()]

    def set_cluster_ids(self, assignments: Mapping[int, int]) -> None:
        for log_id, cluster_id in assignments.items():
            self.logs[log_id] = dataclasses.replace(self.logs[log_id], cluster_id=cluster_id)

    def stats(self) -> QuestionStats:
        logs = list(self.logs.values())
        replied = [log.latency_ms for log in logs if log.status is not AnswerStatus.ERROR]
        return QuestionStats(
            total=len(logs),
            by_status=dict(Counter(log.status.value for log in logs)),
            by_service=dict(Counter(log.service_id or OTHER_SERVICE for log in logs)),
            by_channel=dict(Counter(log.channel.value for log in logs)),
            avg_latency_ms=sum(replied) / len(replied) if replied else 0.0,
        )

    def delete_demo(self) -> int:
        demo = [log_id for log_id, log in self.logs.items() if log.is_demo]
        for log_id in demo:
            del self.logs[log_id]
        return len(demo)


class InMemoryCallRepo:
    def __init__(self) -> None:
        self.calls: dict[str, dict[str, Any]] = {}

    def record_start(self, call_sid: str, phone: PhoneNumber, direction: str) -> None:
        if call_sid in self.calls:
            return  # idempotent
        self.calls[call_sid] = {
            "phone": phone.e164,
            "direction": direction,
            "started_at": datetime.now(UTC),
            "ended_at": None,
            "turns": 0,
        }

    def record_turn(self, call_sid: str) -> int:
        if call_sid not in self.calls:
            raise NotFound(f"unknown call {call_sid}")
        self.calls[call_sid]["turns"] += 1
        return int(self.calls[call_sid]["turns"])

    def record_end(self, call_sid: str) -> None:
        if call_sid in self.calls:
            self.calls[call_sid]["ended_at"] = datetime.now(UTC)

    def last_outbound_at(self, phone: PhoneNumber) -> datetime | None:
        times = [
            c["started_at"]
            for c in self.calls.values()
            if c["phone"] == phone.e164 and str(c["direction"]).startswith("outbound")
        ]
        return max(times, default=None)

    def count_since(self, since: datetime) -> int:
        return sum(1 for c in self.calls.values() if c["started_at"] >= since)


class InMemoryClusterRepo:
    def __init__(self) -> None:
        self.clusters: list[Cluster] = []

    def replace_all(self, clusters: Sequence[Cluster]) -> list[int]:
        self.clusters = [dataclasses.replace(c, id=i + 1) for i, c in enumerate(clusters)]
        return [c.id for c in self.clusters if c.id is not None]

    def list_all(self) -> list[Cluster]:
        return list(self.clusters)


class InMemoryAnswerCache:
    def __init__(self) -> None:
        self.store: dict[str, Answer] = {}

    def get(self, key: str) -> Answer | None:
        return self.store.get(key)

    def set(self, key: str, answer: Answer) -> None:
        self.store[key] = answer
