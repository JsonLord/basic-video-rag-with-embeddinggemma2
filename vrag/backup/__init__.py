"""Legacy format-1 compatibility and shared age/SQLite helpers.

The active GitHub-only format-2 runtime lives in github.py and service.py.
The old snapshot/restore functions below are retained to validate existing format-1
archives; their external-asset contract is not used by the current runtime.
"""
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import subprocess
import tarfile
import tempfile
import time

from config.schema import Configuration

FORMAT=1
MAX_FILE=32*1024*1024
MAX_TOTAL=40*1024*1024
MEDIA_SUFFIXES={'.mp4','.m4a','.webm','.jpg','.jpeg','.png','.wav','.flac','.mov'}
SECRET=re.compile(rb'(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16}|Bearer [A-Za-z0-9._~-]{24,})')

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def safe_file(path,root):
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):raise ValueError('unsafe source file')
    if path.stat().st_size>MAX_FILE:raise ValueError('snapshot file too large')

def db_snapshot(source,dest):
    with sqlite3.connect(f'file:{source}?mode=ro',uri=True) as src,sqlite3.connect(dest) as dst:
        src.backup(dst,pages=128,sleep=.01)
        if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('database integrity failure')
    # SQLite page slack can retain deleted credentials; VACUUM removes free pages.
    with sqlite3.connect(dest) as db:db.execute('VACUUM')

def age(args,**kwargs):
    result=subprocess.run([os.environ.get('AGE_BIN','age'),*map(str,args)],capture_output=True,timeout=120,**kwargs)
    if result.returncode:raise ValueError('age operation failed; check recipient/identity provisioning')
    return result.stdout

