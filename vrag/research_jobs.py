"""Durable, bounded outbound research coordinator. Never retry ambiguous submission."""

import asyncio
import hashlib
import json
import time
import uuid
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field, model_validator
from config.schema import Strict
from .mentor_api import user, runtime_snapshot
from .mentor_state import database, owned_conversation, compact_ledger
from .providers import ProviderFailure
from .research import adapter, identity, public_metadata

router = APIRouter(prefix="/api/research/jobs")
TERMINAL = {"completed", "failed", "cancelled"}


class Citation(Strict):
    url: str = Field(max_length=2000)
    title: str = Field(min_length=1, max_length=300)

    @model_validator(mode="after")
    def safe(self):
        try:
            u = urlsplit(self.url)
            port = u.port
        except ValueError:
            raise ValueError("invalid citation") from None
        if (
            u.scheme != "https"
            or not u.hostname
            or u.username
            or u.password
            or port not in (None, 443)
            or "/a2a/t-" in u.path
        ):
            raise ValueError("unsafe citation")
        return self


class Result(Strict):
    text: str = Field(min_length=1, max_length=8000)
    citations: list[Citation] = Field(min_length=1, max_length=20)


class Submit(Strict):
    conversation_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    request_id: str = Field(pattern=r"^[a-zA-Z0-9_-]{8,100}$")
    goal: str = Field(min_length=1, max_length=2000)
    agent_id: str = Field(
        default="documentation_research", pattern="^documentation_research$"
    )
    permitted_refs: list[str] = Field(default_factory=list, max_length=20)
    consent: bool = False


def get_job(jid, owner, cid=None, include_deleted=False):
    with database() as db:
        row = db.execute(
            "SELECT * FROM research_jobs WHERE id=? AND owner=?", (jid, owner)
        ).fetchone()
        if not row or cid and row["conversation"] != cid:
            raise HTTPException(404, "research job not found")
        if not include_deleted:
            owned_conversation(row["conversation"], owner, db)
        r = dict(row)
    return {
        "id": r["id"],
        "conversation_id": r["conversation"],
        "agent_id": "documentation_research",
        "status": r["status"],
        "remote_task_id": r["remote_id"],
        "context_id": r["context_id"],
        "history_revision": r["revision"],
        "result": json.loads(r["result"]) if r["result"] else None,
        "error": r["error"],
        "cancel_requested": bool(r["cancel_requested"]),
        "created": r["created"],
        "updated": r["updated"],
    }


def enqueue(body, owner):
    owned_conversation(body.conversation_id, owner)
    if not body.consent:
        raise HTTPException(403, "explicit research consent required")
    # Public API may delegate a typed question; only tools can attach owned refs.
    from .conversation import selected

    rev, cfg = runtime_snapshot()
    name, p = selected(cfg, "research.dispatch")
    endpoint = identity(p)
    payload = {
        "goal": body.goal,
        "agent_id": body.agent_id,
        "permitted_refs": body.permitted_refs,
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    with database() as db:
        db.execute("BEGIN IMMEDIATE")
        owned_conversation(body.conversation_id, owner, db)
        row = db.execute(
            "SELECT id,fingerprint FROM research_jobs WHERE owner=? AND conversation=? AND idempotency_key=?",
            (owner, body.conversation_id, body.request_id),
        ).fetchone()
        if row:
            if row["fingerprint"] != digest:
                raise HTTPException(409, "idempotency conflict")
            jid = row["id"]
        else:
            if (
                db.execute(
                    "SELECT COUNT(*) FROM research_jobs WHERE status NOT IN ('completed','failed','cancelled')"
                ).fetchone()[0]
                >= 100
            ):
                raise HTTPException(429, "research queue capacity")
            if (
                db.execute(
                    "SELECT COUNT(*) FROM research_jobs WHERE owner=?", (owner,)
                ).fetchone()[0]
                >= 2000
            ):
                raise HTTPException(429, "research history capacity")
            jid = "research_" + uuid.uuid4().hex
            now = time.time()
            db.execute(
                "INSERT INTO research_jobs(id,owner,conversation,idempotency_key,fingerprint,status,payload,provider,revision,destination_hash,created,updated) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    jid,
                    owner,
                    body.conversation_id,
                    body.request_id,
                    digest,
                    "queued",
                    json.dumps(payload),
                    name,
                    rev,
                    endpoint,
                    now,
                    now,
                ),
            )
    return get_job(jid, owner, body.conversation_id)


