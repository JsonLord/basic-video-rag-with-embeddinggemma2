"""Bounded OpenAI SSE client over the existing provider/egress abstraction.

The durable conversation runner owns tool execution and turn state. This module
validates streaming text and complete correlated tool calls; it never executes them.
"""
import asyncio
import json
import os
from typing import Literal
import httpx
from pydantic import Field, model_validator
from config.schema import Strict
from .providers import ProviderFailure, destination, resolved_provider, MAX_RESPONSE
from .egress import transport_for
from .conversation_tools import ToolCall

class FunctionCall(Strict):
    name: str
    arguments: str

class AssistantCall(Strict):
    id: str
    type: Literal['function'] = 'function'
    function: FunctionCall
    @model_validator(mode='after')
    def checked(self):
        ToolCall(id=self.id,name=self.function.name,arguments=json.loads(self.function.arguments))
        return self

class Message(Strict):
    role: Literal['system','user','assistant','tool']
    content: str = Field(max_length=16000)
    tool_call_id: str | None = Field(default=None,max_length=100)
    tool_calls: list[AssistantCall] | None = Field(default=None,max_length=5)
    @model_validator(mode='after')
    def owned_tool_result(self):
        if self.role=='tool' and not self.tool_call_id:raise ValueError('tool result requires correlation')
        if self.role!='tool' and self.tool_call_id:raise ValueError('unexpected tool correlation')
        if self.tool_calls and self.role!='assistant':raise ValueError('only assistants can call tools')
        if self.tool_calls and len({c.id for c in self.tool_calls})!=len(self.tool_calls):raise ValueError('duplicate tool IDs')
        return self

def validate_correlation(messages):
    pending=set()
    for m in messages:
        if m.role=='tool':
            if m.tool_call_id not in pending:raise ProviderFailure('invalid_tool_correlation')
            pending.remove(m.tool_call_id)
        else:
            if pending:raise ProviderFailure('invalid_tool_correlation')
            if m.tool_calls:pending={c.id for c in m.tool_calls}
    if pending:raise ProviderFailure('invalid_tool_correlation')

class StreamEvent(Strict):
    type: Literal['text','tool_call','done']
    text: str = Field(default='',max_length=32000)
    call: ToolCall | None = None
    model: str | None = None

