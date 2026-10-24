"""Typed authenticated execution and idempotency boundary; handlers are registered by the conversation runtime."""
import asyncio
import hashlib
import inspect
import json
from typing import Literal
from pydantic import ConfigDict, Field, model_validator
from config.schema import Strict

class ToolFailure(Exception):
    pass

class Arguments(Strict):
    model_config=ConfigDict(extra='forbid',frozen=True,strict=True)

class DispatchResearch(Arguments):
    goal: str = Field(min_length=1,max_length=2000)
    agent_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,64}$')
    permitted_refs: list[str] = Field(default_factory=list,max_length=20)

class ResearchJob(Arguments):
    job_id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')

class RetrieveEvidence(Arguments):
    query: str = Field(min_length=1,max_length=1000)
    k: int = Field(default=5,ge=1,le=10)

class SummarizeScene(Arguments):
    observation_refs: list[str] = Field(min_length=1,max_length=20)

ARGUMENTS={'dispatch_research':DispatchResearch,'get_research_status':ResearchJob,
           'cancel_research':ResearchJob,'retrieve_video_evidence':RetrieveEvidence,
           'summarize_scene':SummarizeScene}

class ToolCall(Arguments):
    id: str = Field(pattern=r'^[a-zA-Z0-9_-]{1,100}$')
    name: Literal['dispatch_research','get_research_status','cancel_research','retrieve_video_evidence','summarize_scene']
    arguments: dict
    @model_validator(mode='after')
    def valid_arguments(self):
        ARGUMENTS[self.name].model_validate(self.arguments)
        if len(json.dumps(self.arguments).encode())>8192:raise ValueError('tool arguments too large')
        return self

class ToolContext(Arguments):
    owner: str = Field(pattern=r'^[a-f0-9]{64}$')
    session_id: str = Field(min_length=8,max_length=100)
    allow_research: bool = False
    agent_ids: list[str] = Field(default_factory=list,max_length=20)
    permitted_refs: list[str] = Field(default_factory=list,max_length=20)

class ToolRegistry:
    """Authenticated callbacks plus a bounded, restart-safe idempotency ledger.

    A pending/crashed operation is outcome_unknown, never blindly repeated.
    Registered handlers must themselves enforce owned evidence/job access. Real
    research handlers and reconciliation live in research_jobs; this boundary never dispatches by model-supplied URL.
    """
    def __init__(self,authorize,handlers=None,connect=None):
        if connect is None:
            from .jobs import connect as existing_database
            connect=existing_database
        self.authorize=authorize
        self.handlers=dict(handlers or {})
        if not set(self.handlers)<=set(ARGUMENTS):raise ValueError('unknown tool handler')
        self.connect=connect
        self.slots=asyncio.Semaphore(2)

    def definitions(self):
        return [{'type':'function','function':{'name':name,'description':'Bounded authenticated '+name,
                  'parameters':ARGUMENTS[name].model_json_schema()}} for name in sorted(self.handlers)]

    async def execute(self,call:ToolCall,context:ToolContext):
        authorized=self.authorize(context.owner,context.session_id)
        if inspect.isawaitable(authorized):authorized=await authorized
        if not authorized:raise ToolFailure('unauthorized')
        # Revalidate callers that used unsafe Pydantic model_copy/construct.
        call=ToolCall.model_validate(call.model_dump())
        context=ToolContext.model_validate(context.model_dump())
        args=ARGUMENTS[call.name].model_validate(call.arguments)
        refs=getattr(args,'permitted_refs',getattr(args,'observation_refs',[]))
        if not set(refs)<=set(context.permitted_refs):raise ToolFailure('privacy_denied')
        if call.name=='dispatch_research' and (not context.allow_research or args.agent_id not in context.agent_ids):
            raise ToolFailure('privacy_denied')
        if call.name not in self.handlers:raise ToolFailure('tool_unavailable')
        if self.slots.locked():raise ToolFailure('busy')
        fingerprint=hashlib.sha256(json.dumps({'name':call.name,'arguments':call.arguments},sort_keys=True).encode()).hexdigest()
        key=(context.owner,context.session_id,call.id)
        async with self.slots:
            with self.connect() as db:
                db.execute('CREATE TABLE IF NOT EXISTS mentor_tool_calls(owner TEXT,session TEXT,call_id TEXT,fingerprint TEXT,status TEXT,result TEXT,PRIMARY KEY(owner,session,call_id))')
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT fingerprint,status,result FROM mentor_tool_calls WHERE owner=? AND session=? AND call_id=?',key).fetchone()
                if row:
                    if row[0]!=fingerprint:raise ToolFailure('idempotency_conflict')
                    if row[1]!='complete':raise ToolFailure('outcome_unknown')
                    return json.loads(row[2])
                if db.execute('SELECT COUNT(*) FROM mentor_tool_calls').fetchone()[0]>=10000:raise ToolFailure('ledger_full')
                db.execute('INSERT INTO mentor_tool_calls VALUES(?,?,?,?,?,?)',(*key,fingerprint,'running',None))
            # Commit running before invoking a potentially irreversible external handler.
            try:
                result=await self.handlers[call.name](args,context)
                serialized=json.dumps(result,allow_nan=False)
                if len(serialized.encode())>32768:raise ToolFailure('tool_result_too_large')
            except asyncio.CancelledError:raise
            except Exception:
                # Never persist exception text or provider credentials/payloads.
                serialized=json.dumps({'status':'error','code':'tool_execution_failed'})
            with self.connect() as db:
                db.execute('UPDATE mentor_tool_calls SET status=?,result=? WHERE owner=? AND session=? AND call_id=?',('complete',serialized,*key))
            return json.loads(serialized)


def owned_session_registry(handlers=None):
    from .mentor_api import session_for
    return ToolRegistry(lambda owner,sid:session_for(sid,owner),handlers)
