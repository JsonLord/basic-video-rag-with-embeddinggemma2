"""Versioned configuration and live contracts; raw media is processed in memory only."""
import asyncio
import base64
from collections import deque
from datetime import datetime, timezone
import hashlib
import hmac
import io
import os
import secrets
import time
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response
from PIL import Image, UnidentifiedImageError
from pydantic import Field, ValidationError
import yaml

from config.schema import Strict, parse_yaml, parse_configuration
from .providers import Decision, Detection, ProviderFailure, destination, resolved_provider
from .routing import route
from .settings import store

router = APIRouter()

def auth(request: Request, admin=False):
    expected = os.environ.get('VM_ADMIN_TOKEN' if admin else 'VM_USER_TOKEN', '')
    value = request.headers.get('authorization', '')
    if not value and not admin and request.method in ('GET','HEAD') and request.url.path.startswith('/media/'):
        value = 'Bearer ' + request.cookies.get('vm-media','')
    if not expected or len(expected) < 24 or not hmac.compare_digest(value.encode('utf-8'), ('Bearer ' + expected).encode('utf-8')):
        raise HTTPException(401, 'configure a server token (at least 24 characters) and authenticate')
    # Bearer authorization avoids ambient-cookie CSRF. Also reject cross-origin browser requests.
    origin = request.headers.get('origin')
    if origin:
        allowed = set(filter(None, os.environ.get('VM_ALLOWED_ORIGINS', '').split(',')))
        forwarded = request.headers.get('x-forwarded-host') if request.client and request.client.host in ('127.0.0.1', '::1', 'testclient') else None
        host = forwarded or request.headers.get('host', '')
        if (allowed and origin not in allowed) or (not allowed and origin not in ('https://' + host, 'http://' + host)):
            raise HTTPException(403, 'origin denied')
    return hashlib.sha256(value.encode()).hexdigest()

def admin(request: Request):
    return auth(request, True)

def user(request: Request):
    return auth(request)

class ConfigInput(Strict):
    yaml: str = Field(max_length=65536)
    expected_version: int = Field(default=1, ge=1)

class MigrationInput(ConfigInput):
    include_environment_defaults: bool = False

class Rollback(Strict):
    version: int = Field(ge=1)
    expected_version: int = Field(ge=1)

class DryRunInput(Strict):
    feature: str = Field(min_length=1, max_length=100)
    camera_id: str = Field(default="camera1", pattern="^camera[12]$")

class SessionInput(Strict):
    consent: bool

class FrameInput(Strict):
    camera_id: str = Field(pattern='^camera[12]$')
    frame_id: int = Field(ge=0, le=9007199254740991)
    captured_at: float = Field(ge=0, allow_inf_nan=False)
    image: str = Field(max_length=1500000)
    feature: str = Field(min_length=1, max_length=100)
    config_version: int = Field(ge=1)
    routing_revision: int | None = Field(default=None,ge=0)
    request_id: str = Field(max_length=100)

class ProviderStatus(Strict):
    provider: str
    status: str
    latency_ms: int
    capability_version: int = 1
    frame_id: int | None = None
    camera_id: str | None = None
    captured_at: float | None = None
    config_version: int | None = None

class Observation(Strict):
    schema_version: int = 1
    history_revision: int = 1
    routing_revision: int = 0
    session_id: str
    camera_id: str
    frame_id: int
    captured_at: float
    request_id: str
    config_version: int
    observed_at: datetime
    source_width: int
    source_height: int
    detections: list[Detection]
    decisions: list[Decision]
    provider_results: list[ProviderStatus]
    warnings: list[str]

class AudioInput(Strict):
    audio: str = Field(max_length=2800000)
    duration_ms: int = Field(ge=1, le=15000)

class Session:
    def __init__(self, owner):
        self.owner = owner
        self.expiry = time.monotonic() + 1800
        self.last = {}
        self.busy = set()
        self.rate = {}
        self.events = deque(maxlen=20)
        self.task = {'goal':'', 'step':'Observe', 'completed':False}
        self.last_transcript = ''
        self.overrides = {}
        self.routing_revision = 0

sessions = {}

def reap_sessions():
    now = time.monotonic()
    for sid in list(sessions):
        if sessions[sid].expiry <= now:
            del sessions[sid]

async def session_cleanup():
    while True:
        reap_sessions()
        await asyncio.sleep(30)

def session_for(sid, owner):
    reap_sessions()
    s = sessions.get(sid)
    if not s or s.owner != owner:
        raise HTTPException(404, 'session expired or unavailable')
    return s

