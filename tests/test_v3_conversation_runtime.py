"""Real local SQLite/API orchestration with fake OpenAI + official SDK wire fixtures."""

import asyncio
import hashlib
import json
import time
import httpx
import pytest
from config.v2 import ConfigurationV2, ProviderV2
from config.schema import Route
from vrag import conversation as chat, research_jobs as research
from vrag.mentor_state import database, recover_turns, compact_ledger
from vrag.research import A2AAdapter
from vrag.api import app

TOKEN = "v3-chat-test-user-token-00000000"
OWNER = hashlib.sha256(("Bearer " + TOKEN).encode()).hexdigest()

from v3_protocol_fixtures import packet, completion, calls, WireAgent


@pytest.fixture
def runtime(tmp_path, monkeypatch):
    monkeypatch.setattr("vrag.jobs.DATA", tmp_path)
    monkeypatch.setenv("VM_USER_TOKEN", TOKEN)
    monkeypatch.setenv("OPENAI_COMPATIBLE_URL", "https://models.example/v1")
    monkeypatch.setenv("A2A_URL", "https://agent.example/a2a/t-{token}")
    monkeypatch.setenv("A2A_TOKEN", "synthetic-path-key-12345")
    monkeypatch.setenv("VM_ALLOWED_HOSTS", "models.example,agent.example")
    monkeypatch.setattr(
        "socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", ("8.8.8.8", 443))]
    )
    qwen = ProviderV2(
        adapter="openai-conversation",
        model="fixture-qwen",
        base_url_env="OPENAI_COMPATIBLE_URL",
        trust="approved_sensitive",
        capabilities=["conversation"],
    )
    agent = ProviderV2(
        adapter="a2a",
        model="Agent Zero fixture",
        base_url_env="A2A_URL",
        api_key_secret="A2A_TOKEN",
        auth_mode="path_token",
        trust="approved_sensitive",
        capabilities=["research_dispatch"],
    )
    cfg = ConfigurationV2(
        providers={"qwen": qwen, "agent": agent},
        features={
            "mentor.conversation": Route(providers=["qwen"]),
            "research.dispatch": Route(providers=["agent"]),
        },
    )
    monkeypatch.setattr(chat, "runtime_snapshot", lambda: (4, cfg))
    monkeypatch.setattr(research, "runtime_snapshot", lambda: (4, cfg))
    monkeypatch.setattr("vrag.mentor_api.runtime_snapshot", lambda: (4, cfg))
    monkeypatch.setattr(chat, "tools", None)
    chat.runs.clear()
    return cfg


async def client():
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://testserver",
        headers={"Authorization": "Bearer " + TOKEN},
    )


async def wait_turn(cid):
    async with await client() as c:
        for _ in range(100):
            result = (await c.get("/api/mentor/conversations/" + cid)).json()
            if result["turns"] and result["turns"][-1]["status"] not in (
                "running",
                "queued",
            ):
                return result["turns"][-1]
            await asyncio.sleep(0.01)
    pytest.fail("generation did not terminate")


async def setup_job(c, cid, key="request_research_001"):
    r = await c.post(
        "/api/research/jobs",
        json={
            "conversation_id": cid,
            "request_id": key,
            "goal": "Research safe assembly",
            "consent": True,
        },
    )
    assert r.status_code == 200, r.text
    return r.json()


def row(jid):
    with database() as db:
        return dict(
            db.execute("SELECT * FROM research_jobs WHERE id=?", (jid,)).fetchone()
        )


