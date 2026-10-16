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
from pydantic import Field
import yaml

from config.schema import Strict, parse_yaml
from .providers import ProviderFailure, destination
from .routing import route
from .settings import store

router = APIRouter()

def auth(request: Request, admin=False):
    expected = os.environ.get('VM_ADMIN_TOKEN' if admin else 'VM_USER_TOKEN', '')
    value = request.headers.get('authorization', '')
    if not expected or len(expected) < 24 or not hmac.compare_digest(value, 'Bearer ' + expected):
        raise HTTPException(401, 'configure a server token (at least 24 characters) and authenticate')
    # Bearer authorization avoids ambient-cookie CSRF. Also reject cross-origin browser requests.
    origin = request.headers.get('origin')
    if origin:
        allowed = set(filter(None, os.environ.get('VM_ALLOWED_ORIGINS', '').split(',')))
        forwarded = request.headers.get('x-forwarded-host') if request.client and request.client.host in ('127.0.0.1', '::1', 'testclient') else None
        host = forwarded or request.headers.get('host', '')
        if origin not in allowed and origin not in ('https://' + host, 'http://' + host):
            raise HTTPException(403, 'origin denied')
    return hashlib.sha256(value.encode()).hexdigest()

def admin(request: Request):
    return auth(request, True)

def user(request: Request):
    return auth(request)

class ConfigInput(Strict):
    yaml: str = Field(max_length=65536)
    expected_version: int = Field(default=1, ge=1)

class Rollback(Strict):
    version: int = Field(ge=1)
    expected_version: int = Field(ge=1)

class SessionInput(Strict):
    consent: bool

class FrameInput(Strict):
    camera_id: str = Field(pattern='^camera[12]$')
    frame_id: int = Field(ge=0, le=9007199254740991)
    captured_at: float = Field(ge=0, allow_inf_nan=False)
    image: str = Field(max_length=1500000)
    feature: str = Field(min_length=1, max_length=100)
    config_version: int = Field(ge=1)
    request_id: str = Field(max_length=100)

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
        self.events = deque(maxlen=30)

sessions = {}

def session_for(sid, owner):
    s = sessions.get(sid)
    if not s or s.owner != owner or s.expiry < time.monotonic():
        raise HTTPException(404, 'session expired or unavailable')
    return s

@router.get('/api/health')
def health():
    return {'status': 'ok', 'api_version': 1, 'inference': 'remote-only', 'config_version': store.version,
            'configuration': 'persistent-path-configured' if store.path else 'read-only-defaults',
            'providers_configured': len(store.history[-1].providers), 'sessions': 'ephemeral'}

@router.get('/api/providers')
def providers(owner=Depends(user)):
    version, cfg = store.snapshot()
    return {'config_version': version, 'providers': {k: {'label': p.label, 'adapter': p.adapter, 'model': p.model,
            'capabilities': p.capabilities, 'trust': p.trust, 'credential_present': bool(os.environ.get(p.api_key_secret, '')) if p.api_key_secret else True,
            'destination': __import__('urllib.parse', fromlist=['urlsplit']).urlsplit(os.environ.get(p.base_url_env, '')).hostname,
            'protocol_verified': p.adapter != 'laya-vision'} for k,p in cfg.providers.items()},
            'features': {k: v.model_dump() for k,v in cfg.features.items()}}

@router.get('/api/config')
def get_config(owner=Depends(admin)):
    version, cfg = store.snapshot()
    return {'config_version': version, 'yaml': yaml.safe_dump(cfg.model_dump(), sort_keys=False),
            'history': list(range(1, version+1)), 'writable': bool(store.path)}

@router.get('/api/config/template')
def template(owner=Depends(admin)):
    from pathlib import Path
    return Response((Path(__file__).parent.parent/'config/examples/disabled.yaml').read_text(), media_type='application/yaml', headers={'Content-Disposition': 'attachment; filename=visual-mentor.yaml'})

async def validate(text):
    try:
        cfg = parse_yaml(text)
    except Exception:
        # Never echo YAML or validation input (it may contain pasted secrets).
        raise HTTPException(422, 'Invalid YAML/schema: use unique keys, no aliases, known providers and compatible capabilities; check template') from None
    for p in cfg.providers.values():
        try:
            await destination(p, False)
        except ProviderFailure:
            raise HTTPException(422, 'Provider endpoint missing or denied: configure HTTPS public host in VM_ALLOWED_HOSTS and endpoint environment variable') from None
    return cfg

@router.post('/api/config/validate')
async def validate_config(body: ConfigInput, owner=Depends(admin)):
    cfg = await validate(body.yaml)
    old = store.history[-1].model_dump()
    new = cfg.model_dump()
    return {'valid': True, 'config_version': store.version, 'changed_sections': [k for k in new if new[k] != old[k]], 'profile': cfg.profile}

