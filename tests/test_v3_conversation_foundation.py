"""Gate 03 start: mock OpenAI SSE and authenticated handler fixtures, no live Qwen/A2A."""
import asyncio
import json
import sqlite3
import httpx
import pytest
from config.v2 import ProviderV2
from vrag.providers import Adapter, ProviderFailure
from vrag.conversation_stream import stream
from vrag.conversation_tools import ToolCall, ToolContext, ToolRegistry, ToolFailure

@pytest.fixture
def setup(tmp_path,monkeypatch):
    monkeypatch.setenv('OPENAI_COMPATIBLE_URL','https://models.example/v1')
    monkeypatch.setenv('OPENAI_COMPATIBLE_MODEL','qwen-synthetic')
    monkeypatch.setenv('OPENAI_COMPATIBLE_API_KEY','synthetic-stream-key')
    monkeypatch.setenv('VM_ALLOWED_HOSTS','models.example')
    monkeypatch.setattr('socket.getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))])
    p=ProviderV2(adapter='openai-conversation',model='candidate',model_env='OPENAI_COMPATIBLE_MODEL',base_url_env='OPENAI_COMPATIBLE_URL',api_key_secret='OPENAI_COMPATIBLE_API_KEY',trust='approved_sensitive',capabilities=['conversation'])
    def connect():return sqlite3.connect(tmp_path/'tools.sqlite',timeout=5)
    context=ToolContext(owner='a'*64,session_id='session-fixture',permitted_refs=['camera1:1'],agent_ids=['approved-agent'])
    return p,connect,context


def packet(delta=None,finish=None):
    return 'data: '+json.dumps({'choices':[{'index':0,'delta':delta or {},'finish_reason':finish}]})+'\n\n'

class Chunks(httpx.AsyncByteStream):
    def __init__(self,values):self.values=values;self.closed=False
    async def __aiter__(self):
        for value in self.values:
            yield value.encode()
            await asyncio.sleep(0)
    async def aclose(self):self.closed=True

@pytest.mark.asyncio
async def test_fragmented_text_and_tool_calls_are_not_executed_by_stream(setup):
    p,connect,context=setup;executed=[]
    async def retrieve(args,ctx):executed.append(args.query);return {'citations':[{'ref':'fixture-video','timestamp':2}]}
    registry=ToolRegistry(lambda owner,sid:True,{'retrieve_video_evidence':retrieve},connect)
    content=packet({'content':'Grounded '})+packet({'content':'answer.'})+packet({'tool_calls':[{'index':0,'id':'call_1','type':'function','function':{'name':'retrieve_video_evidence','arguments':'{"query":'}}]})+packet({'tool_calls':[{'index':0,'function':{'arguments':'"workbench"}'}}]},'tool_calls')+'data: [DONE]\n\n'
    transport=Chunks([content[:47],content[47:101],content[101:]])
    def reply(request):
        body=json.loads(request.content)
        assert request.url.path=='/v1/chat/completions' and body['model']=='qwen-synthetic' and body['stream']
        assert request.headers['authorization']=='Bearer synthetic-stream-key'
        assert body['tools'][0]['function']['name']=='retrieve_video_evidence'
        return httpx.Response(200,headers={'Content-Type':'text/event-stream'},stream=transport)
    events=[e async for e in Adapter(httpx.MockTransport(reply)).stream('qwen',p,[{'role':'user','content':'question'}],registry)]
    assert ''.join(e.text for e in events)=='Grounded answer.' and events[-1].type=='done'
    assert transport.closed and executed==[]
    call=next(e.call for e in events if e.type=='tool_call')
    result=await registry.execute(call,context)
    assert result['citations'][0]['timestamp']==2 and executed==['workbench']
    # Restart with the same database: no duplicate handler side effect.
    again=ToolRegistry(lambda owner,sid:True,{'retrieve_video_evidence':retrieve},connect)
    assert await again.execute(call,context)==result and executed==['workbench']
    with pytest.raises(ToolFailure,match='idempotency_conflict'):
        await again.execute(call.model_copy(update={'arguments':{'query':'changed'}}),context)

@pytest.mark.asyncio
@pytest.mark.parametrize('scenario',['truncated','invalid-arguments','unknown-tool','duplicate-id','oversize'])
async def test_invalid_stream_never_emits_executable_tool_call(setup,scenario):
    p,connect,context=setup
    async def handler(*args):pytest.fail('stream must not execute tools')
    registry=ToolRegistry(lambda *a:True,{'retrieve_video_evidence':handler},connect)
    name='arbitrary_network_request' if scenario=='unknown-tool' else 'retrieve_video_evidence'
    args='{"query":"x","url":"https://unapproved.invalid"}' if scenario=='invalid-arguments' else '{"query":"x"}'
    calls=[{'index':0,'id':'call_1','function':{'name':name,'arguments':args}}]
    if scenario=='duplicate-id':calls.append({'index':1,'id':'call_1','function':{'name':name,'arguments':args}})
    content=packet({'tool_calls':calls},'tool_calls')
    if scenario!='truncated':content+='data: [DONE]\n\n'
    if scenario=='oversize':content='data: '+('x'*65537)+'\n\n'
    a=Adapter(httpx.MockTransport(lambda r:httpx.Response(200,headers={'content-type':'text/event-stream'},content=content)))
    emitted=[]
    with pytest.raises(ProviderFailure):
        async for event in stream(a,'q',p,[{'role':'user','content':'x'}],registry):emitted.append(event)
    assert not any(e.type=='tool_call' for e in emitted)

@pytest.mark.asyncio
async def test_auth_privacy_unknown_handlers_and_revoked_access(setup):
    p,connect,context=setup;count=[]
    async def dispatch(args,ctx):count.append(args.goal);return {'status':'queued','job_id':'synthetic-only'}
    allowed=True
    registry=ToolRegistry(lambda *a:allowed,{'dispatch_research':dispatch},connect)
    call=ToolCall(id='research_1',name='dispatch_research',arguments={'goal':'bounded research','agent_id':'approved-agent','permitted_refs':['camera1:1']})
    with pytest.raises(ToolFailure,match='privacy_denied'):await registry.execute(call,context)
    assert not count
    authorized=context.model_copy(update={'allow_research':True})
    assert (await registry.execute(call,authorized))['status']=='queued'
    allowed=False
    with pytest.raises(ToolFailure,match='unauthorized'):await registry.execute(call,authorized)
    assert len(count)==1
    missing=ToolRegistry(lambda *a:True,connect=connect)
    with pytest.raises(ToolFailure,match='tool_unavailable'):
        await missing.execute(ToolCall(id='get_1',name='get_research_status',arguments={'job_id':'job_1'}),context)

@pytest.mark.asyncio
async def test_canceled_handler_stays_outcome_unknown_after_restart(setup):
    p,connect,context=setup;entered=asyncio.Event();count=[]
    async def retrieve(*args):count.append(1);entered.set();await asyncio.Event().wait()
    registry=ToolRegistry(lambda *a:True,{'retrieve_video_evidence':retrieve},connect)
    call=ToolCall(id='pending_1',name='retrieve_video_evidence',arguments={'query':'x'})
    pending=asyncio.create_task(registry.execute(call,context));await entered.wait();pending.cancel()
    with pytest.raises(asyncio.CancelledError):await pending
    restarted=ToolRegistry(lambda *a:True,{'retrieve_video_evidence':retrieve},connect)
    with pytest.raises(ToolFailure,match='outcome_unknown'):await restarted.execute(call,context)
    assert count==[1]

@pytest.mark.asyncio
async def test_stream_cancel_releases_transport_and_concurrency(setup):
    p,connect,context=setup;entered=asyncio.Event();closed=[]
    class Waiting(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set();await asyncio.Event().wait();yield b''
        async def aclose(self):closed.append(True)
    a=Adapter(httpx.MockTransport(lambda r:httpx.Response(200,headers={'content-type':'text/event-stream'},stream=Waiting())))
    async def consume():return [e async for e in stream(a,'q',p,[{'role':'user','content':'x'}])]
    task=asyncio.create_task(consume());await entered.wait();task.cancel()
    with pytest.raises(asyncio.CancelledError):await task
    assert closed and not a.limits[('q',p.concurrency)].locked()

@pytest.mark.asyncio
@pytest.mark.parametrize('status',[401,403,302])
async def test_stream_authorization_and_redirect_fail_closed(setup,status):
    p,connect,context=setup;calls=[]
    def reply(request):calls.append(request);return httpx.Response(status,headers={'location':'https://unapproved.invalid'})
    with pytest.raises(ProviderFailure):
        async for event in stream(Adapter(httpx.MockTransport(reply)),'q',p,[{'role':'user','content':'x'}]):pass
    assert len(calls)==1


# Real encryption with mock GitHub storage also preserves the tool idempotency ledger.
from test_github_checkpoints import encrypted, make_library

@pytest.mark.asyncio
async def test_tool_idempotency_survives_encrypted_destructive_restore(setup,encrypted,tmp_path):
    import shutil
    p,_,context=setup
    backup,remote=encrypted
    root=tmp_path/'source';data,state=make_library(root)
    def connect():return sqlite3.connect(data/'jobs.sqlite')
    count=[]
    async def retrieve(args,ctx):count.append(1);return {'citation':'v1:0'}
    call=ToolCall(id='backed_call',name='retrieve_video_evidence',arguments={'query':'evidence'})
    registry=ToolRegistry(lambda *a:True,{'retrieve_video_evidence':retrieve},connect)
    assert await registry.execute(call,context)=={'citation':'v1:0'}
    stage=tmp_path/'stage';stage.mkdir();backup.capture(data,state,stage);backup.backup(stage)
    shutil.rmtree(root);shutil.rmtree(stage)
    backup.restore(tmp_path/'restored')
    restarted=ToolRegistry(lambda *a:True,{'retrieve_video_evidence':retrieve},lambda:sqlite3.connect(tmp_path/'restored/data/jobs.sqlite'))
    assert await restarted.execute(call,context)=={'citation':'v1:0'} and count==[1]
