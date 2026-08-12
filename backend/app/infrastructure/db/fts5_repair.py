"""
FTS5 virtual-table repair helpers.

Background
----------
The `transcript_chunks_fts` table is an SQLite FTS5 virtual table that powers
BM25 retrieval. It is mirrored by triggers on `transcript_chunks` (ai/ad/au)
so insert/update/delete operations on the source table stay in sync.

In rare cases — typically when the SQLite file is copied across platforms,
restored from an older snapshot, or after an interrupted write — the FTS5
vtable becomes unusable: even `SELECT count(*) FROM transcript_chunks_fts`
raises `DatabaseError: vtable constructor failed`. Once corrupt, the
`AFTER DELETE` and `AFTER UPDATE` triggers that touch the virtual table fail
on **every** DELETE/UPDATE, which breaks:

* `system_reset_service.perform_factory_reset()` (bulk DELETE of all
  transcript_chunks → trigger fires into broken FTS → 500)
* Any code path that mutates transcript_chunks while the triggers are still
  installed.

Because the SQLite vtab registry is per-connection, a naive
`DROP TABLE IF EXISTS transcript_chunks_fts` against the same connection
that detected the corruption raises `vtable constructor failed`. The only
reliable recovery is:

    1. DROP the 3 triggers on transcript_chunks (so the broken vtable is no
       longer referenced)
    2. PRAGMA writable_schema=ON; DELETE FROM sqlite_master
       WHERE name='transcript_chunks_fts'; PRAGMA writable_schema=OFF
       (evict the broken vtable entry from the schema)
    3. DROP the five shadow tables
       (transcript_chunks_fts_{config,content,data,docsize,idx})
    4. Dispose the SQLAlchemy engine pool so the next connection has a fresh
       vtab registry (this is the SQLite-specific step that makes the next
       CREATE work)
    5. CREATE VIRTUAL TABLE transcript_chunks_fts USING fts5(...) and
       reinstall the three triggers with the exact DDL used by init_db().

The helper below implements that sequence and is idempotent: on a healthy
DB it performs a single probe and returns without modification.
"""

from __future__ import annotations

import logging
from typing import Tuple

import sqlite3

from sqlalchemy import text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

_FTS_TRIGGERS = ("transcript_chunks_ai", "transcript_chunks_ad", "transcript_chunks_au")
_FTS_SHADOWS = (
    "transcript_chunks_fts_config",
    "transcript_chunks_fts_content",
    "transcript_chunks_fts_data",
    "transcript_chunks_fts_docsize",
    "transcript_chunks_fts_idx",
)
_FTS_NAME = "transcript_chunks_fts"
_CREATE_FTS = (
    "CREATE VIRTUAL TABLE transcript_chunks_fts USING fts5("
    "chunk_id UNINDEXED, workspace_id UNINDEXED, text)"
)
_CREATE_TRIGGER_AI = (
    "CREATE TRIGGER transcript_chunks_ai AFTER INSERT ON transcript_chunks BEGIN "
    "INSERT INTO transcript_chunks_fts(chunk_id, workspace_id, text) "
    "VALUES (new.id, new.workspace_id, new.text); END"
)
_CREATE_TRIGGER_AD = (
    "CREATE TRIGGER transcript_chunks_ad AFTER DELETE ON transcript_chunks BEGIN "
    "DELETE FROM transcript_chunks_fts WHERE chunk_id = old.id; END"
)
_CREATE_TRIGGER_AU = (
    "CREATE TRIGGER transcript_chunks_au AFTER UPDATE ON transcript_chunks BEGIN "
    "DELETE FROM transcript_chunks_fts WHERE chunk_id = old.id; "
    "INSERT INTO transcript_chunks_fts(chunk_id, workspace_id, text) "
    "VALUES (new.id, new.workspace_id, new.text); END"
)


def _probe_file(db_path: str) -> bool:
    """Open the SQLite file with a brand-new sqlite3 handle (no vtab cache).

    An SQLAlchemy connection that has already constructed the FTS5 vtable
    will keep it cached for the lifetime of the connection. Probing through
    the engine pool can therefore report False-Negative on a healthy
    connection that was opened before the on-disk file became corrupt.
    """
    try:
        con = sqlite3.connect(db_path)
        try:
            con.execute(f"SELECT count(*) FROM {_FTS_NAME}").fetchone()
            return True
        finally:
            con.close()
    except Exception:
        return False


