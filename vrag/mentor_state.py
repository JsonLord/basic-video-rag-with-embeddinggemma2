"""Conversation/research metadata in the existing transactionally backed-up jobs DB."""

import json
import time
from contextlib import contextmanager
from fastapi import HTTPException
from . import jobs


@contextmanager
def database():
    db = jobs.connect()
    try:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS mentor_conversations (
          id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL,
          created REAL NOT NULL, deleted INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS mentor_turns (
          id TEXT PRIMARY KEY, conversation TEXT NOT NULL, request_id TEXT NOT NULL,
          fingerprint TEXT NOT NULL, status TEXT NOT NULL, payload TEXT NOT NULL,
          messages TEXT NOT NULL DEFAULT '[]', error TEXT, created REAL NOT NULL,
          UNIQUE(conversation,request_id));
        CREATE TABLE IF NOT EXISTS mentor_events (
          seq INTEGER PRIMARY KEY AUTOINCREMENT, turn TEXT NOT NULL,
          conversation TEXT NOT NULL, kind TEXT NOT NULL, payload TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS mentor_events_conversation ON mentor_events(conversation,seq);
        CREATE TABLE IF NOT EXISTS research_jobs (
          id TEXT PRIMARY KEY, owner TEXT NOT NULL, conversation TEXT NOT NULL,
          idempotency_key TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL,
          payload TEXT NOT NULL, provider TEXT NOT NULL, revision INTEGER NOT NULL,
          destination_hash TEXT NOT NULL, remote_id TEXT, context_id TEXT,
          result TEXT, error TEXT, attempts INTEGER NOT NULL DEFAULT 0,
          cancel_requested INTEGER NOT NULL DEFAULT 0, created REAL NOT NULL, updated REAL NOT NULL,
          UNIQUE(owner,conversation,idempotency_key));
        """)
        yield db
        db.commit()
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()


def owned_conversation(cid, owner, db=None):
    if db is None:
        with database() as conn:
            return owned_conversation(cid, owner, conn)
    row = db.execute(
        "SELECT * FROM mentor_conversations WHERE id=? AND owner=? AND deleted=0",
        (cid, owner),
    ).fetchone()
    if not row:
        raise HTTPException(404, "conversation not found")
    return dict(row)


def turn_owned(owner, tid):
    with database() as db:
        row = db.execute(
            "SELECT conversation,status FROM mentor_turns WHERE id=?", (tid,)
        ).fetchone()
        if not row:
            return False
        try:
            owned_conversation(row["conversation"], owner, db)
        except HTTPException:
            return False
        return row["status"] == "running"


def event(tid, cid, kind, payload):
    encoded = json.dumps(payload, allow_nan=False)
    if len(encoded.encode()) > 40000:
        raise ValueError("event too large")
    with database() as db:
        if (
            db.execute(
                "SELECT COUNT(*) FROM mentor_events WHERE turn=?", (tid,)
            ).fetchone()[0]
            >= 4096
        ):
            raise ValueError("event capacity exceeded")
        db.execute(
            "INSERT INTO mentor_events(turn,conversation,kind,payload) VALUES(?,?,?,?)",
            (tid, cid, kind, encoded),
        )


def recover_turns():
    # Provider generations are not replayed after an uncertain process shutdown.
    with database() as db:
        db.execute(
            "UPDATE mentor_turns SET status='outcome_unknown',error='process_interrupted' WHERE status IN ('queued','running')"
        )


def compact_ledger():
    """A permanent deleted-conversation tombstone blocks replay before ledger GC.

    Keep uncertain entries and all active conversation results. Only completed
    entries belonging to terminal deleted conversations can be reclaimed.
    """
    with database() as db:
        if not db.execute(
            "SELECT 1 FROM sqlite_master WHERE name='mentor_tool_calls'"
        ).fetchone():
            return
        db.execute("""DELETE FROM mentor_tool_calls WHERE status='complete' AND session IN (
          SELECT t.id FROM mentor_turns t JOIN mentor_conversations c ON t.conversation=c.id
          WHERE c.deleted=1 AND t.status NOT IN ('running','queued','outcome_unknown')
          AND NOT EXISTS (SELECT 1 FROM research_jobs r WHERE r.conversation=c.id
          AND r.status NOT IN ('completed','failed','cancelled')))""")