def request_cancel(jid, owner, cid=None):
    old = get_job(jid, owner, cid)
    with database() as db:
        if old["status"] not in TERMINAL:
            db.execute(
                "UPDATE research_jobs SET cancel_requested=1,attempts=0,updated=?,status=CASE WHEN status='queued' THEN 'cancelled' ELSE status END WHERE id=? AND cancel_requested=0",
                (time.time(), jid),
            )
    return get_job(jid, owner, cid)


def tool_conversation(context):
    with database() as db:
        row = db.execute(
            "SELECT conversation FROM mentor_turns WHERE id=?", (context.session_id,)
        ).fetchone()
        if not row:
            raise HTTPException(404, "turn not found")
        owned_conversation(row["conversation"], context.owner, db)
        return row["conversation"]


async def dispatch_tool(args, context):
    cid = tool_conversation(context)
    # Stable identity across a crash between queue insertion and tool ledger commit.
    key = hashlib.sha256(
        (context.session_id + json.dumps(args.model_dump(), sort_keys=True)).encode()
    ).hexdigest()
    return enqueue(
        Submit(
            conversation_id=cid,
            request_id=key,
            goal=args.goal,
            agent_id=args.agent_id,
            permitted_refs=args.permitted_refs,
            consent=context.allow_research,
        ),
        context.owner,
    )


async def status_tool(args, context):
    return get_job(args.job_id, context.owner, tool_conversation(context))


async def cancel_tool(args, context):
    return request_cancel(args.job_id, context.owner, tool_conversation(context))


def recover():
    with database() as db:
        db.execute(
            "UPDATE research_jobs SET status='outcome_unknown',error='submission_interrupted' WHERE status='dispatching' AND remote_id IS NULL"
        )


def output(task, p):
    # Only bounded text JSON artifacts; no files, remote fetches, HTML execution,
    # agent instructions or arbitrary protocol data become application actions.
    parts = [part.root for artifact in task.artifacts or [] for part in artifact.parts]
    if (
        not parts
        or len(parts) > 20
        or any(getattr(p, "kind", "") != "text" for p in parts)
    ):
        raise ProviderFailure("a2a_invalid_result")
    text = "".join(part.text for part in parts)
    if len(text.encode()) > 16000:
        raise ProviderFailure("a2a_invalid_result")
    import os

    key = os.environ.get(p.api_key_secret, "") if p.api_key_secret else ""
    if key and key in text:
        raise ProviderFailure("a2a_sensitive_result")
    try:
        result = Result.model_validate_json(text).model_dump()
    except ValueError:
        raise ProviderFailure("a2a_invalid_result") from None
    return {
        **result,
        "authority": "untrusted advisory research; source links have not been independently verified",
    }


def save_task(row, task, info, p):
    public_metadata([task.id, task.context_id], p)
    if row["remote_id"] and task.id != row["remote_id"]:
        raise ProviderFailure("a2a_task_identity_mismatch")
    if row["context_id"] and task.context_id != row["context_id"]:
        raise ProviderFailure("a2a_task_identity_mismatch")
    state = {
        "submitted": "submitted",
        "working": "running",
        "input-required": "input_required",
        "completed": "completed",
        "canceled": "cancelled",
        "failed": "failed",
        "rejected": "failed",
        "auth-required": "input_required",
    }.get(task.status.state.value)
    if not state:
        raise ProviderFailure("a2a_invalid_task_state")
    result = output(task, p) if state == "completed" else None
    if result:
        result["provenance"] = {
            "agent": info,
            "task_id": task.id,
            "context_id": task.context_id,
            "received_at": time.time(),
            "history_revision": row["revision"],
        }
    with database() as db:
        # Cancellation requests made while HTTP was in flight are preserved.
        deleted = db.execute(
            "SELECT deleted FROM mentor_conversations WHERE id=?",
            (row["conversation"],),
        ).fetchone()[0]
        db.execute(
            "UPDATE research_jobs SET status=?,remote_id=?,context_id=?,result=?,error=NULL,attempts=0,updated=? WHERE id=?",
            (
                state,
                task.id,
                task.context_id,
                json.dumps(result) if result and not deleted else None,
                time.time(),
                row["id"],
            ),
        )
        if deleted and state in TERMINAL:
            db.execute("UPDATE research_jobs SET payload='{}' WHERE id=?", (row["id"],))