@router.get('/api/health')
def health():
    return {'status': 'ok', 'api_version': 1, 'inference': 'remote-only', 'config_version': store.version,
            'configuration': 'state-directory-configured' if store.path else 'read-only-defaults',
            'providers_configured': len(store.history[-1].providers), 'sessions': 'ephemeral'}

def provider_host(p):
    from urllib.parse import urlsplit
    try:
        return urlsplit(os.environ.get(p.base_url_env, '')).hostname
    except ValueError:
        return None

def runtime_snapshot():
    from .runtime_config import with_environment_defaults
    version,cfg=store.snapshot()
    try:return version,with_environment_defaults(cfg)
    except ProviderFailure as exc:raise HTTPException(422,exc.code) from None

@router.get('/api/providers')
def providers(owner=Depends(user)):
    version, cfg = runtime_snapshot()
    return {'schema_version':cfg.version,'history_revision':version,'config_version': version, 'providers': {k: {'label': p.label, 'adapter': p.adapter, 'model': p.model,
            'capabilities': p.capabilities, 'trust': p.trust, 'credential_present': bool(os.environ.get(p.api_key_secret, '')) if p.api_key_secret else True,
            'destination': provider_host(p),
            'capability_version':getattr(p,'capability_version',1),
            'protocol_verified':p.adapter not in ('a2a','openai-conversation'), 'live_status': 'not_checked'} for k,p in cfg.providers.items()},
            'features': {k: v.model_dump() for k,v in cfg.features.items()}}

@router.get('/api/config')
def get_config(owner=Depends(admin)):
    version, cfg = store.snapshot()
    from .runtime_config import environment_summary
    from config.v2 import FEATURE_ROLES
    models={}
    for name,p in cfg.providers.items():
        try:models[name]={'model':resolved_provider(p).model,'configured':True}
        except ProviderFailure:models[name]={'model':p.model,'configured':False}
    return {'schema_version':cfg.version,'history_revision':version,'roles':FEATURE_ROLES,
            'environment_defaults':environment_summary(),'models':models,
            'config_version': version, 'yaml': yaml.safe_dump(store.serialized_revision(version), sort_keys=False),
            'history': list(range(1, version+1)), 'writable': bool(store.path), 'config':cfg.model_dump(),
            'destinations':{k:('https://'+provider_host(p) if provider_host(p) else None) for k,p in cfg.providers.items()},
            'credentials':{k:bool(os.environ.get(p.api_key_secret,'')) if p.api_key_secret else True for k,p in cfg.providers.items()}}


@router.post('/api/config/migrate')
async def migrate_config(body: MigrationInput, owner=Depends(admin)):
    from config.v2 import migrate
    from .runtime_config import with_environment_defaults
    # Preview only: explicit CAS apply is a separate operation.
    try:
        cfg=migrate(parse_yaml(body.yaml))
        if body.include_environment_defaults:cfg=with_environment_defaults(cfg)
    except Exception:
        raise HTTPException(422,'Migration configuration invalid; check schema and approved environment defaults') from None
    return {'schema_version':2,'history_revision':store.version,'config_version':store.version,
            'persisted':False,'yaml':yaml.safe_dump(cfg.model_dump(),sort_keys=False)}

@router.get('/api/config/history/{revision}')
def export_revision(revision:int,owner=Depends(admin)):
    if not 1<=revision<=store.version:raise HTTPException(404,'unknown revision')
    raw=store.serialized_revision(revision)
    return {'schema_version':raw.get('version',1),'history_revision':revision,
            'yaml':yaml.safe_dump(raw,sort_keys=False),'config':raw}

@router.get('/api/config/template')
def template(owner=Depends(admin)):
    from pathlib import Path
    return Response((Path(__file__).parent.parent/'config/examples/disabled.yaml').read_text(), media_type='application/yaml', headers={'Content-Disposition': 'attachment; filename=visual-mentor.yaml'})

async def validate(text):
    try:
        cfg = parse_yaml(text)
    except ValidationError as exc:
        known = {'version','profile','providers','features','adapter','base_url_env','api_key_secret','model','capabilities','trust','timeout_ms','concurrency','strategy','result_policy','quorum','fusion','enabled','conditions','cameras','privacy','record_video','analysis_fps','width','height'}
        errors = ['.'.join(str(k) if k in known else '<entry>' for k in e['loc']) + ': ' + e['type'] for e in exc.errors(include_input=False, include_context=False)][:8]
        raise HTTPException(422, 'Configuration schema errors: ' + '; '.join(errors)) from None
    except Exception:
        # Never echo YAML or validation input (it may contain pasted secrets).
        raise HTTPException(422, 'Invalid YAML/schema: use unique keys, no aliases, known providers and compatible capabilities; check template') from None
    active = {pid for rule in cfg.features.values() if rule.enabled for pid in rule.providers}
    for pid in active:
        try:
            await destination(resolved_provider(cfg.providers[pid]), False)
        except ProviderFailure:
            raise HTTPException(422, 'Provider endpoint missing or denied: configure HTTPS public host in VM_ALLOWED_HOSTS and endpoint environment variable') from None
    return cfg

