"""Persistent, single-worker media queue. No local inference; staged resumable work."""
import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sqlite3
import time
import uuid

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from .config import DATA, VIDEOS_DIR, INDEX_DIR
from .mentor_api import user
from .providers import ProviderFailure
from .routing import route
from .settings import store
from .remote import space_id

router=APIRouter(prefix='/api')
MAX_UPLOAD=64*1024*1024
MAX_DURATION=1800
upload_slots=asyncio.Semaphore(2)

def connect():
    DATA.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DATA/'jobs.sqlite',timeout=10)
    db.row_factory=sqlite3.Row
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, video_id TEXT, title TEXT, status TEXT, stage TEXT, error TEXT, created REAL, updated REAL, attempts INTEGER DEFAULT 0, transcript TEXT)')
    return db

def update(jid, **values):
    values['updated']=time.time()
    with connect() as db:
        db.execute('UPDATE jobs SET '+','.join(f'{k}=?' for k in values)+' WHERE id=?', [*values.values(),jid])

def listing():
    with connect() as db:return [dict(r) for r in db.execute('SELECT id,video_id,title,status,stage,error,created,updated,attempts FROM jobs ORDER BY created DESC LIMIT 100')]

def check_cancel(jid):
    with connect() as db:row=db.execute('SELECT status FROM jobs WHERE id=?',(jid,)).fetchone()
    if not row or row['status']=='cancelled':raise asyncio.CancelledError()

