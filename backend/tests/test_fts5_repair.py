"""
Tests for the transcript_chunks_fts FTS5 repair helper.

These tests use scratch SQLite files copied from a reference DB layout so we
can exercise the corrupt-vtable recovery path without touching real data.
"""
import os
import shutil
import tempfile
import pytest
from sqlalchemy import create_engine, text

from app.infrastructure.db.fts5_repair import (
    probe_transcript_chunks_fts,
    repair_transcript_chunks_fts,
)


@pytest.fixture
def scratch_db_with_broken_fts():
    """Create a scratch SQLite file with a deliberately broken FTS5 vtable.

    Corruption mode: clear the ``transcript_chunks_fts_config`` shadow table
    (FTS5 stores ``version=4`` there). A fresh connection to the file will
    then refuse to construct the vtable with::

        OperationalError: invalid fts5 file format (found 0, expected 4 or 5)
        - run 'rebuild'

    The same symptom class as the production ``vtable constructor failed:
    transcript_chunks_fts`` error. Any DELETE or UPDATE on
    ``transcript_chunks`` fires the after-triggers into the broken vtable and
    fails the whole transaction — exactly the regression the helper prevents.

    Note on fixture setup: corruption MUST be applied via raw ``sqlite3`` in
    a separate process-connection, *not* through the SQLAlchemy engine. Once
    an SQLAlchemy connection constructs the FTS5 vtable it is cached on the
    connection for its lifetime; subsequent probes via the same pool can
    return True even though the on-disk file is corrupt. Using a raw
    ``sqlite3`` handle for the corruption avoids that warm-cache false-negative.
    """
    import sqlite3 as _sqlite3

    tmp = tempfile.mkdtemp(prefix="athenus-fts5-test-")
    db_path = os.path.join(tmp, "scratch.db")
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    try:
        with engine.begin() as conn:
            conn.execute(text(
                "CREATE TABLE transcript_chunks ("
                "id VARCHAR PRIMARY KEY, workspace_id VARCHAR, "
                "media_id VARCHAR, text TEXT, start_time FLOAT, end_time FLOAT, "
                "chunk_index INT, word_count INT)"
            ))
            conn.execute(text(
                "CREATE VIRTUAL TABLE transcript_chunks_fts USING fts5("
                "chunk_id UNINDEXED, workspace_id UNINDEXED, text)"
            ))
        # Dispose the SQLAlchemy pool so the next probe opens a truly fresh
        # connection (no warm vtab cache from a prior session).
        engine.dispose()

        # Corrupt via raw sqlite3: clear the _config shadow so version=4 is
        # gone and SQLite reports "invalid fts5 file format" on file open.
        raw = _sqlite3.connect(db_path)
        raw.execute("DELETE FROM transcript_chunks_fts_config")
        raw.commit()
        raw.close()

        # Sanity: probe must now return False.
        assert not probe_transcript_chunks_fts(engine)
        yield engine
    finally:
        engine.dispose()
        shutil.rmtree(tmp, ignore_errors=True)


def test_probe_healthy_engine_returns_true(tmp_path):
    """A freshly-created FTS5 table must probe as healthy (single SELECT count)."""
    db = tmp_path / "healthy.db"
    engine = create_engine(
        f"sqlite:///{db}", connect_args={"check_same_thread": False}
    )
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE transcript_chunks (id VARCHAR PRIMARY KEY, text TEXT)"
        ))
        conn.execute(text(
            "CREATE VIRTUAL TABLE transcript_chunks_fts USING fts5("
            "chunk_id UNINDEXED, workspace_id UNINDEXED, text)"
        ))
    try:
        assert probe_transcript_chunks_fts(engine) is True
    finally:
        engine.dispose()


def test_repair_is_idempotent_on_healthy_db(tmp_path):
    """Calling repair() on a healthy DB returns 'healthy' without writing."""
    db = tmp_path / "healthy.db"
    engine = create_engine(
        f"sqlite:///{db}", connect_args={"check_same_thread": False}
    )
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE transcript_chunks (id VARCHAR PRIMARY KEY, text TEXT)"
        ))
        conn.execute(text(
            "CREATE VIRTUAL TABLE transcript_chunks_fts USING fts5("
            "chunk_id UNINDEXED, workspace_id UNINDEXED, text)"
        ))
    try:
        status, ok = repair_transcript_chunks_fts(engine)
        assert status == "healthy"
        assert ok is True
        # Triggers not installed (init_db wasn't run) but repair() should not
        # have created them either.
        rows = engine.connect().execute(
            text("SELECT count(*) FROM sqlite_master "
                 "WHERE type='trigger' AND name LIKE 'transcript_chunks_a%'")
        ).fetchone()[0]
        assert rows == 0
    finally:
        engine.dispose()


def test_repair_rebuilds_broken_vtable(scratch_db_with_broken_fts):
    """The repair helper must evict the broken vtable and rebuild it cleanly."""
    engine = scratch_db_with_broken_fts
    status, ok = repair_transcript_chunks_fts(engine)
    assert status == "repaired"
    assert ok is True
    # Probe now succeeds.
    assert probe_transcript_chunks_fts(engine) is True
    # Triggers reinstalled and active.
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT count(*) FROM sqlite_master "
            "WHERE type='trigger' AND name LIKE 'transcript_chunks_a%'"
        )).fetchone()[0]
        assert rows == 3


def test_purge_after_repair_succeeds(scratch_db_with_broken_fts):
    """The actual regression: bulk DELETE of transcript_chunks must succeed
    after the repair, and FTS rows must follow via the trigger."""
    engine = scratch_db_with_broken_fts
    status, ok = repair_transcript_chunks_fts(engine)
    assert (status, ok) == ("repaired", True)

    with engine.begin() as conn:
        # Seed a chunk.
        conn.execute(text(
            "INSERT INTO transcript_chunks(id, workspace_id, text) "
            "VALUES ('c1', 'w1', 'hello world')"
        ))
        # Bulk purge.
        deleted = conn.execute(text("DELETE FROM transcript_chunks")).rowcount
        assert deleted == 1
    # FTS is empty.
    with engine.connect() as conn:
        assert conn.execute(
            text("SELECT count(*) FROM transcript_chunks_fts")
        ).fetchone()[0] == 0
        assert conn.execute(
            text("SELECT count(*) FROM transcript_chunks")
        ).fetchone()[0] == 0


def test_repair_then_repair_returns_healthy(scratch_db_with_broken_fts):
    """Calling repair twice must be safe — second call should report 'healthy'."""
    engine = scratch_db_with_broken_fts
    first, _ = repair_transcript_chunks_fts(engine)
    assert first == "repaired"
    second, ok = repair_transcript_chunks_fts(engine)
    assert second == "healthy"
    assert ok is True