@router.post('/api/config/apply')
async def apply_config(body: ConfigInput, owner=Depends(admin)):
    cfg = await validate(body.yaml)
    try:
        version = await store.apply(cfg, body.expected_version)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from None
    return {'config_version': version, 'profile': cfg.profile}

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
    _, cfg = store.snapshot()
    if pid not in cfg.providers:
        raise HTTPException(404, 'unknown provider')
    p = cfg.providers[pid]
    # Only a synthetic image/text; microphone tests require an explicit bounded clip in a live session.
    if p.adapter == 'openai-transcription':
        raise HTTPException(409, 'Use an explicitly enabled live audio clip to test transcription')
    image = Image.new('RGB', (32,32), 'white')
    out = io.BytesIO(); image.save(out, format='JPEG')
    payload = {'text': 'Synthetic connection test. Respond with OK.', 'image': 'data:image/jpeg;base64,' + base64.b64encode(out.getvalue()).decode(), 'camera_id': 'test', 'frame_id': 0, 'width':32, 'height':32}
    start = time.monotonic()
    await adapter.call(pid, p, payload, False)
    return {'provider': pid, 'status':'ok', 'latency_ms': round((time.monotonic()-start)*1000), 'synthetic': True}

@router.post('/api/live/sessions')
def create_session(body: SessionInput, owner=Depends(user)):
    if not body.consent:
        raise HTTPException(400, 'explicit transfer consent required')
    for sid in list(sessions):
        if sessions[sid].expiry < time.monotonic():
            del sessions[sid]
    if len(sessions) >= 64 or sum(s.owner == owner for s in sessions.values()) >= 4:
        raise HTTPException(429, 'session limit')
    sid = secrets.token_urlsafe(24)
    sessions[sid] = Session(owner)
    return {'session_id': sid, 'config_version': store.version, 'expires_in': 1800, 'retention': 'in-memory observations only'}

@router.delete('/api/live/sessions/{sid}')
def delete_session(sid: str, owner=Depends(user)):
    session_for(sid, owner)
    del sessions[sid]
    return {'deleted': True}

@router.post('/api/live/sessions/{sid}/frames')
async def analyze_frame(sid: str, body: FrameInput, owner=Depends(user)):
    s = session_for(sid, owner)
    version, cfg = store.snapshot()
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
        out, statuses = await route(cfg, body.feature, {**body.model_dump(), 'width':width, 'height':height})
    finally:
        s.busy.discard(body.camera_id)
    # Deleting a session while an inference request is in flight discards its result.
    session_for(sid, owner)
    result = {'session_id':sid, 'camera_id':body.camera_id, 'frame_id':body.frame_id, 'captured_at':body.captured_at,
              'request_id':body.request_id, 'config_version':version, 'observed_at':received,
              'source_width':width, 'source_height':height, 'detections':[d.model_dump() for d in out.detections],
              'decisions':[d.model_dump() for d in out.decisions], 'provider_results':statuses,
              'warnings':['No successful provider result'] if not any(r['status']=='ok' for r in statuses) else []}
    s.events.append(result)
    return result

@router.get('/api/live/sessions/{sid}/events')
def events(sid: str, owner=Depends(user)):
    return list(session_for(sid, owner).events)

@router.post('/api/live/sessions/{sid}/transcribe')
async def transcribe(sid: str, body: AudioInput, owner=Depends(user)):
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
    _, cfg = store.snapshot()
    s.busy.add('audio'); s.rate['audio'] = time.monotonic()
    try:
        out, statuses = await route(cfg, 'audio.transcription', {'audio':audio})
    finally:
        s.busy.discard('audio')
    session_for(sid, owner)
    return {'text':out.text, 'provider_results':statuses, 'duration_ms':body.duration_ms}

@router.post('/api/live/sessions/{sid}/guidance')
async def guidance(sid: str, owner=Depends(user)):
    s = session_for(sid, owner)
    if 'mentor' in s.busy or time.monotonic() - s.rate.get('mentor', 0) < 2:
        raise HTTPException(429, 'guidance rate limit')
    _, cfg = store.snapshot()
    s.busy.add('mentor'); s.rate['mentor'] = time.monotonic()
    try:
        out, statuses = await route(cfg, 'mentor.reasoning', {'text': 'Give cautious next-step guidance from these observations, identify uncertainty. No autonomous actions. ' + str(list(s.events)[-5:])[:24000]})
    finally:
        s.busy.discard('mentor')
    session_for(sid, owner)
    return {'guidance':out.text, 'provider_results':statuses, 'autonomous':False}
