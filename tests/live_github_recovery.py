"""Opt-in live GitHub recovery drill. Writes only a new test-* namespace.

Run from checkout root: AGE_BIN=... python tests/live_github_recovery.py
Prefers VM_BACKUP_GITHUB_TOKEN, otherwise the existing GH_TOKEN; never prints credentials.
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
from vrag.backup.github import Checkpoints,GitHubStore,GitHubPermanentError,digest


def main():
    namespace='test-recovery-'+time.strftime('%Y%m%d')+'-'+uuid.uuid4().hex[:8]
    repo='JsonLord/visual-mentor-backups'
    evidence=Path('docs/evidence/github-recovery-live.json')
    events=[]
    expected={}
    def diagnostic(event):
        events.append(event)
        evidence.write_text(json.dumps({'live':True,'status':'in_progress','namespace':namespace,'repository':repo,'credential_source':'VM_BACKUP_GITHUB_TOKEN' if os.environ.get('VM_BACKUP_GITHUB_TOKEN') else 'GH_TOKEN','http_events':events,'fixture_file_hashes':expected},indent=2)+'\n')
    evidence.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='vm-live-recovery-') as temp:
        temp=Path(temp);key=temp/'protected.agekey'
        binary=os.environ.get('AGE_BIN','age');keygen=str(Path(binary).with_name('age-keygen'))
        subprocess.run([keygen,'-o',str(key)],capture_output=True,check=True)
        recipient=subprocess.run([keygen,'-y',str(key)],capture_output=True,text=True,check=True).stdout.strip()
        remote=GitHubStore(repo,namespace,token=os.environ.get('VM_BACKUP_GITHUB_TOKEN') or os.environ['GH_TOKEN'],diagnostic=diagnostic)
        backup=Checkpoints(remote,recipient,key)
        root=temp/'work';data,state=make_library(root);stage=temp/'stage';stage.mkdir()
        backup.capture(data,state,stage)
        expected={p.relative_to(stage).as_posix():digest(p) for p in stage.rglob('*') if p.is_file()}
        first=None
        try:
            first=backup.backup(stage)
            second=backup.backup(stage)
        except GitHubPermanentError as error:
            report=json.loads(evidence.read_text())
            report.update(status='blocked',failure_code=error.code,status_code=error.status,failure_host=error.host,request_id=error.request_id,committed_checkpoints=1 if first else 0,first_checkpoint=first['checkpoint'] if first else None,recovery_verified=False)
            evidence.write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps({'status':'blocked','failure_code':error.code,'host':error.host,'status_code':error.status,'request_id':error.request_id}))
            return False
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
from pathlib import Path
from vrag.backup.github import digest
import os,json
root=Path(os.environ['VM_RECOVERY_ROOT'])
restored_hashes={p.relative_to(root).as_posix():digest(p) for p in root.rglob('*') if p.is_file() and p.name!='backup-health.json'}
from fastapi.testclient import TestClient
from vrag.api import app,rag
import numpy as np
async def synthetic_query(text):return np.array([1,0,0],dtype=np.float32)
rag.query=synthetic_query # deterministic query vector; no live provider claim
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
    search=client.get('/api/search',params={'q':'blue test video','dim':3,'view':'text'},headers=headers)
    assert search.status_code==200 and search.json()['hits'][0]['video_id']=='v1'
    media=client.get('/media/v1/video.mp4',headers={**headers,'Range':'bytes=0-31'})
    assert media.status_code==206 and len(media.content)==32
    assert client.get('/media/v1/video.mp4').status_code==401
    c=client.get('/api/config',headers={'Authorization':'Bearer '+os.environ['VM_ADMIN_TOKEN']})
    assert c.status_code==200 and c.json()['config']['profile']=='recovered'
print(json.dumps({'fresh_app_library':True,'index_segments':1,'configuration_recovered':True,'search_route':True,'query_embedding':'synthetic deterministic stub','media_range':True,'anonymous_media_denied':True,'restored_file_hashes':restored_hashes}))
'''
        result=subprocess.run([sys.executable,'-c',code],env=env,capture_output=True,text=True,timeout=300)
        if result.returncode:raise ValueError('fresh application recovery verification failed: '+result.stderr[-1800:])
        child=json.loads(result.stdout.strip().splitlines()[-1])
        assert child['restored_file_hashes']==expected,'pre-startup recovered file hashes differ'
        subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(root/'data/videos/v1/video.mp4'),'-f','null','-'],capture_output=True,check=True,timeout=30)
        # Application startup may alter SQLite journal metadata; verify logical rows too.
        import sqlite3
        with sqlite3.connect(root/'data/jobs.sqlite') as database:
            assert database.execute('SELECT status FROM jobs').fetchone()==('complete',)

        report={'live':True,'repository':repo,'namespace':namespace,'first_checkpoint':first['checkpoint'],
                'recovered_checkpoint':second['checkpoint'],'files':len(expected),'all_file_hashes_match':True,'file_hashes':expected,'media_decode_verified':True,'sqlite_integrity_and_rows_match':True,
                'incremental_unchanged_checkpoint_assets':len(newest),'encrypted_asset_bytes':sum(a['size'] for rows in assets.values() for a in rows),
                'fresh_application_checks':child,'status':'passed','http_events':events,'asset_counts':{tag:len(rows) for tag,rows in assets.items()},
                'key_disposition':'ephemeral test identity destroyed after drill; no production keys used',
                'scheduling_verified':False}
        output=Path('docs/evidence/github-recovery-live.json');output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:v for k,v in report.items() if k not in ('http_events','file_hashes','fresh_application_checks')}))
        return True


if __name__=='__main__':
    try:
        passed=main()
    except Exception as error:
        evidence=Path('docs/evidence/github-recovery-live.json')
        report=json.loads(evidence.read_text()) if evidence.exists() else {}
        report.update(status='failed',failure_code='live_drill_failed',error_type=type(error).__name__,recovery_verified=False)
        evidence.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({'status':'failed','error_type':type(error).__name__}))
        passed=False
    raise SystemExit(0 if passed else 2)