@router.get('/api/config/profiles')
def profiles(owner=Depends(admin)):
    from pathlib import Path
    directory = Path(__file__).parent.parent/'config/examples'
    return {p.stem:p.read_text() for p in directory.glob('*.yaml')}

@router.post('/api/config/validate')
async def validate_config(body: ConfigInput, owner=Depends(admin)):
    cfg = await validate(body.yaml)
    old = store.history[-1].model_dump()
    new = cfg.model_dump()
    return {'valid': True, 'config_version': store.version, 'changed_sections': [k for k in new if new[k] != old.get(k)], 'profile': cfg.profile}

@router.post('/api/config/apply')
async def apply_config(body: ConfigInput, owner=Depends(admin)):
    cfg = await validate(body.yaml)
    try:
        version = await store.apply(cfg, body.expected_version)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return {'schema_version':cfg.version,'history_revision':version,'config_version': version, 'profile': cfg.profile}

@router.post('/api/config/rollback')
async def rollback(body: Rollback, owner=Depends(admin)):
    if body.version > len(store.history):
        raise HTTPException(404, 'unknown version')
    cfg = store.history[body.version-1]
    # Endpoints may have changed since this version was saved; validate again.
    await validate(yaml.safe_dump(cfg.model_dump()))
    try:
        version = await store.apply(cfg, body.expected_version)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return {'config_version': version, 'restored_version': body.version}

@router.post('/api/providers/{pid}/test')
async def test_provider(pid: str, owner=Depends(admin)):
    from .providers import adapter
    _, cfg = runtime_snapshot()
    if pid not in cfg.providers:
        raise HTTPException(404, 'unknown provider')
    p = cfg.providers[pid]
    # Only a synthetic image/text; microphone tests require an explicit bounded clip in a live session.
    if p.adapter == 'a2a':
        from .research import adapter as research_adapter
        return {'provider':pid,'status':'agent_card_verified','inference_tested':False,**await research_adapter.probe(p)}
    if p.adapter == 'openai-conversation':
        from .conversation_probe import probe
        return await probe(pid,p)
    if p.adapter == 'openai-transcription':
        raise HTTPException(409, 'Use an explicitly enabled live audio clip to test transcription')
    image = Image.new('RGB', (32,32), 'white')
    out = io.BytesIO(); image.save(out, format='JPEG')
    payload = {'text': 'Synthetic connection test. Respond with OK.', 'image': 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode(), 'camera_id': 'test', 'frame_id': 0, 'width':32, 'height':32}
    if p.adapter in ('openai-chat-vision','openai-conversation') and 'image_understanding' not in p.capabilities:
        payload.pop('image')
    start = time.monotonic()
    await adapter.call(pid, p, payload, False)
    return {'provider': pid, 'status':'ok', 'latency_ms': round((time.monotonic()-start)*1000), 'synthetic': True}

@router.post('/api/routing/dry-run')
async def dry_run(body: DryRunInput, owner=Depends(admin)):
    _, cfg = runtime_snapshot()
    f = io.BytesIO(); Image.new('RGB', (32,32), 'white').save(f, format='JPEG')
    payload = {'text':'Synthetic routing test; no real camera data.',
        'camera_id':body.camera_id, 'frame_id':0, 'width':32, 'height':32}
    if body.feature.startswith('live.'):
        payload['image']='data:image/jpeg;base64,' + base64.b64encode(f.getvalue()).decode()
    out, statuses = await route(cfg, body.feature, payload, False)
    return {'synthetic':True, 'provider_results':statuses, 'detections':[d.model_dump() for d in out.detections], 'decisions':[d.model_dump() for d in out.decisions]}

async def disconnectable(request, operation):
    task = asyncio.create_task(operation)
    try:
        while not task.done():
            done, _ = await asyncio.wait({task}, timeout=0.25)
            if done:
                break
            if await request.is_disconnected():
                task.cancel()
                raise HTTPException(499, 'client disconnected')
        return await task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)