async def stream(adapter,name,provider,messages,registry=None,*,sensitive=True):
    """Yield text progressively; tool calls only after a complete, valid stream.

    Caller owns user/session authentication and explicit routing selection. Tools
    execute separately through ToolRegistry's ownership/privacy/idempotency checks.
    """
    p=resolved_provider(provider)
    if p.adapter!='openai-conversation' or 'conversation' not in p.capabilities:raise ProviderFailure('capability_mismatch')
    typed=[Message.model_validate(m.model_dump() if isinstance(m,Message) else m) for m in messages]
    if not 1<=len(typed)<=20 or sum(len(m.content) for m in typed)>32000:raise ProviderFailure('context_limit')
    validate_correlation(typed)
    base=await destination(p,sensitive)
    if not base.endswith('/v1'):base += '/v1'
    key=os.environ.get(p.api_key_secret,'') if p.api_key_secret else ''
    if p.api_key_secret and not key:raise ProviderFailure('credential_missing')
    semaphore=adapter.limits.setdefault((name,p.concurrency),asyncio.Semaphore(p.concurrency))
    if semaphore.locked():raise ProviderFailure('busy')
    request={'model':p.model,'messages':[m.model_dump(exclude_none=True) for m in typed],'stream':True,'max_tokens':1024}
    if registry and registry.definitions():request['tools']=registry.definitions()
    headers={'Authorization':f'Bearer {key}'} if key else {}
    buffer=bytearray();event_lines=[];calls={};text_size=0;total=0;finished=None;done=False;reported_model=None
    async with semaphore:
        try:
            async with asyncio.timeout(p.timeout_ms/1000):
                async with httpx.AsyncClient(transport=adapter.transport or transport_for(base),timeout=p.timeout_ms/1000,follow_redirects=False) as client:
                    async with client.stream('POST',base+'/chat/completions',headers=headers,json=request) as response:
                        if response.status_code in (401,403):raise ProviderFailure('provider_auth_denied')
                        if not 200<=response.status_code<300:raise ProviderFailure('provider_error')
                        if response.headers.get('content-type','').split(';')[0].strip().lower()!='text/event-stream':raise ProviderFailure('invalid_output')
                        async for chunk in response.aiter_bytes():
                            total+=len(chunk)
                            if total>MAX_RESPONSE:raise ProviderFailure('invalid_output')
                            buffer.extend(chunk)
                            while b'\n' in buffer:
                                line,_,remaining=buffer.partition(b'\n');buffer=bytearray(remaining)
                                if len(line)>65536:raise ProviderFailure('invalid_output')
                                line=line.rstrip(b'\r')
                                if line.startswith(b'data:'):event_lines.append(line[5:].lstrip())
                                if sum(map(len,event_lines))>65536:raise ProviderFailure('invalid_output')
                                if line or not event_lines:continue
                                data=b'\n'.join(event_lines);event_lines=[]
                                if data==b'[DONE]':done=True;break
                                value=json.loads(data)
                                if value.get('model'):
                                    if value['model']!=p.model:raise ProviderFailure('model_identity_mismatch')
                                    reported_model=value['model']
                                choices=value.get('choices',[])
                                if not choices:continue # Optional usage-only chunk.
                                if len(choices)!=1 or choices[0].get('index',0)!=0:raise ProviderFailure('invalid_output')
                                choice=choices[0];delta=choice.get('delta',{})
                                content=delta.get('content')
                                if content:
                                    if not isinstance(content,str):raise ProviderFailure('invalid_output')
                                    text_size+=len(content)
                                    if text_size>32000:raise ProviderFailure('invalid_output')
                                    yield StreamEvent(type='text',text=content)
                                for part in delta.get('tool_calls',[]):
                                    index=part['index']
                                    if isinstance(index,bool) or not isinstance(index,int) or not 0<=index<5:raise ProviderFailure('invalid_output')
                                    call=calls.setdefault(index,{'id':'','name':'','arguments':''})
                                    if part.get('type','function')!='function':raise ProviderFailure('invalid_output')
                                    call['id']+=part.get('id','')
                                    function=part.get('function',{})
                                    call['name']+=function.get('name','');call['arguments']+=function.get('arguments','')
                                    if len(call['id'])>100 or len(call['name'])>100 or len(call['arguments'].encode())>8192:raise ProviderFailure('invalid_output')
                                if choice.get('finish_reason') is not None:finished=choice['finish_reason']
                            if len(buffer)>65536:raise ProviderFailure('invalid_output')
                            if done:break
            if not done or finished not in ('stop','tool_calls') or (calls and finished!='tool_calls') or (finished=='tool_calls' and not calls):raise ProviderFailure('incomplete_stream')
            validated=[]
            for index,call in sorted(calls.items()):
                parsed=ToolCall(id=call['id'],name=call['name'],arguments=json.loads(call['arguments']))
                if not registry or parsed.name not in registry.handlers:raise ProviderFailure('unavailable_tool_call')
                if any(c.id==parsed.id for c in validated):raise ProviderFailure('invalid_output')
                validated.append(parsed)
            for call in validated:yield StreamEvent(type='tool_call',call=call)
            yield StreamEvent(type='done',model=reported_model)
        except asyncio.CancelledError:raise
        except (TimeoutError,httpx.TimeoutException):raise ProviderFailure('timeout') from None
        except ProviderFailure:raise
        except httpx.HTTPError:raise ProviderFailure('provider_error') from None
        except (ValueError,KeyError,TypeError,AttributeError):raise ProviderFailure('invalid_output') from None
