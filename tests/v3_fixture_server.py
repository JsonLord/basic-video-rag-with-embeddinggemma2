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
