import asyncio
import pytest
from config.schema import Configuration, Provider, Route, Condition
from vrag.providers import Output, Decision, ProviderFailure
from vrag.routing import route

def cfg(strategy, **kwargs):
    p=Provider(adapter='openai-chat-vision',base_url_env='URL',model='model',capabilities=['image_understanding'],trust='approved_sensitive')
    return Configuration(providers={'a':p,'b':p},features={'live.camera1.scene':Route(strategy=strategy,providers=['a'] if strategy=='single' else ['a','b'],**kwargs)})

@pytest.mark.asyncio
@pytest.mark.parametrize('strategy',['single','fallback','parallel','sequential','conditional'])
async def test_strategies(monkeypatch,strategy):
    calls=[]
    async def call(name,p,payload,sensitive):
        calls.append((name,payload.copy()))
        return Output(decisions=[Decision(source=name,reason='seen')])
    monkeypatch.setattr('vrag.routing.adapter.call',call)
    options={'conditions':[Condition(field='camera_id',equals='camera1',provider='b')]} if strategy=='conditional' else {}
    out,status=await route(cfg(strategy,**options),'live.camera1.scene',{'camera_id':'camera1'})
    assert out.decisions
    assert all(s['status']=='ok' for s in status)
    if strategy=='sequential':assert 'previous' in calls[1][1]
    if strategy=='conditional':assert calls[0][0]=='b'
    if strategy=='fallback':assert len(calls)==1

@pytest.mark.asyncio
async def test_fallback_does_not_ignore_destination_denial(monkeypatch):
    calls=[]
    async def call(name,*args):
        calls.append(name)
        raise ProviderFailure('destination_denied')
    monkeypatch.setattr('vrag.routing.adapter.call',call)
    out,status=await route(cfg('fallback'),'live.camera1.scene',{})
    assert calls==['a'] and not out.decisions

@pytest.mark.asyncio
async def test_eligible_fallback_and_independent_parallel_error(monkeypatch):
    async def call(name,*args):
        if name=='a':raise ProviderFailure('timeout')
        return Output(text='success')
    monkeypatch.setattr('vrag.routing.adapter.call',call)
    for strategy in ['fallback','parallel']:
        out,status=await route(cfg(strategy),'live.camera1.scene',{})
        assert out.text=='success' and status[0]['status']=='timeout'

@pytest.mark.asyncio
async def test_first_valid_cancels_slow_calls(monkeypatch):
    cancelled=[]
    async def call(name,*args):
        if name=='a':
            await asyncio.sleep(0.01)
            return Output(text='success')
        try:await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.append(name);raise
    monkeypatch.setattr('vrag.routing.adapter.call',call)
    out,status=await route(cfg('parallel',result_policy='first_valid'),'live.camera1.scene',{})
    assert out.text=='success' and cancelled==['b']
    assert status[-1]['status']=='cancelled'

@pytest.mark.asyncio
async def test_quorum_failure_is_explicit(monkeypatch):
    async def call(name,*args):
        if name=='b':raise ProviderFailure('provider_error')
        return Output(text='one result')
    monkeypatch.setattr('vrag.routing.adapter.call',call)
    out,status=await route(cfg('parallel',result_policy='quorum',quorum=2),'live.camera1.scene',{})
    assert not out.text and len(status)==2 and out.warnings==['quorum_not_met']
