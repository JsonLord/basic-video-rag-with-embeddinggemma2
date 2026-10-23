"""Explicit v2 schema; importing this module never rewrites v1 history."""
from typing import Literal
from pydantic import Field, model_validator
from .schema import Provider, Configuration, Capability, Route, Camera, Privacy, Strict

FEATURE_ROLES = (
    'mentor.conversation', 'live.camera1.detection', 'live.camera2.detection',
    'live.camera1.decisions', 'live.camera2.decisions', 'live.tracking',
    'live.framing.target_selection', 'live.temporal_reasoning',
    'audio.transcription', 'research.dispatch',
)
LEGACY_ROLES = {'live.camera1.scene','live.camera2.scene','live.visual_decision',
                'rag.reasoning','mentor.reasoning','rag.text_embeddings'}

class ProviderV2(Provider):
    adapter: Literal['openai-chat-vision','openai-embeddings','openai-transcription','detection-http','laya-vision','openai-conversation','a2a']
    capabilities: list[Capability | Literal['conversation','temporal_reasoning','research_dispatch']] = Field(max_length=10)
    capability_version: Literal[1] = 1
    model_env: str | None = Field(default=None,pattern=r'^[A-Z][A-Z0-9_]{0,79}$')

    @model_validator(mode='after')
    def supported(self):
        # Override, rather than relax, the independent v1 capability validator.
        if self.adapter in ('openai-conversation','a2a'):
            if self.api_key_secret and (self.api_key_secret.startswith(('VM_','HF_','HUGGING_FACE_','GITHUB_','GH_','AWS_','RCLONE_','AGE_','OIC_','AZURE_','GOOGLE_')) or self.api_key_secret in ('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY')):
                raise ValueError('provider credentials cannot reference application, infrastructure or recovery secrets')
            permitted={'openai-conversation':{'conversation','reasoning'},'a2a':{'research_dispatch'}}[self.adapter]
            if not set(self.capabilities)<=permitted:raise ValueError('unsupported adapter capability')
        elif self.adapter=='openai-chat-vision' and 'temporal_reasoning' in self.capabilities:
            Provider.model_validate({**self.model_dump(exclude={'model_env','capability_version'}),'capabilities':[c for c in self.capabilities if c!='temporal_reasoning']})
            if 'image_understanding' not in self.capabilities:raise ValueError('temporal reasoning requires image input')
        else:
            Provider.model_validate(self.model_dump(exclude={'model_env','capability_version'}))
        if self.model_env and self.adapter!='openai-conversation':raise ValueError('model_env is only supported by conversation adapter')
        if self.model_env and self.model_env!='OPENAI_COMPATIBLE_MODEL':raise ValueError('unsupported model variable')
        return self

class ConfigurationV2(Strict):
    version: Literal[2] = 2
    profile: str = Field(default='unconfigured',min_length=1,max_length=100)
    providers: dict[str,ProviderV2] = Field(default_factory=dict,max_length=32)
    features: dict[str,Route] = Field(default_factory=dict,max_length=64)
    cameras: dict[Literal['camera1','camera2'],Camera] = Field(default_factory=lambda:{'camera1':Camera(),'camera2':Camera()})
    privacy: Privacy = Field(default_factory=Privacy)
    migrated_from: Literal[1] | None = None

    @model_validator(mode='after')
    def references(self):
        import re
        if any(not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',p) for p in self.providers):raise ValueError('invalid provider identifier')
        for feature,rule in self.features.items():
            if not re.fullmatch(r'[a-zA-Z0-9_.-]{1,100}',feature):raise ValueError('invalid feature role')
            if any(p not in self.providers for p in rule.providers):raise ValueError('unknown provider')
            ps=[self.providers[p] for p in rule.providers]
            if not rule.enabled:continue
            if any(p.model.lower().startswith(('replace-with','verified_','your-')) for p in ps):raise ValueError('replace placeholder model identifiers before enabling routes')
            required={'mentor.conversation':'conversation','audio.transcription':'transcription','rag.text_embeddings':'text_embeddings','mentor.reasoning':'reasoning','rag.reasoning':'reasoning','live.tracking':'object_tracking','live.temporal_reasoning':'temporal_reasoning'}
            cap=required.get(feature)
            if cap and any(cap not in p.capabilities for p in ps):raise ValueError(f'{feature}: missing required capability')
            if feature.endswith('.detection') and not any('bounding_boxes' in p.capabilities for p in ps):raise ValueError('detection requires spatial geometry')
            if feature.endswith('.decisions') and any('visual_decision' not in p.capabilities for p in ps):raise ValueError('decisions require decision capability')
            if feature in ('research.dispatch','live.framing.target_selection'):raise ValueError('this dispatch contract is not implemented; keep disabled')
            if feature=='rag.text_embeddings' and rule.strategy!='single':raise ValueError('embedding indexes require one explicit provider identity')
            if feature.startswith('live.') and any(not set(p.capabilities)&{'image_understanding','visual_decision','object_detection','object_tracking'} for p in ps):raise ValueError('live route requires visual capability')
        return self

def migrate(config):
    if isinstance(config,ConfigurationV2):return config.model_copy(deep=True)
    if not isinstance(config,Configuration):raise ValueError('expected typed v1 configuration')
    return ConfigurationV2.model_validate({**config.model_dump(),'version':2,'migrated_from':1})