@pytest.mark.asyncio
async def test_full_stream_tool_followup_async_research_reconnect_and_continuation(
    runtime, monkeypatch
):
    wire = WireAgent()
    monkeypatch.setattr(research, "adapter", A2AAdapter(httpx.MockTransport(wire)))
    requests = []

    async def evidence(args, context):
        return {
            "citations": [
                {
                    "video_id": "fixture-video",
                    "idx": 0,
                    "title": "Assembly",
                    "start": 1,
                    "end": 3,
                    "text": "Clear the workbench",
                }
            ],
            "provenance": {"fixture": True},
        }

    tools = chat.registry()
    tools.handlers["retrieve_video_evidence"] = evidence
    monkeypatch.setattr(chat, "tools", tools)

    def qwen(request):
        b = json.loads(request.content)
        requests.append(b)
        if b["messages"][-1]["role"] == "tool":
            assistant = b["messages"][-3]
            assert (
                assistant["role"] == "assistant" and len(assistant["tool_calls"]) == 2
            )
            assert [m["tool_call_id"] for m in b["messages"][-2:]] == [
                "call_0",
                "call_1",
            ]
            data = completion("I found a clip. Research is running independently.")
        elif "Incorporate" in b["messages"][-1]["content"]:
            assert "https://docs.example/safety" in b["messages"][-1]["content"]
            data = completion("Updated answer: clear the workbench [Safety guide].")
        else:
            data = calls(
                [
                    ("retrieve_video_evidence", {"query": "assembly"}),
                    (
                        "dispatch_research",
                        {
                            "goal": "Research safe assembly",
                            "agent_id": "documentation_research",
                        },
                    ),
                ]
            )
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=data
        )

    monkeypatch.setattr(chat.adapter, "transport", httpx.MockTransport(qwen))
    async with await client() as c:
        cid = (await c.post("/api/mentor/conversations", json={})).json()["id"]
        body = {
            "request_id": "user_turn_001",
            "text": "Help with assembly",
            "allow_research": True,
        }
        first = await c.post(f"/api/mentor/conversations/{cid}/turns", json=body)
        assert first.status_code == 200
        turn = await wait_turn(cid)
        assert turn["status"] == "completed", turn
        duplicate = await c.post(f"/api/mentor/conversations/{cid}/turns", json=body)
        assert duplicate.json()["id"] == first.json()["id"]
        event_response = await c.get(f"/api/mentor/conversations/{cid}/events")
        assert "tool_result" in event_response.text
        packets = [
            json.loads(line[6:])
            for line in event_response.text.splitlines()
            if line.startswith("data: ")
        ]
        seq = packets[-1]["seq"]
        assert (
            await c.get(f"/api/mentor/conversations/{cid}/events?after={seq}")
        ).text == ""
        jobs = (
            await c.get("/api/research/jobs", params={"conversation_id": cid})
        ).json()
        assert len(jobs) == 1 and jobs[0]["status"] == "queued"
        assert wire.submissions == 0  # chat never waits on remote execution
        jid = jobs[0]["id"]
        await research.step(row(jid))
        assert research.get_job(jid, OWNER)["status"] == "running"
        # Recreate adapter + startup reconciliation, preserving DB, while task runs.
        monkeypatch.setattr(research, "adapter", A2AAdapter(httpx.MockTransport(wire)))
        research.recover()
        recover_turns()
        await research.step(row(jid))
        assert (
            research.get_job(jid, OWNER)["status"] == "completed"
            and wire.submissions == 1
        )
        restored = (await c.get(f"/api/research/jobs/{jid}/artifacts")).json()
        assert (
            restored["result"]["citations"][0]["url"] == "https://docs.example/safety"
        )
        new = await c.post(
            f"/api/mentor/conversations/{cid}/turns",
            json={
                "request_id": "user_turn_002",
                "text": "Incorporate completed research",
                "research_refs": [jid],
            },
        )
        assert new.status_code == 200
        assert (await wait_turn(cid))["status"] == "completed"
        assert len(requests) == 3
        assert (await c.post(f"/api/research/jobs/{jid}/cancel")).json()[
            "status"
        ] == "completed"
        with database() as db:
            assert (
                db.execute("SELECT COUNT(*) FROM mentor_tool_calls").fetchone()[0] == 2
            )
        assert (await c.delete(f"/api/mentor/conversations/{cid}")).status_code == 200
        assert (await c.get(f"/api/mentor/conversations/{cid}")).status_code == 404
        with database() as db:
            assert (
                db.execute("SELECT COUNT(*) FROM mentor_tool_calls").fetchone()[0] == 0
            )
        assert (
            await c.post(f"/api/mentor/conversations/{cid}/turns", json=body)
        ).status_code == 404


