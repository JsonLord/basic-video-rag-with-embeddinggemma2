import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import threading
import time
import pytest
from vrag.backup import snapshot,restore,digest,db_snapshot,retention_keep,stale_status

@pytest.fixture
def source(tmp_path,monkeypatch):
    age=os.environ.get('AGE_BIN') or shutil.which('age')
    if not age:pytest.skip('Install age to run real encrypted restore tests')
    monkeypatch.setenv('AGE_BIN',age)
    keygen=str(Path(age).with_name('age-keygen'))
    key=tmp_path/'identity';r=subprocess.run([keygen,'-o',str(key)],capture_output=True,check=True)
    recipient=subprocess.run([keygen,'-y',str(key)],capture_output=True,text=True,check=True).stdout.strip()
    source=tmp_path/'source';data=source/'data';state=source/'state';assets=tmp_path/'object-store'
    state.mkdir(parents=True);(data/'videos/v1').mkdir(parents=True);(assets/'videos/v1').mkdir(parents=True)
    (source/'source-snapshot.json').write_text(json.dumps({'snapshot_id':'test-immutable-v1'}))
    (state/'config-history.json').write_text('[{"version":1}]')
    (state/'.env').write_text('NEVER_INCLUDE_THIS')
    (data/'videos/v1/meta.json').write_text('{"id":"v1","title":"Workshop"}')
    (data/'videos/v1/video.mp4').write_bytes(b'original private video')
    (assets/'videos/v1/video.mp4').write_bytes(b'original private video')
    (data/'live').mkdir();(data/'live/raw-camera.jpg').write_bytes(b'NEVER_INCLUDE_THIS')
    with sqlite3.connect(data/'jobs.sqlite') as db:db.execute('CREATE TABLE test (n INTEGER)');db.execute('INSERT INTO test VALUES (7)')
    output=tmp_path/'snapshots/one.age'
    args=dict(data_root=data,state_root=state,assets_root=assets,output=output,recipient=recipient,source_snapshot_id='test-immutable-v1')
    return args,key

def test_actual_age_roundtrip_and_secret_exclusion(source,tmp_path):
    args,key=source;report=snapshot(**args)
    assert report['coverage_verified'] and report['asset_count']==1
    raw=args['output'].read_bytes();assert raw.startswith(b'age-encryption.org/')
    assert b'Workshop' not in raw and b'NEVER_INCLUDE_THIS' not in raw
    staging=tmp_path/'clean'
    dry=restore(args['output'],key,staging,args['assets_root'],True)
    assert dry['verified'] and not staging.exists()
    result=restore(args['output'],key,staging,args['assets_root'])
    assert staging.stat().st_mode & 0o777 == 0o700
    assert result['verified'] and not (staging/'state/.env').exists() and not (staging/'data/live').exists()
    assert (staging/'data/videos/v1/video.mp4').read_bytes()==b'original private video'
    with sqlite3.connect(staging/'data/jobs.sqlite') as db:assert db.execute('SELECT n FROM test').fetchone()==(7,)
    with pytest.raises(ValueError,match='destination must be new'):restore(args['output'],key,staging,args['assets_root'])

@pytest.mark.parametrize('failure',['missing','corrupt','secret','oversize'])
def test_no_false_success(source,failure):
    args,_=source
    if failure=='missing':(args['assets_root']/'videos/v1/video.mp4').unlink()
    if failure=='corrupt':(args['assets_root']/'videos/v1/video.mp4').write_bytes(b'wrong')
    if failure=='secret':(args['data_root']/'videos/v1/meta.json').write_text('{"token":"sk-abcdefghijklmnopqrstuvwxyz"}')
    if failure=='oversize':(args['data_root']/'videos/v1/meta.json').write_bytes(b'x'*(32*1024*1024+1))
    with pytest.raises(ValueError):snapshot(**args)
    assert not args['output'].exists()

def test_corruption_and_missing_asset_block_restore(source,tmp_path):
    args,key=source;snapshot(**args)
    (args['assets_root']/'videos/v1/video.mp4').unlink()
    with pytest.raises(ValueError):restore(args['output'],key,tmp_path/'stage',args['assets_root'])
    args['output'].write_bytes(args['output'].read_bytes()+b'corrupt')
    with pytest.raises(ValueError,match='integrity'):restore(args['output'],key,tmp_path/'stage',args['assets_root'])
    assert not (tmp_path/'stage').exists()

def test_sqlite_backup_under_concurrent_writes(tmp_path):
    path=tmp_path/'live.sqlite'
    with sqlite3.connect(path) as db:db.execute('CREATE TABLE pairs (n INTEGER)');db.execute('INSERT INTO pairs VALUES (0)');db.execute('INSERT INTO pairs VALUES (0)')
    stop=threading.Event()
    def writes():
        with sqlite3.connect(path) as db:
            n=0
            while not stop.is_set():
                n+=1
                with db:db.execute('UPDATE pairs SET n=?',(n,))
    thread=threading.Thread(target=writes);thread.start()
    try:
        db_snapshot(path,tmp_path/'copy.sqlite')
        with sqlite3.connect(tmp_path/'copy.sqlite') as db:rows=db.execute('SELECT n FROM pairs').fetchall();assert rows[0]==rows[1]
    finally:stop.set();thread.join()

def test_late_run_and_retention_never_remove_newest_good():
    assert stale_status({})['stale']
    assert not stale_status({'last_verified_success':100},now=101)['stale']
    assert stale_status({'last_verified_success':100},now=100+15*3600)['stale']
    assert not stale_status({'last_verified_success':100},now=101)['enabled']
    rows=[{'created_at':1000,'coverage_verified':True,'ciphertext_sha256':'good'},{'created_at':2000,'coverage_verified':False,'ciphertext_sha256':'bad'}]
    assert retention_keep(rows,now=100000000)=={'good'}

def test_retention_preserves_last_restore_qualified_copy():
    rows=[{'created_at':1,'coverage_verified':True,'restore_verified':True,'ciphertext_sha256':'restored'}, {'created_at':10000000,'coverage_verified':True,'ciphertext_sha256':'latest'}]
    keep=retention_keep(rows,now=10000001)
    assert {'restored','latest'}<=keep

def test_workflow_is_private_template_and_schedule_is_exact():
    import yaml
    root=Path(__file__).resolve().parent.parent
    source=root/'deploy/backup-repository/.github/workflows/backup-12h.yml'
    config=yaml.load(source.read_text(),Loader=yaml.BaseLoader)
    assert config['on']['schedule'][0]['cron']=='17 0,12 * * *'
    assert 'workflow_dispatch' in config['on']
    assert config['concurrency']['cancel-in-progress']=='false'
    assert config['jobs']['snapshot']['if']=="vars.BACKUPS_APPROVED == 'true'"
    assert not (root/'.github/workflows/backup-12h.yml').exists()
    assert 'Verify private destination' in [s.get('name') for s in config['jobs']['snapshot']['steps']]