def _engine_db_path(engine: Engine) -> str | None:
    """Best-effort resolve of the underlying SQLite file path."""
    url = engine.url
    if not url.get_backend_name().startswith("sqlite"):
        return None
    db = url.database
    if not db:
        return None
    # `:memory:` urls have database == ":memory:" — nothing to do.
    if db == ":memory:":
        return None
    return db


def probe_transcript_chunks_fts(engine: Engine) -> bool:
    """Return True if `transcript_chunks_fts` is queryable on disk.

    For SQLite engines we deliberately bypass the pool and open a brand-new
    `sqlite3` connection to the file so the probe reflects the actual on-disk
    state, not a stale vtab cache from a long-lived pooled connection.
    For non-SQLite engines (PostgreSQL for the cloud target) we fall back to
    a pool probe — there's no FTS5 vtable to cache in that backend.
    """
    if engine is None:
        return True
    db_path = _engine_db_path(engine)
    if db_path is not None:
        return _probe_file(db_path)
    try:
        with engine.connect() as conn:
            row = conn.execute(text(f"SELECT count(*) FROM {_FTS_NAME}")).fetchone()
            _ = row[0] if row is not None else 0
        return True
    except Exception:
        return False


def repair_transcript_chunks_fts(engine: Engine) -> Tuple[str, bool]:
    """Ensure `transcript_chunks_fts` is queryable; rebuild it if not.

    Returns a (status, ok) tuple where status is one of:
        "healthy"     — probe succeeded; nothing was changed.
        "repaired"    — broken vtable was detected and rebuilt; post-probe ok.
        "noop-noengine" — engine was None; treated as healthy.
        "failed:<reason>" — repair attempt did not leave a queryable vtable.

    The function is safe to call on healthy databases (single probe, no writes).
    """
    if engine is None:
        return ("noop-noengine", True)

    if probe_transcript_chunks_fts(engine):
        return ("healthy", True)

    logger.warning("Detected broken transcript_chunks_fts virtual table; rebuilding.")

    db_path = _engine_db_path(engine)

    if db_path is not None:
        # On-disk repair path: open a brand-new sqlite3 connection for the
        # whole destructive + recreate sequence. This guarantees the vtab
        # registry is fresh on each step (the SQLAlchemy pool's connection
        # would still hold the broken cached vtable even after dispose()).
        try:
            with sqlite3.connect(db_path) as raw:
                # 1) drop triggers so subsequent DELETE/UPDATE of
                #    transcript_chunks never references the broken vtable.
                for trig in _FTS_TRIGGERS:
                    raw.execute(f"DROP TRIGGER IF EXISTS {trig}")
                # 2) evict the broken vtable from sqlite_master via
                #    writable_schema (plain DROP TABLE raises "vtable
                #    constructor failed" against the broken vtable).
                raw.execute("PRAGMA writable_schema=ON")
                raw.execute(
                    "DELETE FROM sqlite_master WHERE name = ?", (_FTS_NAME,)
                )
                raw.execute("PRAGMA writable_schema=OFF")
                # 3) drop the 5 shadow tables.
                for shadow in _FTS_SHADOWS:
                    raw.execute(f"DROP TABLE IF EXISTS {shadow}")
                raw.commit()
            # 4) New connection: the vtab registry is empty for this file,
            # so CREATE VIRTUAL TABLE succeeds.
            with sqlite3.connect(db_path) as raw:
                raw.execute(_CREATE_FTS)
                raw.execute(_CREATE_TRIGGER_AI)
                raw.execute(_CREATE_TRIGGER_AD)
                raw.execute(_CREATE_TRIGGER_AU)
                raw.commit()
        except Exception as e:
            msg = f"failed:recreate:{type(e).__name__}:{e}"
            logger.error("FTS5 rebuild failed: %s", e)
            return (msg, False)

        # Dispose the engine pool so the backend reopens against the
        # freshly-rebuilt file on next checkout.
        try:
            engine.dispose()
        except Exception as e:  # pragma: no cover
            logger.warning("engine.dispose() failed: %s", e)

        if probe_transcript_chunks_fts(engine):
            logger.info("Successfully rebuilt transcript_chunks_fts virtual table.")
            return ("repaired", True)
        return ("failed:probe-after-rebuild", False)

    # Non-SQLite (e.g. PostgreSQL cloud target) — there is no FTS5 vtable
    # to repair here. Probe ran via the engine pool; nothing to do.
    return ("failed:non-sqlite-corrupt-state", False)