async def step(row):
    from .conversation import selected

    if row["status"] in TERMINAL or row["attempts"] >= 6:
        return
    if time.time() - row["created"] > 86400:
        with database() as db:
            db.execute(
                "UPDATE research_jobs SET status='outcome_unknown',error='research_deadline_exceeded',attempts=6,updated=? WHERE id=?",
                (time.time(), row["id"]),
            )
        return
    try:
        _, cfg = runtime_snapshot()
        name, p = selected(cfg, "research.dispatch")
        if name != row["provider"] or identity(p) != row["destination_hash"]:
            raise ProviderFailure("research_configuration_changed")
        if row["status"] == "queued":
            # Persist before network IO. A timeout/crash after this point can never
            # cause another submit, even if the remote accepted the first request.
            with database() as db:
                db.execute("BEGIN IMMEDIATE")
                changed = db.execute(
                    "UPDATE research_jobs SET status='dispatching',attempts=attempts+1,updated=? WHERE id=? AND status='queued' AND cancel_requested=0",
                    (time.time(), row["id"]),
                ).rowcount
            if not changed:
                return
            task, info = await adapter.submit(p, row["id"], json.loads(row["payload"]))
        elif row["remote_id"]:
            with database() as db:
                db.execute(
                    "UPDATE research_jobs SET attempts=attempts+1,updated=? WHERE id=?",
                    (time.time(), row["id"]),
                )
            task, info = await (
                adapter.cancel(p, row["remote_id"])
                if row["cancel_requested"] == 1
                else adapter.get(p, row["remote_id"])
            )
        else:
            return
        save_task(row, task, info, p)
        if row["cancel_requested"] == 1:
            with database() as db:
                db.execute(
                    "UPDATE research_jobs SET cancel_requested=2 WHERE id=? AND cancel_requested=1",
                    (row["id"],),
                )
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        code = (
            exc.code
            if isinstance(exc, ProviderFailure)
            else "research_operation_failed"
        )
        permanent = code in {
            "provider_auth_denied",
            "credential_missing",
            "credential_invalid",
            "destination_denied",
            "research_configuration_changed",
            "a2a_agent_identity_mismatch",
            "a2a_card_destination_mismatch",
            "a2a_auth_unqualified",
            "a2a_protocol_unqualified",
            "a2a_invalid_metadata",
            "a2a_sensitive_metadata",
            "a2a_invalid_result",
            "a2a_sensitive_result",
            "a2a_task_identity_mismatch",
        }
        # Invalid final data is failed; unknown network submission is never retried.
        state = (
            "failed"
            if code
            in {
                "a2a_invalid_metadata",
                "a2a_sensitive_metadata",
                "a2a_invalid_result",
                "a2a_sensitive_result",
                "a2a_task_identity_mismatch",
            }
            else "outcome_unknown"
        )
        with database() as db:
            db.execute(
                "UPDATE research_jobs SET status=?,error=?,attempts=CASE WHEN ? THEN 6 ELSE attempts END,updated=? WHERE id=?",
                (state, code, int(permanent), time.time(), row["id"]),
            )


async def coordinator():
    recover()
    while True:
        with database() as db:
            rows = [
                dict(r)
                for r in db.execute(
                    "SELECT * FROM research_jobs WHERE status IN ('queued','submitted','running','input_required','outcome_unknown') AND attempts<6 ORDER BY updated LIMIT 100"
                )
            ]
        eligible = [
            r
            for r in rows
            if r["status"] == "queued"
            or r["remote_id"]
            and time.time() - r["updated"] >= min(60, 2 ** (r["attempts"] + 1))
        ]
        # No unbounded background task fanout; camera/chat requests stay independent.
        for offset in range(0, len(eligible), 2):
            await asyncio.gather(*(step(r) for r in eligible[offset : offset + 2]))
        compact_ledger()
        await asyncio.sleep(1)


@router.post("")
def create(body: Submit, owner=Depends(user)):
    if body.permitted_refs:
        raise HTTPException(
            403,
            "attach observation references only through an authorized conversation turn",
        )
    return enqueue(body, owner)


@router.get("")
def listing(conversation_id: str, owner=Depends(user)):
    owned_conversation(conversation_id, owner)
    with database() as db:
        ids = [
            r[0]
            for r in db.execute(
                "SELECT id FROM research_jobs WHERE owner=? AND conversation=? ORDER BY created DESC LIMIT 100",
                (owner, conversation_id),
            )
        ]
    return [get_job(jid, owner, conversation_id) for jid in ids]


@router.get("/{jid}")
def detail(jid: str, owner=Depends(user)):
    return get_job(jid, owner)


@router.post("/{jid}/cancel")
def cancel(jid: str, owner=Depends(user)):
    return request_cancel(jid, owner)


@router.get("/{jid}/artifacts")
def artifacts(jid: str, owner=Depends(user)):
    job = get_job(jid, owner)
    return {"status": job["status"], "result": job["result"]}
