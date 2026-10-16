"""Strict, bounded configuration. Credentials are references, never YAML values."""
from typing import Literal
import re
import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

Capability = Literal['image_understanding', 'visual_decision', 'object_detection', 'bounding_boxes', 'object_tracking', 'reasoning', 'text_embeddings', 'multimodal_embeddings', 'transcription']

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

class Provider(Strict):
    label: str = Field(default='', max_length=100)
    adapter: Literal['openai-chat-vision', 'openai-embeddings', 'openai-transcription', 'detection-http', 'laya-vision']
    base_url_env: str = Field(pattern=r'^[A-Z][A-Z0-9_]{0,79}$')
    api_key_secret: str | None = Field(default=None, pattern=r'^[A-Z][A-Z0-9_]{0,79}$')
    model: str = Field(min_length=1, max_length=200)
    capabilities: list[Capability] = Field(max_length=10)
    trust: Literal['approved_sensitive', 'public_only'] = 'public_only'
    timeout_ms: int = Field(default=10000, ge=100, le=60000)
    concurrency: int = Field(default=2, ge=1, le=8)
    @model_validator(mode='after')
    def supported(self):
        supported = {
            'openai-chat-vision': {'image_understanding', 'reasoning', 'visual_decision'},
            'openai-embeddings': {'text_embeddings'},
            'openai-transcription': {'transcription'},
            'detection-http': {'object_detection', 'bounding_boxes', 'object_tracking'},
            # Laya's wire protocol is not published in this repository. Fail closed.
            'laya-vision': set(),
        }
        if not set(self.capabilities) <= supported[self.adapter]:
            raise ValueError('capability is not supported by this adapter; use a verified provider protocol')
        return self

class Condition(Strict):
    field: Literal['camera_id', 'has_detections']
    equals: str | bool
    provider: str

class Route(Strict):
    strategy: Literal['single', 'fallback', 'parallel', 'sequential', 'conditional'] = 'single'
    providers: list[str] = Field(min_length=1, max_length=8)
    enabled: bool = True
    result_policy: Literal['all', 'first_valid', 'quorum'] = 'all'
    quorum: int = Field(default=1, ge=1, le=8)
    fusion: Literal['spatial_semantic'] | None = None
    fallback_on: list[Literal['timeout', 'provider_error', 'invalid_output']] = Field(default_factory=lambda: ['timeout', 'provider_error', 'invalid_output'])
    conditions: list[Condition] = Field(default_factory=list, max_length=8)
    @model_validator(mode='after')
    def valid(self):
        if len(set(self.providers)) != len(self.providers):
            raise ValueError('duplicate providers')
        if self.strategy == 'single' and len(self.providers) != 1:
            raise ValueError('single requires exactly one provider')
        if self.quorum > len(self.providers):
            raise ValueError('quorum exceeds provider count')
        if self.strategy == 'conditional' and not self.conditions:
            raise ValueError('conditional requires deterministic conditions')
        if any(c.provider not in self.providers for c in self.conditions):
            raise ValueError('condition provider must belong to route')
        return self

class Camera(Strict):
    analysis_fps: float = Field(default=1, gt=0, le=2)
    width: int = Field(default=640, ge=160, le=1920)
    height: int = Field(default=480, ge=120, le=1080)

class Privacy(Strict):
    record_video: Literal[False] = False
    upload_only_on_explicit_start: Literal[True] = True
    require_approved_destination_for_camera: Literal[True] = True

class Configuration(Strict):
    version: Literal[1] = 1
    profile: str = Field(default='unconfigured', min_length=1, max_length=100)
    providers: dict[str, Provider] = Field(default_factory=dict, max_length=32)
    features: dict[str, Route] = Field(default_factory=dict, max_length=64)
    cameras: dict[Literal['camera1', 'camera2'], Camera] = Field(default_factory=lambda: {'camera1': Camera(), 'camera2': Camera()})
    privacy: Privacy = Field(default_factory=Privacy)
    @model_validator(mode='after')
    def references(self):
        for key in self.providers:
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}', key):
                raise ValueError('invalid provider identifier')
        required = {'rag.text_embeddings': 'text_embeddings', 'audio.transcription': 'transcription', 'rag.reasoning': 'reasoning', 'mentor.reasoning': 'reasoning'}
        for feature, route in self.features.items():
            if any(p not in self.providers for p in route.providers):
                raise ValueError(f'{feature}: unknown provider')
            if route.enabled:
                cap = required.get(feature)
                caps = {c for p in route.providers for c in self.providers[p].capabilities}
                if cap and cap not in caps:
                    raise ValueError(f'{feature}: missing {cap} capability')
                if feature.endswith('.tracking') and 'object_tracking' not in caps:
                    raise ValueError('tracking requires a real tracker')
                if feature.endswith('.detection') and 'bounding_boxes' not in caps:
                    raise ValueError('detection requires a spatial detector')
                if feature.startswith('live.') and not caps & {'image_understanding', 'visual_decision', 'object_detection', 'object_tracking'}:
                    raise ValueError('live route requires visual capability')
        return self

def parse_yaml(text: str) -> Configuration:
    if len(text.encode()) > 65536:
        raise ValueError('configuration exceeds 64 KiB')
    # Reject aliases/anchors entirely rather than expanding attacker-controlled graphs.
    if any(isinstance(t, (yaml.tokens.AliasToken, yaml.tokens.AnchorToken)) for t in yaml.scan(text)):
        raise ValueError('YAML aliases and anchors are disabled')
    class UniqueLoader(yaml.SafeLoader):
        pass
    def mapping(loader, node):
        result = {}
        for k, v in node.value:
            key = loader.construct_object(k)
            if key in result:
                raise ValueError('duplicate YAML key')
            result[key] = loader.construct_object(v)
        return result
    UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, mapping)
    return Configuration.model_validate(yaml.load(text, Loader=UniqueLoader))