async def command(*args, timeout=180):
    proc=await asyncio.create_subprocess_exec(*map(str,args),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
    try:
        out,err=await asyncio.wait_for(proc.communicate(),timeout)
        if proc.returncode:raise ProviderFailure('media_processing_failed')
        return out
    finally:
        if proc.returncode is None:
            proc.kill();await proc.wait()

async def run_job(job):
    jid,vid=job['id'],job['video_id'];vdir=VIDEOS_DIR/vid
    check_cancel(jid)
    update(jid,status='running',stage='probe',error=None,attempts=job['attempts']+1)
    probe=json.loads(await command('ffprobe','-v','error','-show_format','-show_streams','-of','json',vdir/'original',timeout=20))
    duration=float(probe['format']['duration'])
    if not math.isfinite(duration) or not 0<duration<=MAX_DURATION:raise ProviderFailure('duration_limit_30_minutes')
    if not any(s['codec_type']=='video' for s in probe['streams']):raise ProviderFailure('video_stream_required')
    check_cancel(jid)
    update(jid,stage='proxy')
    if not (vdir/'video.mp4').exists():
        await command('ffmpeg','-hide_banner','-loglevel','error','-nostdin','-i',vdir/'original','-vf','scale=640:-2','-r','15','-c:v','libx264','-threads','1','-preset','veryfast','-crf','26','-c:a','aac','-movflags','+faststart','-y',vdir/'proxy.tmp.mp4',timeout=600)
        os.replace(vdir/'proxy.tmp.mp4',vdir/'video.mp4')
    await command('ffmpeg','-hide_banner','-loglevel','error','-nostdin','-i',vdir/'video.mp4','-frames:v','1','-threads','1','-y',vdir/'thumb.jpg')
    meta=dict(id=vid,title=job['title'],duration=duration,source_file='Browser upload',youtube_id=None,webpage_url=None,view_count=None,channel_position=None,transcript_source='remote',transcript_engine='whisper')
    (vdir/'meta.json').write_text(json.dumps(meta))
    (vdir/'segments').mkdir(exist_ok=True)
    _,cfg=store.snapshot()
    update(jid,stage='transcription')
    if job['transcript']:
        cues=[{'start':0,'end':duration,'text':job['transcript']}]
        meta.update(transcript_source='user supplied',transcript_engine='manual')
    elif (vdir/'transcript.json').exists():cues=json.loads((vdir/'transcript.json').read_text())
    else:
        if not any(s['codec_type']=='audio' for s in probe['streams']):raise ProviderFailure('transcript_required_video_has_no_audio')
        cues=[]
        for start in range(0,math.ceil(duration),30):
            check_cancel(jid)
            audio=vdir/'speech.m4a'
            await command('ffmpeg','-hide_banner','-loglevel','error','-nostdin','-ss',start,'-i',vdir/'original','-t','30','-vn','-ac','1','-ar','16000','-c:a','aac','-b:a','48k','-threads','1','-y',audio)
            out,status=await route(cfg,'audio.transcription',{'audio':audio.read_bytes(),'audio_filename':'speech.m4a','audio_mime':'audio/mp4'})
            audio.unlink(missing_ok=True)
            if not out.text:raise ProviderFailure(status[-1]['status'] if status else 'transcription_unavailable')
            cues.append({'start':start,'end':min(start+30,duration),'text':out.text})
    (vdir/'transcript.json').write_text(json.dumps(cues))
    (vdir/'meta.json').write_text(json.dumps(meta))
    update(jid,stage='segmentation')
    segments=[]
    for idx,start in enumerate(range(0,math.ceil(duration),30)):
        check_cancel(jid)
        end=min(start+30,duration)
        text=' '.join(c['text'] for c in cues if c['start']<end and c['end']>start)
        segments.append(dict(id=f'{vid}_{idx:03d}',video_id=vid,title=job['title'],idx=idx,start=start,end=end,text=text))
        await command('ffmpeg','-hide_banner','-loglevel','error','-nostdin','-ss',min(start+1,duration/2),'-i',vdir/'video.mp4','-frames:v','1','-threads','1','-y',vdir/'segments'/f'{idx:03d}.jpg')
    (vdir/'segments.json').write_text(json.dumps(segments))
    update(jid,stage='embeddings')
    # Rebuild a complete, separate revision. Atomic CURRENT pointer avoids mixed vectors.
    rule=cfg.features.get('rag.text_embeddings')
    if not rule or not rule.enabled or rule.strategy!='single':raise ProviderFailure('embedding_provider_unavailable')
    provider=cfg.providers[rule.providers[0]]
    corpus=[]
    for source in sorted(VIDEOS_DIR.glob('*/segments.json')):corpus.extend(json.loads(source.read_text()))
    if len(corpus)>10000:raise ProviderFailure('corpus_limit_10000_segments')
    from .index import get_index
    previous=get_index()
    previous_manifest=previous.path/'manifest.json'
    reusable={}
    if previous_manifest.exists() and json.loads(previous_manifest.read_text()).get('embedding_space')==space_id(provider) and 'text' in previous.views:
        reusable={s['id']:(s,previous.views['text'][i].tolist()) for i,s in enumerate(previous.segments)}
    vectors=[]
    for seg in corpus:
        check_cancel(jid)
        old=reusable.get(seg['id'])
        if old and all(old[0].get(k)==seg.get(k) for k in ('title','text','start','end')):
            vectors.append(old[1]);continue
        out,status=await route(cfg,'rag.text_embeddings',{'text':f'title: {seg["title"]} | text: {seg["text"]}'})
        if not out.embedding:raise ProviderFailure(status[-1]['status'] if status else 'embedding_provider_unavailable')
        vectors.append(out.embedding)
    matrix=np.asarray(vectors,dtype=np.float32)
    if matrix.ndim!=2 or not np.isfinite(matrix).all() or (np.linalg.norm(matrix,axis=1)==0).any():raise ProviderFailure('invalid_embedding_matrix')
    matrix/=np.linalg.norm(matrix,axis=1,keepdims=True)
    revision=uuid.uuid4().hex
    output=INDEX_DIR/'revisions'/revision;output.mkdir(parents=True)
    np.save(output/'text.npy',matrix)
    (output/'segments.json').write_text(json.dumps(corpus))
    manifest=dict(model=provider.model,embedding_space=space_id(provider),dimension=matrix.shape[1],mrl_dims=[matrix.shape[1]],views={'text':{'count':len(corpus)}},segments=len(corpus),corpus_revision=revision,preprocessing='title-text-v1',segmentation='30s-v1',modality='text',built_at=time.time())
    (output/'manifest.json').write_text(json.dumps(manifest))
    check_cancel(jid)
    if store.snapshot()[1].providers.get(rule.providers[0])!=provider:raise ProviderFailure('provider_changed_retry_required')
    pointer=INDEX_DIR/'.CURRENT.tmp';pointer.write_text(revision);os.replace(pointer,INDEX_DIR/'CURRENT')
    from .index import get_index
    get_index.cache_clear()
    update(jid,status='complete',stage='searchable',error=None)

async def worker():
    with connect() as db:db.execute("UPDATE jobs SET status='queued' WHERE status='running'")
    while True:
        with connect() as db:job=db.execute("SELECT * FROM jobs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if job:
            try:await run_job(dict(job))
            except asyncio.CancelledError:
                # Shutdown preserves retryable queue state; user cancellation is durable.
                check=False
                with connect() as db:check=db.execute('SELECT status FROM jobs WHERE id=?',(job['id'],)).fetchone()[0]=='cancelled'
                if not check:raise
            except ProviderFailure as exc:update(job['id'],status='blocked',error=exc.code)
            except Exception:update(job['id'],status='failed',error='job_failed_check_media_and_configuration')
        await asyncio.sleep(0.5)

@router.get('/jobs')
def jobs(owner=Depends(user)):return listing()

@router.post('/ingest')
async def upload(request:Request,filename:str=Query('Upload',max_length=200),owner=Depends(user)):
    if upload_slots.locked():raise HTTPException(429,'two uploads already in progress')
    async with upload_slots:
        return await _upload(request,filename)

async def _upload(request,filename):
    if sum(j['status'] in ('queued','running') for j in listing())>=10:raise HTTPException(429,'queue full')
    if shutil.disk_usage(DATA).free<MAX_UPLOAD*4:raise HTTPException(507,'insufficient disk space')
    jid=uuid.uuid4().hex;temp=DATA/('upload-'+jid)
    size=0;digest=hashlib.sha256()
    try:
        async with asyncio.timeout(300):
            with temp.open('xb') as out:
                async for chunk in request.stream():
                    size+=len(chunk)
                    if size>MAX_UPLOAD:raise HTTPException(413,'upload exceeds 64 MiB')
                    out.write(chunk);digest.update(chunk)
        if not size:raise HTTPException(422,'empty video')
        if sum(j['status'] in ('queued','running') for j in listing())>=10:raise HTTPException(429,'queue full')
        vid='upload-'+digest.hexdigest()[:24]
        vdir=VIDEOS_DIR/vid;vdir.mkdir(parents=True,exist_ok=True)
        with connect() as db:existing=db.execute('SELECT id FROM jobs WHERE video_id=?',(vid,)).fetchone()
        if existing:return {'id':existing['id'],'deduplicated':True}
        os.replace(temp,vdir/'original')
        now=time.time()
        with connect() as db:db.execute('INSERT INTO jobs (id,video_id,title,status,stage,created,updated) VALUES (?,?,?,?,?,?,?)',(jid,vid,filename,'queued','upload',now,now))
        return {'id':jid,'video_id':vid,'status':'queued'}
    except TimeoutError:raise HTTPException(408,'upload timeout') from None
    finally:temp.unlink(missing_ok=True)

class JobAction(BaseModel):
    action:str=Field(pattern='^(retry|cancel)$')
    transcript:str|None=Field(default=None,max_length=64000)

@router.post('/jobs/{jid}')
def action(jid:str,body:JobAction,owner=Depends(user)):
    job=next((j for j in listing() if j['id']==jid),None)
    if not job:raise HTTPException(404,'unknown job')
    if body.action=='retry' and job['status'] not in ('blocked','failed','cancelled'):raise HTTPException(409,'job is already active or complete')
    values={'status':'queued' if body.action=='retry' else 'cancelled','error':None}
    if body.transcript is not None:values['transcript']=body.transcript
    update(jid,**values)
    return {'status':values['status']}
