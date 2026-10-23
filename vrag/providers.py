"""Bounded remote-only adapters. No local models or implicit capability conversion."""
import asyncio
import json
import ipaddress
import os
from urllib.parse import urlsplit

import httpx
from pydantic import Field, model_validator
from config.schema import Provider, Strict
from .egress import public_addresses, proxy_for, transport_for

MAX_RESPONSE = 2 * 1024 * 1024

class ProviderFailure(Exception):
    def __init__(self, code='provider_error'):
        self.code = code
        super().__init__(code)

class DetectionEvidence(Strict):
    source: str = Field(max_length=100)
    detection_id: str = Field(max_length=100)
    bbox_xyxy: tuple[float,float,float,float]
    confidence: float = Field(ge=0,le=1)
    object_id: str | None = Field(default=None,max_length=100)

class Detection(Strict):
    evidence: list[DetectionEvidence] = Field(default_factory=list,max_length=1600)
    detection_id: str = Field(max_length=100)
    object_id: str | None = Field(default=None, max_length=100)
    label: str = Field(max_length=200)
    bbox_xyxy: tuple[float, float, float, float]
    confidence: float = Field(ge=0, le=1)
    source: str = Field(max_length=100)
    @model_validator(mode='after')
    def box(self):
        x1, y1, x2, y2 = self.bbox_xyxy
        if not (0 <= x1 < x2 <= 1 and 0 <= y1 < y2 <= 1):
            raise ValueError('invalid normalized box')
        return self

class Decision(Strict):
    action: str = Field(default='observe', max_length=200)
    reason: str = Field(max_length=8000)
    source: str = Field(max_length=100)

class Output(Strict):
    detections: list[Detection] = Field(default_factory=list, max_length=200)
    decisions: list[Decision] = Field(default_factory=list, max_length=20)
    text: str = Field(default='', max_length=32000)
    warnings: list[str] = Field(default_factory=list, max_length=20)
    embedding: list[float] | None = Field(default=None, max_length=16384)

def configured_destination(p: Provider, sensitive: bool) -> str:
    if sensitive and p.trust != 'approved_sensitive':
        raise ProviderFailure('destination_denied')
    raw = os.environ.get(p.base_url_env, '')
    try:
        u = urlsplit(raw)
        port = u.port
    except ValueError:
        raise ProviderFailure('destination_denied') from None
    allowed = {h.strip().lower() for h in os.environ.get('VM_ALLOWED_HOSTS', '').split(',') if h.strip()}
    if u.scheme != 'https' or not u.hostname or u.hostname.lower() not in allowed or u.username or u.password or u.query or u.fragment or port not in (None, 443):
        raise ProviderFailure('destination_denied')
    try:
        literal = ipaddress.ip_address(u.hostname)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise ProviderFailure('destination_denied')
    return raw.rstrip('/')

async def destination(p: Provider, sensitive: bool) -> str:
    raw = configured_destination(p, sensitive)
    u = urlsplit(raw)
    try:
        await public_addresses(u.hostname, min(5, p.timeout_ms / 1000))
    except (TimeoutError, OSError) as exc:
        # Managed environments may provide DNS only inside the trusted proxy.
        # Keep the hostname URL/TLS check and injected credentials on that path.
        # That proxy must enforce public-only resolution (see security.md).
        if not proxy_for(raw):
            raise ProviderFailure('timeout' if isinstance(exc, TimeoutError) else 'destination_denied') from None
    except ValueError:
        raise ProviderFailure('destination_denied') from None
    return raw.rstrip('/')

def resolved_provider(p):
    if getattr(p,'model_env',None):
        model=os.environ.get(p.model_env,'')
        if not model or len(model)>200 or any(ord(c)<32 for c in model):raise ProviderFailure('environment_configuration_invalid')
        return p.model_copy(update={'model':model})
    return p