@router.post('/api/live/sessions')
async def create_session(body: SessionInput, owner=Depends(user)):
    if not body.consent:
        raise HTTPException(400, 'explicit transfer consent required')
    reap_sessions()
    if len(sessions) >= 32 or sum(s.owner == owner for s in sessions.values()) >= 4:
        raise HTTPException(429, 'session limit')
    sid = secrets.token_urlsafe(24)
    sessions[sid] = Session(owner)
    return {'session_id': sid, 'config_version': store.version, 'expires_in': 1800, 'retention': 'in-memory observations only'}

@router.delete('/api/live/sessions/{sid}')
async def delete_session(sid: str, owner=Depends(user)):
    session_for(sid, owner)
    del sessions[sid]
    return {'deleted': True}

@router.post('/api/live/sessions/{sid}/frames', response_model=Observation)
async def analyze_frame(sid: str, body: FrameInput, request: Request, owner=Depends(user)):
    s = session_for(sid, owner)
    version, cfg = runtime_snapshot()
    routing_revision=s.routing_revision
    if body.routing_revision is not None and body.routing_revision!=routing_revision:raise HTTPException(409,'session routing changed')
    if body.feature in s.overrides and s.overrides[body.feature][0]==version:
        cfg.features[body.feature]=s.overrides[body.feature][1]
    if body.config_version != version:
        raise HTTPException(409, 'configuration changed; refresh session routing')
    if not body.feature.startswith(f'live.{body.camera_id}.') and body.feature != 'live.visual_decision':
        raise HTTPException(422, 'feature must belong to this logical camera')
    if body.camera_id in s.busy:
        raise HTTPException(429, 'one analysis per camera is already in flight')
    if body.frame_id <= s.last.get(body.camera_id, -1):
        raise HTTPException(409, 'stale frame')
    if time.monotonic() - s.rate.get(body.camera_id, 0) < 0.5:
        raise HTTPException(429, 'maximum 2 FPS')
    try:
        prefix, encoded = body.image.split(',', 1)
        if prefix not in ('data:image/jpeg;base64', 'data:image/webp;base64'):
            raise ValueError()
        raw = base64.b64decode(encoded, validate=True)
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in ('JPEG','WEBP') or not (1 <= image.width <= 1920 and 1 <= image.height <= 1080):
                raise ValueError()
            width, height = image.size
            image.verify()
    except (ValueError, OSError, UnidentifiedImageError, Image.DecompressionBombError):
        raise HTTPException(422, 'invalid or oversized JPEG/WebP image') from None
    s.busy.add(body.camera_id)
    s.last[body.camera_id] = body.frame_id
    s.rate[body.camera_id] = time.monotonic()
    received = datetime.now(timezone.utc).isoformat()
    try:
        out, statuses = await disconnectable(request, route(cfg, body.feature, {**body.model_dump(), 'width':width, 'height':height}))
    finally:
        s.busy.discard(body.camera_id)
    # Deleting a session while an inference request is in flight discards its result.
    session_for(sid, owner)
    if s.routing_revision!=routing_revision:raise HTTPException(409,'session routing changed; discard observation')
    if store.version!=version:raise HTTPException(409,'configuration changed; discard observation')
    result = {'schema_version':cfg.version,'history_revision':version,'routing_revision':routing_revision,'session_id':sid, 'camera_id':body.camera_id, 'frame_id':body.frame_id, 'captured_at':body.captured_at,
              'request_id':body.request_id, 'config_version':version, 'observed_at':received,
              'source_width':width, 'source_height':height, 'detections':[d.model_dump() for d in out.detections],
              'decisions':[d.model_dump() for d in out.decisions], 'provider_results':statuses,
              'warnings':out.warnings + (['No successful provider result'] if not any(r['status']=='ok' for r in statuses) else [])}
    s.events.append(result)
    return result

@router.get('/api/live/sessions/{sid}/events')
async def events(sid: str, owner=Depends(user)):
    return list(session_for(sid, owner).events)

@router.post('/api/live/sessions/{sid}/transcribe')
async def transcribe(sid: str, body: AudioInput, request: Request, owner=Depends(user)):
    s = session_for(sid, owner)
    if 'audio' in s.busy:
        raise HTTPException(429, 'audio request in flight')
    if time.monotonic() - s.rate.get('audio', 0) < 2:
        raise HTTPException(429, 'audio rate limit')
    try:
        audio = base64.b64decode(body.audio, validate=True)
        if not audio or len(audio) > 2000000 or audio[:4] != b'\x1aE\xdf\xa3':
            raise ValueError()
    except ValueError:
        raise HTTPException(422, 'bounded WebM audio required') from None
    _, cfg = runtime_snapshot()
    s.busy.add('audio'); s.rate['audio'] = time.monotonic()
    try:
        out, statuses = await disconnectable(request, route(cfg, 'audio.transcription', {'audio':audio}))
    finally:
        s.busy.discard('audio')
    session_for(sid, owner)
    s.last_transcript = out.text[:8000]
    return {'text':out.text, 'provider_results':statuses, 'duration_ms':body.duration_ms}

