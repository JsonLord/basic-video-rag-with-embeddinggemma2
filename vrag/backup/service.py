"""Single-process backup queue and pre-import empty-filesystem recovery."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import time

from .github import Checkpoints, GitHubStore, GitHubPermanentError, state_lock


def configured():
    return os.environ.get('VM_BACKUP_ENABLED') == 'true'


def provision_identity():
    # HF Secrets injects this directly; it is not a network-proxy credential.
    # The temporary key file is outside application state and never backed up.
    if os.environ.get('VM_BACKUP_IDENTITY_FILE'):
        return
    identity=os.environ.get('VM_BACKUP_IDENTITY','')
    if not identity:
        raise ValueError('protected age recovery identity required')
    fd,path=tempfile.mkstemp(prefix='vm-protected-identity-',suffix='.agekey')
    with os.fdopen(fd,'w') as output:
        output.write(identity+'\n')
    os.chmod(path,0o600)
    os.environ['VM_BACKUP_IDENTITY_FILE']=path
    # Child processes need only the protected path, not another copy of the key.
    os.environ.pop('VM_BACKUP_IDENTITY',None)


def engine():
    provision_identity()
    return Checkpoints(GitHubStore(os.environ['VM_BACKUP_REPOSITORY'],os.environ.get('VM_BACKUP_NAMESPACE','production')),
                       os.environ['VM_BACKUP_RECIPIENT'],os.environ['VM_BACKUP_IDENTITY_FILE'])


def roots():
    root=Path(os.environ.get('VM_RECOVERY_ROOT','/app/work')).resolve()
    data=Path(os.environ.get('VRAG_DATA',root/'data')).resolve()
    state=Path(os.environ.get('VM_STATE_DIR',root/'state')).resolve()
    if data!=root/'data' or state!=root/'state':raise ValueError('backup requires data and state under VM_RECOVERY_ROOT')
    if Path(os.environ.get('VRAG_INDEX_DIR',data/'index')).resolve()!=data/'index':
        raise ValueError('external index path is not covered')
    identity=Path(os.environ['VM_BACKUP_IDENTITY_FILE']).resolve()
    if identity.is_relative_to(root):raise ValueError('identity must be provisioned outside application state')
    return root,data,state


def bootstrap():
    if not configured():return
    provision_identity()
    root,data,state=roots()
    if root.exists() and any(p.is_file() for p in root.rglob('*')):return
    root.parent.mkdir(parents=True,exist_ok=True)
    if root.exists():
        import shutil
        shutil.rmtree(root)  # empty directories only, checked above
    backup=engine()
    if not backup.store.checkpoints():
        backup.store.verify()
        if os.environ.get('VM_BACKUP_ALLOW_EMPTY')!='true':raise ValueError('no checkpoint; explicit first-start authorization required')
        data.mkdir(parents=True);state.mkdir()
        return
    result=backup.restore(root)
    write_health({**default_health(),'last_recovery_test':result,'last_success':{'checkpoint':result['checkpoint'],'created_at':result['created_at']},'restore_points':[result['checkpoint']]})


def default_health():
    return {'configured':configured(),'last_success':None,'pending_uploads':None,'failure_code':None,
            'last_recovery_test':None,'restore_points':[],'encrypted_storage_bytes':None,'queued':False}


def health_path():
    return Path(os.environ['VM_STATE_DIR'])/'backup-health.json'


def health():
    report=default_health()
    if configured() and health_path().exists():
        try:
            report.update(json.loads(health_path().read_text()))
        except (OSError,ValueError,TypeError):
            report['failure_code']='health_cache_invalid'
    last=(report.get('last_success') or {}).get('created_at')
    report['stale']=last is None or time.time()-last>14*3600
    return report


def write_health(report):
    path=health_path();path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(report));temp.chmod(0o600);os.replace(temp,path)


class BackupQueue:
    def __init__(self):
        self.event=asyncio.Event();self.report=None
        self.busy=False;self.recovery_requested=False

    def request(self, recovery=False):
        if not configured():return False
        self.recovery_requested|=recovery
        self.event.set()
        return True

    def update(self, **values):
        self.report.update(values);write_health(self.report)

    async def run(self):
        self.report=health()
        # A checkpoint on boot catches changes made before an interrupted trigger.
        self.event.set()
        while True:
            try:
                # Validated locally as a fallback timer, not a wake mechanism.
                await asyncio.wait_for(self.event.wait(),timeout=12*3600)
            except TimeoutError:pass
            self.event.clear();self.busy=True
            recovery=self.recovery_requested;self.recovery_requested=False
            self.update(queued=True,last_attempt=time.time(),failure_code=None)
            try:
                backup=engine();_,data,state=roots()
                for attempt in range(3):
                    try:
                        with tempfile.TemporaryDirectory(prefix='vm-capture-') as stage:
                            stage=Path(stage)
                            await asyncio.wait_for(state_lock.acquire(),timeout=90)
                            try:
                                capture=asyncio.create_task(asyncio.to_thread(backup.capture,data,state,stage))
                                try:
                                    await asyncio.shield(capture)
                                except asyncio.CancelledError:
                                    await capture
                                    raise
                            finally:
                                state_lock.release()
                            result=await asyncio.to_thread(backup.backup,stage,self.update)
                        self.update(last_success=result,pending_uploads=0)
                        break
                    except GitHubPermanentError:
                        raise
                    except Exception:
                        if attempt==2:raise
                        await asyncio.sleep(2**attempt)
                rows=await asyncio.to_thread(backup.store.checkpoints)
                self.update(restore_points=[Path(r['path']).stem for r in rows])
                # Actual encrypted usage includes orphaned assets and historical
                # releases, not just objects referenced by the newest checkpoint.
                total=0
                for page in range(1,1001):
                    releases=await asyncio.to_thread(backup.store.request,'GET',backup.store.base+'/releases',params={'per_page':100,'page':page})
                    releases=releases.json()
                    for release in releases:
                        if release['tag_name'].startswith('vm-'+backup.store.namespace+'-'):
                            assets=await asyncio.to_thread(backup.store.assets,release['id'])
                            total+=sum(a['size'] for a in assets)
                    if len(releases)<100:break
                else:raise ValueError('storage inventory listing limit')
                self.update(encrypted_storage_bytes=total)
                if recovery:
                    with tempfile.TemporaryDirectory(prefix='vm-recovery-test-') as temp:
                        result=await asyncio.to_thread(backup.restore,Path(temp)/'recovered')
                    self.update(last_recovery_test=result)
            except asyncio.CancelledError:raise
            except GitHubPermanentError as error:
                self.update(failure_code=error.code)
            except Exception:
                # Never expose exception text containing provider credentials.
                self.update(failure_code='backup_or_recovery_failed',last_recovery_test={'verified':False,'tested_at':time.time()} if recovery else self.report.get('last_recovery_test'))
            finally:
                self.busy=False;self.update(queued=self.event.is_set())


queue=BackupQueue()
