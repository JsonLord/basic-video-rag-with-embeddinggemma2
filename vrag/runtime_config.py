"""HF variables overlay the existing registry, never saved secret values or health."""
import os
from config.schema import Route
from config.v2 import ProviderV2, migrate
from .providers import ProviderFailure, configured_destination


def environment_providers(names=None):
    providers={}
    for name,url,model,key,adapter,caps in (
        ('hf-conversation','OPENAI_COMPATIBLE_URL','OPENAI_COMPATIBLE_MODEL','OPENAI_COMPATIBLE_API_KEY','openai-conversation',['conversation','reasoning']),
        ('hf-research','A2A_URL',None,'A2A_TOKEN','a2a',['research_dispatch']),
    ):
        if names is not None and name not in names:continue
        if not os.environ.get(url):continue
        selected=os.environ.get(model,'') if model else 'agent-card-unqualified'
        if not selected or len(selected)>200 or any(ord(c)<32 for c in selected):raise ProviderFailure('environment_configuration_invalid')
        p=ProviderV2(adapter=adapter,label='HF environment default; live capability unqualified',
            model=selected,model_env=model,base_url_env=url,api_key_secret=key,
            capabilities=caps,trust='public_only',auth_mode='path_token' if adapter=='a2a' and '/a2a/t-{token}' in os.environ.get(url,'') else 'bearer')
        try:configured_destination(p,False)
        except ProviderFailure:raise ProviderFailure('environment_configuration_invalid') from None
        providers[name]=p
    return providers


def with_environment_defaults(config):
    selected={name for name,feature in (("hf-conversation","mentor.conversation"),("hf-research","research.dispatch")) if feature not in config.features}
    defaults=environment_providers(selected)
    if not defaults:return config.model_copy(deep=True)
    result=migrate(config)
    for name,feature in (('hf-conversation','mentor.conversation'),('hf-research','research.dispatch')):
        if feature in result.features or name not in defaults:continue
        if name in result.providers:raise ProviderFailure('environment_configuration_conflict')
        result.providers[name]=defaults[name]
        # Presence is not privacy authorization, health or activation.
        result.features[feature]=Route(providers=[name],enabled=False)
    return type(result).model_validate(result.model_dump())


def environment_summary():
    try:
        ps=environment_providers()
        from .mentor_api import provider_host
        return {'status':'configured' if ps else 'unconfigured', 'live_status':'not_checked',
                'providers':{k:{'adapter':p.adapter,'destination':provider_host(p),'model':p.model,
                    'credential_present':bool(os.environ.get(p.api_key_secret,'')),
                    'capability_version':p.capability_version,'trust':p.trust} for k,p in ps.items()}}
    except ProviderFailure as exc:
        return {'status':'configuration_error','error':exc.code,'providers':{},'live_status':'not_checked'}