@router.post('/api/live/sessions/{sid}/guidance')
async def guidance(sid: str, request: Request, owner=Depends(user)):
    s = session_for(sid, owner)
    if 'mentor' in s.busy or time.monotonic() - s.rate.get('mentor', 0) < 2:
        raise HTTPException(429, 'guidance rate limit')
    _, cfg = runtime_snapshot()
    s.busy.add('mentor'); s.rate['mentor'] = time.monotonic()
    try:
        out, statuses = await disconnectable(request, route(cfg, 'mentor.reasoning', {'text': 'Give cautious next-step guidance from these observations, identify uncertainty. No autonomous actions. ' + str(s.task) + ' Recent speech (untrusted): ' + s.last_transcript + str(list(s.events)[-5:])[:24000]}))
    finally:
        s.busy.discard('mentor')
    session_for(sid, owner)
    return {'guidance':out.text, 'provider_results':statuses, 'autonomous':False}


class TaskInput(Strict):
    goal: str = Field(max_length=1000)
    step: str = Field(max_length=500)
    completed: bool = False

@router.put('/api/live/sessions/{sid}/task')
async def task_state(sid: str, body: TaskInput, owner=Depends(user)):
    s = session_for(sid, owner)
    s.task = body.model_dump()
    return {'task':s.task, 'autonomous':False}

@router.post('/api/access')
def media_access(owner=Depends(user)):
    response=Response(status_code=204)
    response.set_cookie('vm-media', os.environ['VM_USER_TOKEN'], httponly=True, secure=True, samesite='strict', path='/media', max_age=3600)
    return response

@router.delete('/api/access')
def clear_media_access():
    response=Response(status_code=204)
    response.delete_cookie('vm-media',path='/media',secure=True,httponly=True,samesite='strict')
    return response

def backup_coordinator(request: Request):
    expected=os.environ.get('VM_BACKUP_TRIGGER_TOKEN','')
    value=request.headers.get('x-vm-backup-token','')
    if expected and len(expected)>=32 and hmac.compare_digest(value.encode(),expected.encode()):
        if request.headers.get('origin'):raise HTTPException(403,'coordinator does not accept browser origins')
        return 'backup-coordinator'
    return admin(request)

@router.get('/api/admin/backup-status')
def backup_status(owner=Depends(backup_coordinator)):
    from .backup.service import health
    return health()

@router.post('/api/admin/backup')
async def backup_trigger(owner=Depends(backup_coordinator)):
    from .backup.service import queue
    if not queue.request():raise HTTPException(409,'backup not configured')
    return {'accepted':True,'completed':False}

@router.post('/api/admin/backup/recovery-test')
async def backup_recovery_test(owner=Depends(admin)):
    from .backup.service import queue
    if not queue.request(recovery=True):raise HTTPException(409,'backup not configured')
    return {'accepted':True,'completed':False,'isolated':True}

class SessionRoutingInput(Strict):
    config_version: int = Field(ge=1)
    feature: str = Field(pattern=r'^live\.(camera[12]\.[a-zA-Z0-9_.-]+|visual_decision)$',max_length=100)
    route: dict

@router.put('/api/live/sessions/{sid}/routing')
async def session_routing(sid: str,body:SessionRoutingInput,owner=Depends(user)):
    from config.schema import Configuration, Route
    s=session_for(sid,owner)
    version,cfg=runtime_snapshot()
    if body.config_version!=version:raise HTTPException(409,'configuration changed')
    if len(s.overrides)>=8 and body.feature not in s.overrides:raise HTTPException(429,'session override limit')
    try:
        override=Route.model_validate(body.route)
        effective=cfg.model_dump()
        effective['features'][body.feature]=override.model_dump()
        parse_configuration(effective)
    except (ValueError,TypeError):raise HTTPException(422,'Invalid session route or provider capabilities') from None
    s.overrides[body.feature]=(version,override)
    s.routing_revision+=1
    features={k:v.model_dump() for k,v in cfg.features.items()}
    features.update({k:rule.model_dump() for k,(v,rule) in s.overrides.items() if v==version})
    return {'config_version':version,'routing_revision':s.routing_revision,'features':features,'persisted':False}
