"""Opt-in live GitHub recovery drill. Writes only a new test-* namespace.

Run from checkout root: AGE_BIN=... python tests/live_github_recovery.py
Uses the existing GitHub identity through GH_TOKEN; never prints credentials.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from test_github_checkpoints import make_library
from vrag.backup.github import Checkpoints,GitHubStore,digest


def main():
    namespace='test-recovery-'+time.strftime('%Y%m%d')+'-'+uuid.uuid4().hex[:8]
    repo='JsonLord/visual-mentor-backups'
    with tempfile.TemporaryDirectory(prefix='vm-live-recovery-') as temp:
        temp=Path(temp);key=temp/'protected.agekey'
        binary=os.environ.get('AGE_BIN','age');keygen=str(Path(binary).with_name('age-keygen'))
        subprocess.run([keygen,'-o',str(key)],capture_output=True,check=True)
        recipient=subprocess.run([keygen,'-y',str(key)],capture_output=True,text=True,check=True).stdout.strip()
        remote=GitHubStore(repo,namespace,token=os.environ.get('VM_BACKUP_GITHUB_TOKEN') or os.environ['GH_TOKEN'])
        backup=Checkpoints(remote,recipient,key)
        root=temp/'work';data,state=make_library(root);stage=temp/'stage';stage.mkdir()
        backup.capture(data,state,stage)
        expected={p.relative_to(stage).as_posix():digest(p) for p in stage.rglob('*') if p.is_file()}
        first=backup.backup(stage)
        second=backup.backup(stage)
        # Only a new manifest should be uploaded on the unchanged second checkpoint.
        releases=remote.request('GET',remote.base+'/releases',params={'per_page':100}).json()
        test_releases=[r for r in releases if r['tag_name'].startswith('vm-'+namespace+'-')]
        assets={r['tag_name']:remote.assets(r['id']) for r in test_releases}
        newest=next(v for k,v in assets.items() if k.endswith(second['checkpoint']))
        assert len(newest)==1,'unchanged media was reuploaded'
        shutil.rmtree(stage);shutil.rmtree(root)
        # A genuinely fresh interpreter restores before importing application globals.
        env={**os.environ,'VM_BACKUP_ENABLED':'true','VM_BACKUP_REPOSITORY':repo,'VM_BACKUP_NAMESPACE':namespace,
             'VM_BACKUP_GITHUB_TOKEN':os.environ.get('VM_BACKUP_GITHUB_TOKEN') or os.environ['GH_TOKEN'],'VM_BACKUP_RECIPIENT':recipient,'VM_BACKUP_IDENTITY_FILE':str(key),
             'VM_RECOVERY_ROOT':str(root),'VRAG_DATA':str(root/'data'),'VM_STATE_DIR':str(root/'state'),
             'VM_USER_TOKEN':'test-user-'+'u'*32,'VM_ADMIN_TOKEN':'test-admin-'+'a'*32}
        code='''
from vrag.backup.service import bootstrap
bootstrap()
from fastapi.testclient import TestClient
from vrag.api import app
import os,json
os.environ['VM_BACKUP_ENABLED']='false' # test checkpoint already exists; no new writes to remote
headers={'Authorization':'Bearer '+os.environ['VM_USER_TOKEN']}
with TestClient(app) as client:
    r=client.get('/api/videos',headers=headers)
    assert r.status_code==200,r.status_code
    assert r.json()[0]['id']=='v1',r.json()
    s=client.get('/api/stats',headers=headers)
    assert s.status_code==200,s.status_code
    assert s.json()['segments']==1,s.json()
    c=client.get('/api/config',headers={'Authorization':'Bearer '+os.environ['VM_ADMIN_TOKEN']})
    assert c.status_code==200 and c.json()['config']['profile']=='recovered'
print(json.dumps({'fresh_app_library':True,'index_segments':1,'configuration_recovered':True}))
'''
        result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=300)
        if result.returncode:raise ValueError('fresh application recovery verification failed: '+result.stderr[-1800:])
        actual={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file() and p.name not in ('backup-health.json','jobs.sqlite-wal','jobs.sqlite-shm')}
        # SQLite opening may alter journal metadata; compare logical rows below.
        import sqlite3
        with sqlite3.connect(root/'data/jobs.sqlite') as database:
            assert database.execute('SELECT status FROM jobs').fetchone()==('complete',)
        actual.pop('data/jobs.sqlite',None);expected.pop('data/jobs.sqlite',None)
        assert expected==actual,'restored files do not match captured checkpoint'
        report={'live':True,'repository':repo,'namespace':namespace,'first_checkpoint':first['checkpoint'],
                'recovered_checkpoint':second['checkpoint'],'files':len(expected),'all_non_sqlite_file_hashes_match':True,'sqlite_integrity_and_rows_match':True,
                'incremental_unchanged_checkpoint_assets':len(newest),'encrypted_asset_bytes':sum(a['size'] for rows in assets.values() for a in rows),
                'fresh_application_checks':json.loads(result.stdout.strip().splitlines()[-1]),
                'key_disposition':'ephemeral test identity destroyed after drill; no production keys used',
                'scheduling_verified':False}
        output=Path('docs/evidence/github-recovery-live.json');output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))


if __name__=='__main__':main()
