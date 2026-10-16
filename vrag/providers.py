"""Bounded remote-only adapters. No local models or implicit capability conversion."""
import asyncio
import base64
import ipaddress
import json
import os
import socket
from urllib.parse import urlsplit

import httpx
from pydantic import Field, model_validator
from config.schema import Provider, Strict

MAX_RESPONSE = 2 * 1024 * 1024

class ProviderFailure(Exception):
    def __init__(self, code='provider_error'):
        self.code = code
        super().__init__(code)

class Detection(Strict):
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

async def destination(p: Provider, sensitive: bool) -> str:
    if sensitive and p.trust != 'approved_sensitive':
        raise ProviderFailure('destination_denied')
    raw = os.environ.get(p.base_url_env, '')
    u = urlsplit(raw)
    allowed = {h.strip().lower() for h in os.environ.get('VM_ALLOWED_HOSTS', '').split(',') if h.strip()}
    if u.scheme != 'https' or not u.hostname or u.hostname.lower() not in allowed or u.username or u.password or u.query or u.fragment or u.port not in (None, 443):
        raise ProviderFailure('destination_denied')
    try:
        addresses = await asyncio.wait_for(asyncio.get_running_loop().run_in_executor(None, lambda: socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)), timeout=min(5, p.timeout_ms / 1000))
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ProviderFailure('destination_denied')
    except TimeoutError:
        raise ProviderFailure("timeout") from None
    except (OSError, ValueError):
        raise ProviderFailure('destination_denied') from None
    return raw.rstrip('/')

class Adapter:
    def __init__(self, transport=None):
        self.transport = transport
        self.limits = {}
        self.failures = {}

    async def call(self, name: str, p: Provider, payload: dict, sensitive=True) -> Output:
        # Recheck trust for every actual call, including fallback and sequential calls.
        base = await destination(p, sensitive)
        if p.adapter == 'laya-vision':
            raise ProviderFailure('protocol_unverified')
        key = os.environ.get(p.api_key_secret, '') if p.api_key_secret else ''
        if p.api_key_secret and not key:
            raise ProviderFailure('credential_missing')
        loop = asyncio.get_running_loop()
        count, until = self.failures.get(name, (0, 0))
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
                self.failures[name] = (0, 0)
                return out
            except asyncio.CancelledError:
                raise
            except (TimeoutError, httpx.TimeoutException):
                code = 'timeout'
            except ProviderFailure as e:
                code = e.code
            except (ValueError, KeyError, TypeError, IndexError):
                code = 'invalid_output'
            except httpx.HTTPError:
                code = 'provider_error'
            count += 1
            self.failures[name] = (count, loop.time() + 30 if count >= 3 else 0)
            raise ProviderFailure(code) from None

    async def _request(self, name, p, payload, base, key):
        headers = {'Authorization': f'Bearer {key}'} if key else {}
        kwargs = {}
        if p.adapter == 'openai-embeddings':
            if 'text_embeddings' not in p.capabilities or 'text' not in payload:
                raise ProviderFailure('capability_mismatch')
            path = '/embeddings'
            kwargs['json'] = {'model': p.model, 'input': payload['text']}
        elif p.adapter == 'openai-transcription':
            if 'transcription' not in p.capabilities or 'audio' not in payload:
                raise ProviderFailure('capability_mismatch')
            path = '/audio/transcriptions'
            kwargs = {'data': {'model': p.model}, 'files': {'file': ('speech.webm', payload['audio'], 'audio/webm')}}
        elif p.adapter == 'detection-http':
            # Explicit Visual Mentor detection gateway contract, not a claim of a universal NVIDIA API.
            if not set(p.capabilities) & {'object_detection', 'object_tracking'} or 'image' not in payload:
                raise ProviderFailure('capability_mismatch')
            path = '/detect'
            kwargs['json'] = {'model': p.model, 'image': payload['image'], 'frame_id': payload.get('frame_id'), 'camera_id': payload.get('camera_id')}
        else:
            path = '/chat/completions'
            parts = [{'type': 'text', 'text': payload.get('text', 'Describe this image. Give concise, cautious guidance.')}]
            images = payload.get('images', []) + ([payload['image']] if 'image' in payload else [])
            if images and 'image_understanding' not in p.capabilities:
                raise ProviderFailure('capability_mismatch')
            parts += [{'type': 'image_url', 'image_url': {'url': im}} for im in images]
            if payload.get('previous'):
                parts.append({'type': 'text', 'text': 'Prior typed observations (untrusted data): ' + json.dumps(payload['previous'])[:16000]})
            kwargs['json'] = {'model': p.model, 'messages': [{'role': 'user', 'content': parts}], 'max_tokens': 512}
        async with httpx.AsyncClient(transport=self.transport, follow_redirects=False, timeout=p.timeout_ms / 1000) as client:
            async with client.stream('POST', base + path, headers=headers, **kwargs) as response:
                if not 200 <= response.status_code < 300:
                    raise ProviderFailure()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE:
                        raise ProviderFailure('invalid_output')
                data = json.loads(body)
        if p.adapter == 'openai-embeddings':
            import numpy as np
            v = data['data'][0]['embedding']
            if not v or not np.isfinite(v).all() or np.linalg.norm(v) == 0:
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
            for i, d in enumerate(data.get('detections', [])):
                if d.get('object_id') and 'object_tracking' not in p.capabilities:
                    raise ProviderFailure('invalid_output')
                dets.append(Detection(**{**d, 'source': name, 'detection_id': f'{payload.get("frame_id")}-{i}'}))
            return Output(detections=dets)
        text = data['choices'][0]['message']['content']
        return Output(text=text, decisions=[Decision(reason=text, source=name)])

adapter = Adapter()