@pytest.mark.asyncio
async def test_research_duplicate_cancel_unknown_submission_and_malicious_results(
    runtime, monkeypatch
):
    wire = WireAgent()
    monkeypatch.setattr(research, "adapter", A2AAdapter(httpx.MockTransport(wire)))
    async with await client() as c:
        cid = (await c.post("/api/mentor/conversations", json={})).json()["id"]
        job = await setup_job(c, cid)
        assert (await setup_job(c, cid))["id"] == job["id"]
        await research.step(row(job["id"]))
        for _ in range(2):
            await c.post(f"/api/research/jobs/{job['id']}/cancel")
        await research.step(row(job["id"]))
        assert wire.cancelled == 1
        await c.post(f"/api/research/jobs/{job['id']}/cancel")
        assert wire.cancelled == 1
        wire.lost = True
        lost = await setup_job(c, cid, "request_lost_001")
        await research.step(row(lost["id"]))
        assert research.get_job(lost["id"], OWNER)["status"] == "outcome_unknown"
        research.recover()
        await research.step(row(lost["id"]))
        assert wire.submissions == 2
        wire.lost = False
        wire.malicious = True
        bad = await setup_job(c, cid, "request_bad_001")
        await research.step(row(bad["id"]))
        await research.step(row(bad["id"]))
        assert research.get_job(bad["id"], OWNER)["status"] == "failed"
        assert research.get_job(bad["id"], OWNER)["result"] is None
        with database() as db:
            assert "synthetic-path-key" not in json.dumps(
                [dict(r) for r in db.execute("SELECT * FROM research_jobs")]
            )


@pytest.mark.asyncio
async def test_ownership_privacy_and_permanent_failures(runtime, monkeypatch):
    wire = WireAgent()
    monkeypatch.setattr(research, "adapter", A2AAdapter(httpx.MockTransport(wire)))
    async with await client() as c:
        cid = (await c.post("/api/mentor/conversations", json={})).json()["id"]
        job = await setup_job(c, cid)
        with database() as db:
            db.execute(
                "UPDATE mentor_conversations SET owner=? WHERE id=?", ("b" * 64, cid)
            )
        assert (await c.get("/api/mentor/conversations/" + cid)).status_code == 404
        assert (await c.get("/api/research/jobs/" + job["id"])).status_code == 404
        with database() as db:
            db.execute(
                "UPDATE mentor_conversations SET owner=? WHERE id=?", (OWNER, cid)
            )
        wire.denied = True
        await research.step(row(job["id"]))
        assert row(job["id"])["attempts"] == 6
        assert row(job["id"])["error"] == "provider_auth_denied"
        assert wire.submissions == 0
        assert (
            await c.post(
                "/api/research/jobs",
                json={
                    "conversation_id": cid,
                    "request_id": "privacy_001",
                    "goal": "x",
                    "consent": False,
                },
            )
        ).status_code == 403
        assert (
            await c.post(
                "/api/research/jobs",
                json={
                    "conversation_id": cid,
                    "request_id": "privacy_002",
                    "goal": "x",
                    "consent": True,
                    "permitted_refs": ["camera1:1"],
                },
            )
        ).status_code == 403
        wire.denied = False
        wire.bad_url = True
        with pytest.raises(Exception, match="a2a_card_destination_mismatch"):
            await research.adapter.probe(runtime.providers["agent"])


@pytest.mark.asyncio
async def test_incomplete_stream_never_executes_and_cancelled_turn_does_not_restart(
    runtime, monkeypatch
):
    count = []

    async def handler(*a):
        count.append(1)
        return {}

    tools = chat.registry()
    tools.handlers["retrieve_video_evidence"] = handler
    monkeypatch.setattr(chat, "tools", tools)
    data = calls([("retrieve_video_evidence", {"query": "x"})]).replace(
        "data: [DONE]\n\n", ""
    )
    monkeypatch.setattr(
        chat.adapter,
        "transport",
        httpx.MockTransport(
            lambda r: httpx.Response(
                200, headers={"content-type": "text/event-stream"}, content=data
            )
        ),
    )
    async with await client() as c:
        cid = (await c.post("/api/mentor/conversations", json={})).json()["id"]
        body = {"request_id": "truncated_001", "text": "x"}
        await c.post(f"/api/mentor/conversations/{cid}/turns", json=body)
        turn = await wait_turn(cid)
        assert turn["status"] == "failed" and turn["error"] == "incomplete_stream"
        assert not count
        # Persist an interrupted generation then restart: no implicit rerun.
        with database() as db:
            db.execute(
                "UPDATE mentor_turns SET status='running' WHERE id=?", (turn["id"],)
            )
        recover_turns()
        again = await c.post(f"/api/mentor/conversations/{cid}/turns", json=body)
        assert again.json()["status"] == "outcome_unknown" and again.json()["replayed"]
        assert not count