def snapshot(data_root,state_root,assets_root,output,recipient,source_snapshot_id,source_revision='unknown'):
    data_root,state_root,assets_root,output=map(Path,(data_root,state_root,assets_root,output))
    if not source_snapshot_id or len(source_snapshot_id)>200:raise ValueError('immutable source snapshot identifier required')
    if assets_root.resolve()==data_root.resolve() or assets_root.resolve().is_relative_to(data_root.resolve()):raise ValueError('media copy must be independent of source data')
    if output.exists():raise ValueError('snapshot output exists')
    if output.resolve().is_relative_to(data_root.resolve()) or output.resolve().is_relative_to(state_root.resolve()):raise ValueError('output must be outside source state')
    if not data_root.is_dir() or not state_root.is_dir():raise ValueError('durable source unavailable')
    # Proof supplied by durable-store exporter, not a flag inferred from local files.
    marker=data_root.parent/'source-snapshot.json'
    if not marker.exists() or json.loads(marker.read_text()).get('snapshot_id')!=source_snapshot_id:raise ValueError('durable source snapshot marker missing or mismatched')
    files={};assets=[];total=0
    with tempfile.TemporaryDirectory(prefix='vm-backup-') as scratch:
        scratch=Path(scratch)
        def add(name,content):
            nonlocal total
            if len(content)>MAX_FILE or total+len(content)>MAX_TOTAL:raise ValueError('snapshot exceeds Git storage budget')
            if SECRET.search(content):raise ValueError('possible credential detected; snapshot refused')
            total+=len(content);files[name]=content
        for filename in ('config-history.json','config-history.backup.json'):
            source=state_root/filename
            if source.exists():
                safe_file(source,state_root)
                history=[Configuration.model_validate(c).model_dump() for c in json.loads(source.read_text())]
                add('state/'+filename,json.dumps(history).encode())
        for name in ('jobs.sqlite',):
            source=data_root/name
            if source.exists():
                safe_file(source,data_root)
                target=scratch/name;db_snapshot(source,target);add('data/'+name,target.read_bytes())
        # Explicit metadata/index scope. Never include .env, logs, answers or live snapshots.
        candidates=[]
        for name in ('meta.json','segments.json','transcript.json'):
            candidates.extend((data_root/'videos').glob('*/'+name))
        for root in (data_root/'index',data_root/'indexes',data_root/'experiments'):
            if root.exists():candidates.extend(p for p in root.rglob('*') if p.is_file() and (p.suffix in ('.json','.npy') or p.name=='CURRENT'))
        for source in sorted(candidates):
            safe_file(source,data_root)
            add('data/'+source.relative_to(data_root).as_posix(),source.read_bytes())
        originals=list((data_root/'videos').glob('*/original'))
        media=originals+[p for p in (data_root/'videos').rglob('*') if p.suffix.lower() in MEDIA_SUFFIXES]
        for source in sorted(set(media)):
            if source.is_symlink() or not source.is_file():raise ValueError('unsafe media')
            relative=source.relative_to(data_root).as_posix();copy=assets_root/relative
            safe_file_unbounded(copy,assets_root)
            checksum=digest(source)
            if copy.stat().st_size!=source.stat().st_size or digest(copy)!=checksum:raise ValueError('durable media missing or checksum mismatch')
            assets.append({'path':relative,'sha256':checksum,'bytes':source.stat().st_size,'location':relative})
        if not files:raise ValueError('empty snapshot refused')
        manifest={'format':FORMAT,'created_at':time.time(),'source_snapshot_id':source_snapshot_id,'source_revision':source_revision,
                  'files':{name:{'bytes':len(value),'sha256':hashlib.sha256(value).hexdigest()} for name,value in files.items()},
                  'assets':assets,'coverage':{'metadata':True,'media_copies_verified':True,'media_count':len(assets),'raw_live_camera':False,'credentials':False,'answer_history':False},
                  'exclusions':['environment credentials','raw live capture','ephemeral sessions','logs','answer history','unrecognized files']}
        archive=scratch/'snapshot.tar.gz'
        with tarfile.open(archive,'w:gz') as tar:
            for name,content in {**files,'manifest.json':json.dumps(manifest).encode()}.items():
                info=tarfile.TarInfo(name);info.size=len(content);info.mode=0o600;tar.addfile(info,io.BytesIO(content))
        output.parent.mkdir(parents=True,exist_ok=True)
        temp=output.with_suffix(output.suffix+'.tmp')
        try:
            age(['-r',recipient,'-o',temp,archive])
            if temp.stat().st_size>MAX_TOTAL:raise ValueError('encrypted snapshot exceeds Git budget')
            os.replace(temp,output)
            envelope={'format':FORMAT,'created_at':manifest['created_at'],'ciphertext_sha256':digest(output),'bytes':output.stat().st_size,'coverage_verified':True,'asset_count':len(assets)}
            output.with_suffix('.json').write_text(json.dumps(envelope))
            return envelope
        except BaseException:
            temp.unlink(missing_ok=True);output.unlink(missing_ok=True);output.with_suffix('.json').unlink(missing_ok=True);raise

def safe_file_unbounded(path,root):
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):raise ValueError('durable media missing or unsafe')

