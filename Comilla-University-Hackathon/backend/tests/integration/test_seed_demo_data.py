"""scripts/seed_demo_data.py: realistic, removable sample rows for the dashboard (D2-R1 / D2-R3)."""

import random
from datetime import UTC, datetime, timedelta

from app.config import Settings
from app.container import Container
from app.domain.entities import QuestionLog
from app.domain.value_objects import AnswerStatus, Channel
from scripts.seed_demo_data import QUESTIONS_DIR, build_logs, read_questions, seed

NOW = datetime(2026, 11, 22, 4, 0, tzinfo=UTC)
IN_SCOPE = read_questions(QUESTIONS_DIR / "seed.csv", "label")
OUT_OF_SCOPE = read_questions(QUESTIONS_DIR / "out_of_scope.csv", "topic")


def sample(count: int = 60, seed_value: int = 7) -> list[QuestionLog]:
    return build_logs(count, IN_SCOPE, OUT_OF_SCOPE, ["h1", "h2", "h3"], NOW, random.Random(seed_value))


def test_question_files_are_read() -> None:
    assert len(IN_SCOPE) > 100 and len(OUT_OF_SCOPE) > 20
    assert all(text and label for text, label in IN_SCOPE + OUT_OF_SCOPE)


def test_rows_look_like_a_real_week() -> None:
    logs = sample()
    assert len(logs) == 60
    assert all(log.is_demo for log in logs)
    assert all(NOW - timedelta(days=7) <= log.created_at <= NOW for log in logs)
    assert [log.created_at for log in logs] == sorted(log.created_at for log in logs)  # oldest first
    statuses = {log.status for log in logs}
    assert statuses == {AnswerStatus.ANSWERED, AnswerStatus.FOLLOW_UP, AnswerStatus.FALLBACK}
    assert {log.channel for log in logs} == {Channel.VOICE, Channel.APP}
    assert len({log.service_id for log in logs}) >= 6  # spread over the services
    assert all(log.service_id == "other" for log in logs if log.status is AnswerStatus.FALLBACK)


def test_same_seed_same_rows() -> None:
    assert [log.text for log in sample()] == [log.text for log in sample()]
    assert [log.text for log in sample(seed_value=1)] != [log.text for log in sample()]


def test_seed_replaces_old_sample_rows_and_keeps_real_ones() -> None:
    c = Container(Settings(_env_file=None, database_url="sqlite://"))
    try:
        c.init_database()
        c.question_logs.add(
            QuestionLog(phone_hash="h", channel=Channel.APP, text="আসল", status=AnswerStatus.ANSWERED)
        )
        assert seed(c, 30, random.Random(1), now=NOW) == 30
        assert seed(c, 30, random.Random(2), now=NOW) == 30  # second run replaces, does not add
        assert c.question_logs.stats().total == 31
        assert c.question_logs.delete_demo() == 30
        assert [log.text for log in c.question_logs.list_recent(None, 10)] == ["আসল"]
    finally:
        c.close()