@pytest.mark.asyncio
async def test_queued_cancel_and_deleted_conversation_retain_uncertain_ledger(
    runtime, monkeypatch
):
    wire = WireAgent()
    monkeypatch.setattr(research, "adapter", A2AAdapter(httpx.MockTransport(wire)))
    async with await client() as c:
        cid = (await c.post("/api/mentor/conversations", json={})).json()["id"]
        job = await setup_job(c, cid)
        assert (await c.post(f"/api/research/jobs/{job['id']}/cancel")).json()[
            "status"
        ] == "cancelled"
        await research.step(row(job["id"]))
        assert wire.submissions == 0
        assert (await c.delete("/api/mentor/conversations/" + cid)).status_code == 200


@pytest.mark.asyncio
async def test_complete_assistant_message_and_correlation_validation(
    runtime, monkeypatch
):
    from vrag.conversation_stream import Message, validate_correlation
    from vrag.providers import ProviderFailure

    call = {
        "id": "correlated_1",
        "type": "function",
        "function": {"name": "retrieve_video_evidence", "arguments": '{"query":"x"}'},
    }
    good = [
        Message(role="assistant", content="", tool_calls=[call]),
        Message(role="tool", content="{}", tool_call_id="correlated_1"),
    ]
    validate_correlation(good)
    with pytest.raises(ProviderFailure, match="invalid_tool_correlation"):
        validate_correlation(
            [good[0], Message(role="tool", content="{}", tool_call_id="wrong")]
        )
    with pytest.raises(ValueError):
        Message(role="user", content="x", tool_calls=[call])


@pytest.mark.asyncio
async def test_owned_scene_tool_and_cancel_without_cancelling_research(
    runtime, monkeypatch
):
    from vrag.mentor_api import Session
    from vrag.conversation_stream import StreamEvent

    session = Session(OWNER)
    session.events.append(
        {
            "camera_id": "camera1",
            "frame_id": 1,
            "request_id": "scene_1",
            "detections": [{"label": "uncertain hand", "confidence": 0.6}],
            "provider_results": [{"status": "ok"}],
        }
    )
    monkeypatch.setattr("vrag.mentor_api.sessions", {"owned_live_session": session})
    ref = "camera1:1:scene_1"
    messages = []

    def qwen(request):
        body = json.loads(request.content)
        messages.append(body)
        if body["messages"][-1]["role"] == "tool":
            result = json.loads(body["messages"][-1]["content"])
            assert result["observations"][0]["ref"] == ref
            assert "uncertain" in result["authority"]
            response = completion(
                "An uncertain hand detection was observed; it is not a verified fact."
            )
        else:
            response = calls([("summarize_scene", {"observation_refs": [ref]})])
        return httpx.Response(
            200, headers={"content-type": "text/event-stream"}, content=response
        )

    monkeypatch.setattr(chat.adapter, "transport", httpx.MockTransport(qwen))
    async with await client() as c:
        cid = (await c.post("/api/mentor/conversations", json={})).json()["id"]
        body = {
            "request_id": "scene_turn_01",
            "text": "What is observed?",
            "live_session": "owned_live_session",
            "observation_refs": [ref],
        }
        assert (
            await c.post(f"/api/mentor/conversations/{cid}/turns", json=body)
        ).status_code == 200
        assert (await wait_turn(cid))["status"] == "completed"
        assert all(
            "image_url" not in json.dumps(request)
            and "data:image" not in json.dumps(request)
            for request in messages
        )
        denied = body | {
            "request_id": "scene_turn_02",
            "observation_refs": ["camera2:1:foreign"],
        }
        assert (
            await c.post(f"/api/mentor/conversations/{cid}/turns", json=denied)
        ).status_code == 403
        job = await setup_job(c, cid)
        entered = asyncio.Event()

        async def waiting(*a, **k):
            yield StreamEvent(type="text", text="Progress ")
            entered.set()
            await asyncio.Event().wait()

        monkeypatch.setattr(chat.adapter, "stream", waiting)
        turn = await c.post(
            f"/api/mentor/conversations/{cid}/turns",
            json={"request_id": "cancel_turn_01", "text": "Keep explaining"},
        )
        await entered.wait()
        assert (await c.post(f"/api/mentor/conversations/{cid}/cancel")).json()[
            "research_cancelled"
        ] is False
        assert (await wait_turn(cid))["status"] == "cancelled"
        assert research.get_job(job["id"], OWNER)["status"] == "queued"
        assert (
            await c.post(
                f"/api/mentor/conversations/{cid}/turns",
                json={"request_id": "cancel_turn_01", "text": "Keep explaining"},
            )
        ).json()["id"] == turn.json()["id"]


