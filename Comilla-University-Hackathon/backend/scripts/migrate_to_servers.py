"""Copies the local data into the Docker services from docker-compose.yml (run once per machine).

Run from backend/, with the services up (`docker compose up -d`) and backend/.env pointing at them
(DATABASE_URL=postgresql+psycopg://..., CHROMA_HOST=localhost):

    python -m scripts.migrate_to_servers

- SQLite file (data/ekcall.db) -> Postgres: every table, same ids, then the id counters move past them.
- Chroma files (data/chroma) -> Chroma server: the passages with their stored embeddings, so nothing is
  re-embedded and the answer cache stays valid.
Refuses to write into a Postgres table or a Chroma collection that already has data. The local files are
only read, never changed, so the old setup keeps working if you switch back.
"""

import argparse
import sys
from pathlib import Path

from sqlalchemy import Engine, Integer, create_engine, func, select, text

from app.config import BACKEND_DIR, get_settings
from app.infrastructure.db.models import Base
from app.infrastructure.db.session import init_db, make_engine
from app.infrastructure.retrieval.chroma_retriever import COLLECTION

SQLITE_FILE = BACKEND_DIR / "data" / "ekcall.db"
CHROMA_DIR = BACKEND_DIR / "data" / "chroma"
BATCH = 500


def copy_database(source: Engine, target: Engine) -> dict[str, int]:
    init_db(target)  # creates the tables if they are missing
    tables = Base.metadata.sorted_tables  # parents before children (foreign keys)
    with target.connect() as conn:
        full = [t.name for t in tables if conn.execute(select(func.count()).select_from(t)).scalar()]
    if full:
        sys.exit(f"Postgres already has data in: {', '.join(full)}. Nothing copied.")

    copied: dict[str, int] = {}
    with source.connect() as src, target.begin() as dst:  # one transaction: all tables or none
        for table in tables:
            rows = [dict(r._mapping) for r in src.execute(select(table))]
            for start in range(0, len(rows), BATCH):
                dst.execute(table.insert(), rows[start : start + BATCH])
            copied[table.name] = len(rows)
            _move_id_counter(dst, table)
    return copied


def _move_id_counter(conn, table) -> None:  # type: ignore[no-untyped-def]
    """Rows kept their ids, so the next new row must get max(id) + 1, not 1."""
    keys = list(table.primary_key.columns)
    if len(keys) != 1 or not isinstance(keys[0].type, Integer):
        return
    column = keys[0].name
    sequence = conn.execute(text("SELECT pg_get_serial_sequence(:t, :c)"), {"t": table.name, "c": column})
    name = sequence.scalar()
    if name:
        conn.execute(
            text(f"SELECT setval(:s, COALESCE((SELECT MAX({column}) FROM {table.name}), 0) + 1, false)"),
            {"s": name},
        )


def copy_chroma(chroma_dir: Path, host: str, port: int) -> int:
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    settings = ChromaSettings(anonymized_telemetry=False)
    source = chromadb.PersistentClient(path=str(chroma_dir), settings=settings).get_collection(COLLECTION)
    server = chromadb.HttpClient(host=host, port=port, settings=settings)
    if COLLECTION in [c.name for c in server.list_collections()]:
        sys.exit(f"The Chroma server already has '{COLLECTION}'. Nothing copied.")

    data = source.get(include=["embeddings", "documents", "metadatas"])
    target = server.create_collection(COLLECTION, configuration={"hnsw": {"space": "cosine"}})
    try:
        for start in range(0, len(data["ids"]), BATCH):
            end = start + BATCH
            target.add(
                ids=data["ids"][start:end],
                embeddings=data["embeddings"][start:end],
                documents=data["documents"][start:end],
                metadatas=data["metadatas"][start:end],
            )
    except Exception:
        server.delete_collection(COLLECTION)  # no half-copied collection left behind
        raise
    if target.count() != source.count():
        sys.exit(f"Chroma copy incomplete: {target.count()} of {source.count()} passages")
    return int(target.count())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--sqlite", type=Path, default=SQLITE_FILE)
    parser.add_argument("--chroma-dir", type=Path, default=CHROMA_DIR)
    args = parser.parse_args()
    settings = get_settings()

    if not settings.database_url.startswith("postgresql"):
        sys.exit("DATABASE_URL in backend/.env is not Postgres. Set it first (see .env.example).")
    if not settings.chroma_host:
        sys.exit("CHROMA_HOST in backend/.env is empty. Set it first (see .env.example).")
    if not args.sqlite.exists():
        sys.exit(f"No SQLite file at {args.sqlite}")

    source = create_engine(f"sqlite:///{args.sqlite.as_posix()}")
    target = make_engine(settings.database_url)
    try:
        copied = copy_database(source, target)
    finally:
        source.dispose()
        target.dispose()
    print(f"{'Postgres table':16} {'rows':>6}")
    for name, n in copied.items():
        print(f"{name:16} {n:>6}")

    if args.chroma_dir.exists():
        n = copy_chroma(args.chroma_dir, settings.chroma_host, settings.chroma_port)
        print(f"\nChroma server: {n} passages in '{COLLECTION}'")
    else:
        print(f"\nNo Chroma files at {args.chroma_dir}: run python -m scripts.ingest instead")
    print("\nDone. Restart the backend; /health should say db ok and vector_db ok.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
