"""Isolated loopback browser test server. NEVER deploy this fixture.

Run only with disposable VRAG_DATA / VM_STATE_DIR and VM_V3_FIXTURE=true.
The actual HTTP/upload/FFmpeg/SQLite/index paths run; inference is deterministic.
"""
import os
if os.environ.get('VM_V3_FIXTURE') != 'true' or not os.environ.get('VRAG_DATA', '').startswith('/tmp/v3-'):
    raise RuntimeError('This test fixture requires explicit opt-in and disposable /tmp/v3- state')
if os.environ.get('VM_BACKUP_ENABLED') != 'false':
    raise RuntimeError('Disable backups for the isolated fixture')
os.environ['VM_USER_TOKEN'] = 'v3-synthetic-fixture-user-token-000000'
from vrag.api import app  # noqa: E402,F401
from vrag.providers import Output  # noqa: E402
from vrag.settings import store  # noqa: E402
from config.schema import parse_yaml  # noqa: E402
import vrag.routing  # noqa: E402
store.history = [parse_yaml('''version: 1
profile: isolated-v3-synthetic-inference
providers:
  embedding:
    adapter: openai-embeddings
    model: synthetic-text-3d
    base_url_env: V3_FIXTURE_URL
    trust: approved_sensitive
    capabilities: [text_embeddings]
  speech:
    adapter: openai-transcription
    model: synthetic-transcript
    base_url_env: V3_FIXTURE_URL
    trust: approved_sensitive
    capabilities: [transcription]
features:
  rag.text_embeddings: {providers: [embedding]}
  audio.transcription: {providers: [speech]}
''')]
store.version = 1
os.environ['V3_FIXTURE_URL'] = 'https://fixture.invalid/v1'

async def synthetic_inference(name, provider, payload, sensitive):
    if name == 'embedding':
        return Output(embedding=[1, 0, 0])
    if name == 'speech' and payload.get('audio'):
        return Output(text='Synthetic recording evidence: clear the workbench.')
    raise RuntimeError('Unexpected fixture provider')

vrag.routing.adapter.call = synthetic_inference

# Gate 03/05 fixture: actual application lifecycle + official SDK JSON-RPC wire
# handling, with deterministic synthetic upstreams and no external calls.
import json
import httpx
from config.v2 import migrate,ProviderV2
from config.schema import Route
from vrag import conversation,research_jobs
from vrag.research import A2AAdapter
from v3_protocol_fixtures import WireAgent,calls,completion

cfg=migrate(store.history[0])
cfg.providers['qwen']=ProviderV2(adapter='openai-conversation',model='fixture-qwen',base_url_env='V3_CHAT_URL',capabilities=['conversation'],trust='approved_sensitive')
cfg.providers['agent']=ProviderV2(adapter='a2a',model='Agent Zero fixture',base_url_env='A2A_URL',api_key_secret='A2A_TOKEN',auth_mode='path_token',capabilities=['research_dispatch'],trust='approved_sensitive')
cfg.features['mentor.conversation']=Route(providers=['qwen'])
cfg.features['research.dispatch']=Route(providers=['agent'])
store.history=[cfg]
os.environ['V3_CHAT_URL']='https://models.example/v1'
os.environ['A2A_URL']='https://agent.example/a2a/t-{token}'
os.environ['A2A_TOKEN']='synthetic-path-key-12345'
os.environ['VM_ALLOWED_HOSTS']='fixture.invalid,models.example,agent.example'

wire=WireAgent()
research_jobs.adapter=A2AAdapter(httpx.MockTransport(wire))

def qwen_stream(request):
    body=json.loads(request.content)
    if body['messages'][-1]['role']=='tool':
        response=completion('The clip supports clearing the workbench. Research is running independently.')
    elif 'Incorporate' in body['messages'][-1]['content']:
        response=completion('Updated from completed research: clear the workbench. Source: https://docs.example/safety')
    else:
        response=calls([('retrieve_video_evidence',{'query':'workbench','k':1}),('dispatch_research',{'goal':'Research safe assembly','agent_id':'documentation_research'})])
    return httpx.Response(200,headers={'content-type':'text/event-stream'},content=response)
conversation.adapter.transport=httpx.MockTransport(qwen_stream)