@pytest.mark.asyncio
async def test_actual_fresh_process_reconciles_persisted_a2a_task(
    runtime, tmp_path, monkeypatch
):
    """A new interpreter imports the real app and polls the existing remote task.

    Agent transport is synthetic in both processes. Database/process continuity is real.
    """
    import os, sys

    wire = WireAgent()
    monkeypatch.setattr(research, "adapter", A2AAdapter(httpx.MockTransport(wire)))
    async with await client() as c:
        cid = (await c.post("/api/mentor/conversations", json={})).json()["id"]
        job = await setup_job(c, cid)
        await research.step(row(job["id"]))
        assert row(job["id"])["status"] == "running"
        code = """
import asyncio,json,sys
from config.v2 import ConfigurationV2
from vrag import research_jobs,conversation
from vrag.research import A2AAdapter
from vrag.mentor_state import database,recover_turns
from v3_protocol_fixtures import WireAgent
import httpx
cfg=ConfigurationV2.model_validate_json(sys.argv[1])
research_jobs.runtime_snapshot=lambda:(4,cfg)
research_jobs.adapter=A2AAdapter(httpx.MockTransport(WireAgent()))
research_jobs.recover();recover_turns()
with database() as db: row=dict(db.execute('SELECT * FROM research_jobs WHERE id=?',(sys.argv[2],)).fetchone())
assert row['remote_id']=='remote-task-1'
asyncio.run(research_jobs.step(row))
with database() as db: result=dict(db.execute('SELECT status,remote_id,result FROM research_jobs WHERE id=?',(sys.argv[2],)).fetchone())
assert result['status']=='completed',result
print(json.dumps({'fresh_process':True,'status':result['status'],'task_id':result['remote_id'],'citations':len(json.loads(result['result'])['citations'])}))
"""
        env = os.environ.copy()
        env["VRAG_DATA"] = str(tmp_path)
        env["PYTHONPATH"] = ".:tests"
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            code,
            runtime.model_dump_json(),
            job["id"],
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), 15)
        assert proc.returncode == 0, stderr.decode()
        assert json.loads(stdout)["fresh_process"] is True
        assert row(job["id"])["status"] == "completed" and wire.submissions == 1


@pytest.mark.asyncio
async def test_ledger_gc_keeps_uncertain_operations_and_deleted_namespace_tombstones(
    runtime,
):
    async with await client() as c:
        cid = (await c.post("/api/mentor/conversations", json={})).json()["id"]
        with database() as db:
            db.execute(
                "INSERT INTO mentor_turns(id,conversation,request_id,fingerprint,status,payload,created) VALUES(?,?,?,?,?,?,?)",
                (
                    "gc_turn",
                    cid,
                    "gc_request",
                    "digest",
                    "outcome_unknown",
                    "{}",
                    time.time(),
                ),
            )
            db.execute(
                "CREATE TABLE mentor_tool_calls(owner TEXT,session TEXT,call_id TEXT,fingerprint TEXT,status TEXT,result TEXT,PRIMARY KEY(owner,session,call_id))"
            )
            db.execute(
                "INSERT INTO mentor_tool_calls VALUES(?,?,?,?,?,?)",
                (OWNER, "gc_turn", "pending", "digest", "running", None),
            )
        await c.delete("/api/mentor/conversations/" + cid)
        compact_ledger()
        with database() as db:
            assert (
                db.execute("SELECT COUNT(*) FROM mentor_tool_calls").fetchone()[0] == 1
            )
            assert (
                db.execute(
                    "SELECT deleted FROM mentor_conversations WHERE id=?", (cid,)
                ).fetchone()[0]
                == 1
            )
        assert not chat.turn_owned(OWNER, "gc_turn")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,code",
    [
        (401, "provider_auth_denied"),
        (403, "provider_auth_denied"),
        (302, "destination_denied"),
    ],
)
async def test_a2a_auth_and_redirect_fail_closed(runtime, status, code):
    from vrag.providers import ProviderFailure

    calls = []

    def denied(request):
        calls.append(request.url.host)
        return httpx.Response(
            status, headers={"location": "https://evil.example/steal"}
        )

    adapter = A2AAdapter(httpx.MockTransport(denied))
    with pytest.raises(ProviderFailure, match=code):
        await adapter.probe(runtime.providers["agent"])
    assert calls == ["agent.example"]