def restore(archive,identity,destination,assets_root,dry_run=False):
    archive,identity,destination,assets_root=map(Path,(archive,identity,destination,assets_root))
    envelope=json.loads(archive.with_suffix('.json').read_text())
    if envelope.get('format')!=FORMAT or digest(archive)!=envelope['ciphertext_sha256']:raise ValueError('ciphertext integrity mismatch')
    if destination.exists():raise ValueError('restore destination must be new; production is never overwritten')
    if archive.stat().st_size>MAX_TOTAL:raise ValueError('archive too large')
    with tempfile.TemporaryDirectory(prefix='vm-restore-') as scratch:
        clear=Path(scratch)/'snapshot.tar.gz'
        age(['-d','-i',identity,'-o',clear,archive])
        import gzip
        with gzip.open(clear,'rb') as compressed:
            expanded=compressed.read(MAX_TOTAL+1024*1024+1)
        if len(expanded)>MAX_TOTAL+1024*1024:raise ValueError('expanded archive exceeds limits')
        with tarfile.open(fileobj=io.BytesIO(expanded),mode='r:') as tar:
            members=tar.getmembers()
            if len(members)>30000 or sum(m.size for m in members)>MAX_TOTAL+1024*1024:raise ValueError('expanded archive exceeds limits')
            names=[m.name for m in members]
            if len(names)!=len(set(names)):raise ValueError('duplicate archive path')
            for m in members:
                path=PurePosixPath(m.name)
                if not m.isfile() or path.is_absolute() or '..' in path.parts or '\\' in m.name:raise ValueError('unsafe archive member')
            manifest=json.load(tar.extractfile('manifest.json'))
            if manifest['format']!=FORMAT or set(names)!=set(manifest['files'])|{'manifest.json'}:raise ValueError('manifest mismatch')
            contents={}
            for name,expected in manifest['files'].items():
                if not name.startswith(('data/','state/')):raise ValueError('unexpected state path')
                content=tar.extractfile(name).read()
                if len(content)!=expected['bytes'] or hashlib.sha256(content).hexdigest()!=expected['sha256']:raise ValueError('snapshot checksum mismatch')
                if SECRET.search(content):raise ValueError('credential found in snapshot')
                contents[name]=content
            for asset in manifest['assets']:
                path=PurePosixPath(asset['path'])
                if path.is_absolute() or '..' in path.parts or not str(path).startswith('videos/'):raise ValueError('unsafe asset path')
                source=assets_root/path
                safe_file_unbounded(source,assets_root)
                if source.stat().st_size!=asset['bytes'] or digest(source)!=asset['sha256']:raise ValueError('missing or corrupt restore asset')
            if not dry_run:
                # Entire restore is staged beside destination and renamed only on success.
                destination.parent.mkdir(parents=True,exist_ok=True)
                with tempfile.TemporaryDirectory(dir=destination.parent,prefix='.restore-') as staging:
                    staging=Path(staging)/'state';staging.mkdir(mode=0o700)
                    for name,content in contents.items():
                        target=staging/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content);target.chmod(0o600)
                    for asset in manifest['assets']:
                        target=staging/'data'/asset['path'];target.parent.mkdir(parents=True,exist_ok=True)
                        import shutil
                        shutil.copyfile(assets_root/asset['path'],target);target.chmod(0o600)
                    for db in staging.rglob('*.sqlite'):
                        with sqlite3.connect(db) as conn:
                            if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('restored database invalid')
                    for asset in manifest['assets']:
                        if digest(staging/'data'/asset['path'])!=asset['sha256']:raise ValueError('asset changed while restoring')
                    if destination.exists():raise ValueError('restore destination appeared')
                    os.rename(staging,destination)
            return {'verified':True,'dry_run':dry_run,'files':len(contents),'assets':len(manifest['assets']),'source_snapshot_id':manifest['source_snapshot_id']}

def stale_status(report,now=None):
    now=time.time() if now is None else now
    last=report.get('last_verified_success')
    age_seconds=now-last if isinstance(last,(int,float)) else None
    return {**report,'age_seconds':age_seconds,'stale':age_seconds is None or age_seconds>14*3600,
            'enabled':bool(report.get('private_repository_verified') and report.get('workflow_run_id') and report.get('restore_verified') and last)}

def retention_keep(envelopes,now=None):
    """14 days of snapshots, 8 weekly and 6 monthly; newest verified always kept."""
    now=time.time() if now is None else now
    valid=sorted((e for e in envelopes if e.get('coverage_verified')),key=lambda e:e['created_at'],reverse=True)
    if not valid:return set()
    restored=[e for e in valid if e.get('restore_verified')]
    if not restored:return {e['ciphertext_sha256'] for e in valid}
    keep={valid[0]['ciphertext_sha256'],restored[0]['ciphertext_sha256']};weeks=set();months=set()
    for e in valid:
        age_seconds=now-e['created_at'];week=int(age_seconds//(7*86400));month=int(age_seconds//(30*86400))
        if age_seconds<=14*86400 or (week<8 and week not in weeks) or (month<6 and month not in months):keep.add(e['ciphertext_sha256'])
        weeks.add(week);months.add(month)
    return keep