class Adapter:
    def __init__(self, transport=None):
        self.transport = transport
        self.limits = {}
        self.failures = {}

    def stream(self,name,p,messages,registry=None):
        from .conversation_stream import stream
        return stream(self,name,p,messages,registry)

    async def call(self, name: str, p: Provider, payload: dict, sensitive=True) -> Output:
        if p.adapter == 'a2a':raise ProviderFailure('adapter_unavailable')
        p=resolved_provider(p)
        # Recheck trust for every actual call, including fallback and sequential calls.
        base = await destination(p, sensitive)
        key = os.environ.get(p.api_key_secret, '') if p.api_key_secret else ''
        if p.api_key_secret and not key:
            raise ProviderFailure('credential_missing')
        loop = asyncio.get_running_loop()
        identity = (name, base, p.model_dump_json())
        count, until = self.failures.get(identity, (0, 0))
        if until > loop.time():
            raise ProviderFailure('circuit_open')
        sem_key = (name, p.concurrency)
        sem = self.limits.setdefault(sem_key, asyncio.Semaphore(p.concurrency))
        # Never accumulate an unbounded waiting queue.
        if sem.locked():
            raise ProviderFailure('busy')
        async with sem:
            try:
                async with asyncio.timeout(p.timeout_ms / 1000):
                    out = await self._request(name, p, payload, base, key)
                self.failures[identity] = (0, 0)
                return out
            except asyncio.CancelledError:
                raise
            except (TimeoutError, httpx.TimeoutException):
                code = 'timeout'
            except ProviderFailure as e:
                code = e.code
            except (ValueError, KeyError, TypeError, IndexError, AttributeError, OverflowError):
                code = 'invalid_output'
            except httpx.HTTPError:
                code = 'provider_error'
            count += 1
            self.failures[identity] = (count, loop.time() + 30 if count >= 3 else 0)
            raise ProviderFailure(code) from None

    async def _request(self, name, p, payload, base, key):
        headers = {'Authorization': f'Bearer {key}'} if key else {}
        kwargs = {}
        if p.adapter == 'laya-vision':
            if 'visual_decision' not in p.capabilities or 'image' not in payload:
                raise ProviderFailure('capability_mismatch')
            prefix, encoded = payload['image'].split(',', 1)
            if prefix not in ('data:image/jpeg;base64', 'data:image/png;base64', 'data:image/webp;base64'):
                raise ProviderFailure('capability_mismatch')
            path = '/v1/system-one'
            kwargs['json'] = {
                'state': {'task': payload.get('text', 'Advisory visual inspection; no autonomous actions.'),
                          'camera_id':payload.get('camera_id'), 'frame_id':payload.get('frame_id'),
                          'previous_observations':payload.get('previous', {})},
                'imageBase64': encoded,
                'questions': {'visual_signal': {'type':'noul', 'instructions':'Is this image clear enough for human visual inspection?'}},
            }
        elif p.adapter == 'openai-embeddings':
            if 'text_embeddings' not in p.capabilities or 'text' not in payload:
                raise ProviderFailure('capability_mismatch')
            path = '/embeddings'
            kwargs['json'] = {'model': p.model, 'input': payload['text']}
        elif p.adapter == 'openai-transcription':
            if 'transcription' not in p.capabilities or 'audio' not in payload:
                raise ProviderFailure('capability_mismatch')
            path = '/audio/transcriptions'
            kwargs = {'data': {'model': p.model}, 'files': {'file': (payload.get('audio_filename','speech.webm'), payload['audio'], payload.get('audio_mime','audio/webm'))}}
        elif p.adapter == 'detection-http':
            # Explicit Visual Mentor detection gateway contract, not a claim of a universal NVIDIA API.
            if not set(p.capabilities) & {'object_detection', 'object_tracking'} or 'image' not in payload:
                raise ProviderFailure('capability_mismatch')
            path = '/detect'
            kwargs['json'] = {'model': p.model, 'image': payload['image'], 'frame_id': payload.get('frame_id'), 'camera_id': payload.get('camera_id')}
        elif p.adapter in ('openai-chat-vision','openai-conversation'):
            if p.adapter=='openai-conversation' and (payload.get('image') or payload.get('images')):raise ProviderFailure('capability_mismatch')
            if p.adapter=='openai-conversation' and not base.endswith('/v1'):base += '/v1'
            path = '/chat/completions'
            parts = [{'type': 'text', 'text': payload.get('text', 'Describe this image. Give concise, cautious guidance.')}]
            images = payload.get('images', []) + ([payload['image']] if 'image' in payload else [])
            if images and 'image_understanding' not in p.capabilities:
                raise ProviderFailure('capability_mismatch')
            parts += [{'type': 'image_url', 'image_url': {'url': im}} for im in images]
            if payload.get('previous'):
                parts.append({'type': 'text', 'text': 'Prior typed observations (untrusted data): ' + json.dumps(payload['previous'])[:16000]})
            kwargs['json'] = {'model': p.model, 'messages': [{'role': 'user', 'content': parts}], 'max_tokens': 512}
        else:raise ProviderFailure('adapter_unavailable')
        async with httpx.AsyncClient(transport=self.transport or transport_for(base), follow_redirects=False, timeout=p.timeout_ms / 1000) as client:
            async with client.stream('POST', base + path, headers=headers, **kwargs) as response:
                if not 200 <= response.status_code < 300:
                    raise ProviderFailure()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE:
                        raise ProviderFailure('invalid_output')
                data = json.loads(body)
        if p.adapter == 'laya-vision':
            # GitHub 77b324a: results.<question>; live 2026-10-16:
            # results.answers.<question>. Neither can supply spatial detections.
            if data.get('backend') != 'laya-vision' or data.get('model') != p.model or 'placeholder' in p.model.lower():
                raise ProviderFailure('invalid_output')
            results = data['results']
            if 'placeholder' in str(results.get('model', '')).lower():
                raise ProviderFailure('invalid_output')
            answers = results['answers'] if 'answers' in results else results
            answer = answers['visual_signal']
            probability = answer['noul']
            import math
            if answer.get('type') != 'noul' or isinstance(probability, bool) or not isinstance(probability, (int, float)) or not math.isfinite(probability) or not 0 <= probability <= 1:
                raise ProviderFailure('invalid_output')
            return Output(decisions=[Decision(action='visual_assessment',
                reason=f'Image inspectability probability: {probability:.4f} (Laya noul score; advisory, not a spatial detection).', source=name)])
        if p.adapter == 'openai-embeddings':
            import numpy as np
            v = data['data'][0]['embedding']
            with np.errstate(over='ignore', invalid='ignore'):
                array = np.asarray(v, dtype=np.float32)
                norm = np.linalg.norm(array)
            if not isinstance(v, list) or not v or array.ndim != 1 or not np.isfinite(array).all() or not np.isfinite(norm) or norm == 0:
                raise ProviderFailure('invalid_output')
            return Output(embedding=v)
        if p.adapter == 'openai-transcription':
            return Output(text=data['text'])
        if p.adapter == 'detection-http':
            if data.get('frame_id') != payload.get('frame_id') or data.get('camera_id') != payload.get('camera_id'):
                raise ProviderFailure('invalid_output')
            if data.get('width') != payload.get('width') or data.get('height') != payload.get('height'):
                raise ProviderFailure('invalid_output')
            dets = []
            if not isinstance(data.get('detections'), list) or len(data['detections']) > 200:
                raise ProviderFailure('invalid_output')
            for i, d in enumerate(data['detections']):
                if not isinstance(d, dict):
                    raise ProviderFailure('invalid_output')
                if 'object_tracking' in p.capabilities and not d.get('object_id'):raise ProviderFailure('invalid_output')
                if d.get('object_id') and 'object_tracking' not in p.capabilities:
                    raise ProviderFailure('invalid_output')
                if 'evidence' in d:raise ProviderFailure('invalid_output')
                dets.append(Detection(**{**d, 'source': name, 'detection_id': f'{payload.get("frame_id")}-{i}'}))
            return Output(detections=dets)
        text = data['choices'][0]['message']['content']
        return Output(text=text, decisions=[Decision(reason=text, source=name)])

adapter = Adapter()