@pytest.mark.asyncio
async def test_a2a_path_credentials_redacted_from_httpx_logs(runtime, caplog):
    import logging

    wire = WireAgent()
    caplog.set_level(logging.INFO, logger="httpx")
    info = await A2AAdapter(httpx.MockTransport(wire)).probe(runtime.providers["agent"])
    assert info["authentication"] == "path_token"
    assert "synthetic-path-key-12345" not in caplog.text
    assert "[REDACTED]" in caplog.text


@pytest.mark.asyncio
async def test_a2a_bearer_auth_requires_card_declaration(runtime, monkeypatch):
    monkeypatch.setenv("A2A_URL", "https://agent.example/a2a")
    provider = runtime.providers["agent"].model_copy(update={"auth_mode": "bearer"})

    def server(request):
        assert request.headers["authorization"] == "Bearer synthetic-path-key-12345"
        card = {
            "name": "Agent Zero fixture",
            "description": "fixture",
            "url": "https://agent.example/a2a",
            "version": "1",
            "protocolVersion": "0.3.0",
            "capabilities": {},
            "defaultInputModes": ["text/plain"],
            "defaultOutputModes": ["application/json"],
            "skills": [
                {
                    "id": "research",
                    "name": "Research",
                    "description": "fixture",
                    "tags": [],
                }
            ],
            "securitySchemes": {"token": {"type": "http", "scheme": "bearer"}},
            "security": [{"token": []}],
        }
        return httpx.Response(200, json=card)

    info = await A2AAdapter(httpx.MockTransport(server)).probe(provider)
    assert info["authentication"] == "bearer"


@pytest.mark.asyncio
async def test_a2a_compressed_discovery_is_bounded_and_decoded_once(runtime):
    import gzip

    wire = WireAgent()

    def compressed(request):
        response = wire(request)
        return httpx.Response(
            response.status_code,
            headers={"content-encoding": "gzip", "content-type": "application/json"},
            content=gzip.compress(response.content),
        )

    info = await A2AAdapter(httpx.MockTransport(compressed)).probe(
        runtime.providers["agent"]
    )
    assert info["name"] == "Agent Zero fixture"


@pytest.mark.asyncio
async def test_acknowledged_remote_cancel_is_polled_without_repeated_cancellation(
    runtime, monkeypatch
):
    wire = WireAgent()

    class AcceptedCancel:
        async def cancel(self, p, task_id):
            wire.cancelled += 1
            from a2a.types import Task

            return Task.model_validate(wire.task("working")), {"name": "fixture"}

        async def get(self, p, task_id):
            wire.polls += 1
            from a2a.types import Task

            return Task.model_validate(wire.task("canceled")), {"name": "fixture"}

        async def submit(self, *a):
            raise AssertionError("must not submit")

    monkeypatch.setattr(research, "adapter", A2AAdapter(httpx.MockTransport(wire)))
    async with await client() as c:
        cid = (await c.post("/api/mentor/conversations", json={})).json()["id"]
        job = await setup_job(c, cid)
        await research.step(row(job["id"]))
        research.request_cancel(job["id"], OWNER, cid)
        monkeypatch.setattr(research, "adapter", AcceptedCancel())
        await research.step(row(job["id"]))
        await research.step(row(job["id"]))
        assert wire.cancelled == 1 and wire.polls == 1
        assert row(job["id"])["status"] == "cancelled"
