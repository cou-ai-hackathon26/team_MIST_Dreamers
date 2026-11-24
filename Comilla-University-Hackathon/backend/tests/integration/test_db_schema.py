"""The database schema matches SRS 6.2 and behaves safely (local SQLite only, no network)."""

import re
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from app.infrastructure.db.models import CallRow, ConversationRow, MessageRow
from app.infrastructure.db.session import init_db, make_engine, make_session_factory

SRS_PATH = Path(__file__).resolve().parents[3] / "docs" / "SRS.md"
OPTIONAL_TABLES = {"otp_codes"}  # COULD requirement, not built


def srs_tables() -> dict[str, set[str]]:
    """{table: {columns}} from the `| `table` | `col` (note), ... |` rows of SRS 6.2."""
    text = SRS_PATH.read_text(encoding="utf-8")
    section = text.split("### 6.2", 1)[1].split("### 6.3", 1)[0]
    tables: dict[str, set[str]] = {}
    for name, cells in re.findall(r"^\| `(\w+)` \|(.+)\|$", section, flags=re.MULTILINE):
        without_notes = re.sub(r"\([^)]*\)", "", cells)  # drop "(PK)", "(`user`/`assistant`)" ...
        tables[name] = set(re.findall(r"`(\w+)`", without_notes))
    return tables


@pytest.fixture
def engine():
    engine = make_engine("sqlite://")
    init_db(engine)
    return engine


def test_tables_and_columns_match_the_srs_exactly(engine) -> None:
    expected = {t: cols for t, cols in srs_tables().items() if t not in OPTIONAL_TABLES}
    inspector = inspect(engine)
    actual = {t: {c["name"] for c in inspector.get_columns(t)} for t in inspector.get_table_names()}
    assert actual == expected


def test_init_db_is_safe_to_run_twice(engine) -> None:
    init_db(engine)  # must not fail or drop anything


def test_file_database_creates_its_folder(tmp_path: Path) -> None:
    db_file = tmp_path / "nested" / "folder" / "ekcall.db"
    engine = make_engine(f"sqlite:///{db_file.as_posix()}")
    init_db(engine)
    assert db_file.exists()
    engine.dispose()


def test_deleting_a_conversation_deletes_its_messages(engine) -> None:
    session_factory = make_session_factory(engine)
    with session_factory() as s:
        conv = ConversationRow(phone="+8801712345678")
        s.add(conv)
        s.flush()
        s.add(MessageRow(conversation_id=conv.id, role="user", channel="app", text="বয়স্ক ভাতা"))
        s.commit()
        s.delete(conv)
        s.commit()
        assert s.scalars(select(MessageRow)).all() == []  # foreign key cascade works


def test_message_needs_an_existing_conversation(engine) -> None:
    with make_session_factory(engine)() as s:
        s.add(MessageRow(conversation_id="no-such-id", role="user", channel="app", text="x"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_call_sid_is_unique(engine) -> None:
    with make_session_factory(engine)() as s:
        s.add(CallRow(call_sid="CA1", phone="+8801712345678", direction="inbound"))
        s.add(CallRow(call_sid="CA1", phone="+8801712345678", direction="inbound"))
        with pytest.raises(IntegrityError):
            s.commit()


def test_times_come_back_as_aware_utc(engine) -> None:
    dhaka = timezone(timedelta(hours=6))
    started = datetime(2026, 11, 21, 10, 0, tzinfo=dhaka)
    with make_session_factory(engine)() as s:
        s.add(CallRow(call_sid="CA2", phone="+8801712345678", direction="inbound", started_at=started))
        s.commit()
    with make_session_factory(engine)() as s:
        row = s.scalars(select(CallRow)).one()
        assert row.started_at.tzinfo is not None
        assert row.started_at == started  # same instant
        assert row.started_at.astimezone(UTC).hour == 4


def test_naive_times_are_refused(engine) -> None:
    with make_session_factory(engine)() as s:
        naive = datetime(2026, 1, 1)  # no time zone
        s.add(CallRow(call_sid="CA3", phone="+8801712345678", direction="inbound", started_at=naive))
        with pytest.raises(Exception, match="naive datetime"):
            s.commit()
