"""GitHub-only encrypted checkpoints. No plaintext state leaves this process.

Writers and snapshot capture share state_lock. Uploads happen after capture, and
an immutable repository record is committed only after all assets read back.
"""
import asyncio
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import sqlite3
import tempfile
import time
import uuid

import httpx

from . import age, db_snapshot, digest, SECRET

state_lock = asyncio.Lock()
CHUNK = 16 * 1024 * 1024
ASSETS_PER_RELEASE = 800
MAX_FILES = 100000
MAX_BYTES = 20 * 1024**3


def encode(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')).encode()


def safe_path(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or not p.parts or p.parts[0] not in ('data', 'state'):
        raise ValueError('unsafe recovery path')
    return p


class GitHubPermanentError(ValueError):
    """A rejected credential/request must not be retried with the same input."""
    def __init__(self, status, host, request_id=None):
        self.status, self.host, self.request_id = status, host, request_id
        self.code = 'github_authentication_failed' if status == 401 else 'github_request_rejected'
        super().__init__(f'{self.code}: status={status} host={host}')


def safe_http_event(response):
    allowed = ('x-github-request-id', 'x-github-api-version-selected',
               'x-ratelimit-limit', 'x-ratelimit-remaining', 'x-ratelimit-resource',
               'x-accepted-github-permissions', 'x-oauth-scopes', 'content-type', 'server')
    headers = {k:response.headers[k][:512] for k in allowed if k in response.headers}
    if 'www-authenticate' in response.headers:
        headers['www-authenticate'] = response.headers['www-authenticate'].split(' ',1)[0]
    return {'method':response.request.method, 'host':response.request.url.host,
            'status':response.status_code, 'headers':headers,
            'client_authorization_attached':bool(response.request.headers.get('authorization'))}


class GitHubStore:
    def __init__(self, repo, namespace='production', token=None, client=None, diagnostic=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
            raise ValueError('invalid repository')
        if not re.fullmatch(r'[a-z0-9-]{1,60}', namespace):
            raise ValueError('invalid namespace')
        self.repo, self.namespace = repo, namespace
        self.diagnostic = diagnostic or (lambda event: None)
        self.client = client or httpx.Client(timeout=120, follow_redirects=False)
        self.token = token or os.environ.get('VM_BACKUP_GITHUB_TOKEN', '')
        if not self.token:
            raise ValueError('VM_BACKUP_GITHUB_TOKEN required')
        self.base = f'https://api.github.com/repos/{repo}'
        self.headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28'}

    def observe(self, response):
        self.diagnostic(safe_http_event(response))

    @staticmethod
    def accepted(response):
        if 400 <= response.status_code < 500 and response.status_code != 429:
            raise GitHubPermanentError(response.status_code,response.request.url.host,
                                       response.headers.get('x-github-request-id'))
        response.raise_for_status()

    def request(self, method, url, *, missing=False, **kwargs):
        # Retry only bounded transient errors. Writes are reconciled by their
        # immutable IDs/names by the caller; no unsafe blind creation loops.
        for attempt in range(3):
            try:
                response = self.client.request(method, url, headers=self.headers, **kwargs)
                self.observe(response)
                if response.status_code == 404 and missing:
                    return None
                if response.status_code in (429, 500, 502, 503, 504):
                    if attempt < 2:
                        time.sleep(min(2**attempt, 4)); continue
                self.accepted(response)
                return response
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 2: raise ValueError('github_network_failure') from None
                time.sleep(2**attempt)
        raise ValueError('github_request_failed')

    def verify(self):
        if self.request('GET', self.base).json().get('private') is not True:
            raise ValueError('backup repository must be private')

    def checkpoints(self):
        # GitHub Contents directory listing is limited to 1000. Shard by year,
        # never silently accept a truncated list. No automatic deletion.
        result = []
        root = self.request('GET', self.base + '/contents/checkpoints/' + self.namespace, missing=True)
        if root is None: return []
        years = root.json()
        if not isinstance(years, list) or len(years) >= 1000: raise ValueError('checkpoint listing limit')
        for year in years:
            if year['type'] != 'dir' or not re.fullmatch(r'\d{4}', year['name']): raise ValueError('unexpected checkpoint directory')
            rows = self.request('GET', self.base + '/contents/' + year['path']).json()
            if len(rows) >= 1000: raise ValueError('checkpoint year full; rotate namespace explicitly')
            result.extend(rows)
        return sorted(result, key=lambda r: r['path'], reverse=True)

    def record(self, row):
        response = self.request('GET', self.base + '/contents/' + row['path']).json()
        return json.loads(base64.b64decode(response['content']))

    def download(self, ref, target):
        # API may redirect to a signed release URL. Never forward GitHub bearer
        # credentials to that other origin. Reject arbitrary redirect hosts.
        headers = {**self.headers, 'Accept': 'application/octet-stream'}
        url = self.base + '/releases/assets/' + str(int(ref['id']))
        for attempt in range(3):
            try:
                response = self.client.get(url, headers=headers, follow_redirects=False)
                self.observe(response)
                if response.status_code in (301, 302, 303, 307, 308):
                    location = httpx.URL(response.headers['location'])
                    if location.scheme != 'https' or location.host not in ('release-assets.githubusercontent.com', 'objects.githubusercontent.com'):
                        raise ValueError('release redirect denied')
                    response = self.client.get(str(location), headers={'Accept': 'application/octet-stream'}, follow_redirects=False)
                    self.observe(response)
                self.accepted(response)
                # Each encrypted object is bounded (manifest is bounded too).
                if len(response.content) > CHUNK + 1024*1024: raise ValueError('asset too large')
                target.write_bytes(response.content)
                if digest(target) != ref['sha256'] or target.stat().st_size != ref['bytes']:
                    raise ValueError('encrypted asset checksum mismatch')
                return
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == 2: raise ValueError('github_download_failed') from None
                time.sleep(2**attempt)

    def release(self, checkpoint):
        tag = f'vm-{self.namespace}-{checkpoint}'
        old = self.request('GET', self.base + '/releases/tags/' + tag, missing=True)
        if old is not None: return old.json()
        try:
            return self.request('POST', self.base + '/releases', json={'tag_name':tag, 'name':tag, 'draft':False, 'prerelease':True}).json()
        except GitHubPermanentError:
            raise
        except (ValueError, httpx.HTTPError):
            old = self.request('GET', self.base + '/releases/tags/' + tag, missing=True)
            if old is None: raise
            return old.json()

    def upload(self, release, source):
        sha = digest(source); name = sha + '.age'
        # Use GitHub's documented URI template, but authorize the destination
        # before attaching credentials. Never follow an upload redirect.
        url = release.get('upload_url','').partition('{')[0]
        parsed = httpx.URL(url)
        expected = f"/repos/{self.repo}/releases/{int(release['id'])}/assets"
        if (parsed.scheme != 'https' or parsed.host != 'uploads.github.com'
            or parsed.port not in (None,443) or parsed.path != expected
            or parsed.userinfo or parsed.query or parsed.fragment):
            raise ValueError('GitHub upload destination denied')
        # Reconcile uncertain creation by immutable ciphertext name, never clobber.
        for attempt in range(3):
            assets = self.assets(release['id'])
            match = next((a for a in assets if a['name'] == name), None)
            if match: break
            try:
                with source.open('rb') as data:
                    match = self.client.post(url, params={'name':name}, headers={**self.headers, 'Content-Type':'application/octet-stream'}, content=data.read(), follow_redirects=False)
                self.observe(match)
                self.accepted(match); match = match.json(); break
            except GitHubPermanentError:
                raise
            except (httpx.HTTPError, ValueError):
                if attempt == 2: raise ValueError('github_upload_failed') from None
                time.sleep(2**attempt)
        ref = {'id':match['id'], 'sha256':sha, 'bytes':source.stat().st_size}
        with tempfile.TemporaryDirectory() as scratch:
            self.download(ref, Path(scratch)/'verify.age')
        return ref

    def assets(self, release_id):
        rows=[]
        for page in range(1, 1001):
            result=self.request('GET', self.base+f'/releases/{release_id}/assets', params={'per_page':100,'page':page}).json()
            rows.extend(result)
            if len(result)<100:return rows
        raise ValueError('release asset listing limit')

    def commit(self, checkpoint, ref):
        year = time.strftime('%Y', time.gmtime())
        path = f'checkpoints/{self.namespace}/{year}/{checkpoint}.json'
        payload = {'format':2, 'created_at':time.time(), 'manifest':ref}
        url = self.base + '/contents/' + path
        existing = self.request('GET', url, missing=True)
        if existing is not None:
            if json.loads(base64.b64decode(existing.json()['content']))['manifest'] != ref:
                raise ValueError('checkpoint collision')
            return
        try:
            self.request('PUT', url, json={'message':'Publish encrypted recovery checkpoint', 'content':base64.b64encode(encode(payload)).decode()})
        except GitHubPermanentError:
            raise
        except (ValueError, httpx.HTTPError):
            existing = self.request('GET', url, missing=True)
            if existing is None or json.loads(base64.b64decode(existing.json()['content']))['manifest'] != ref: raise


class Checkpoints:
    def __init__(self, store, recipient, identity):
        self.store, self.recipient, self.identity = store, recipient, Path(identity)

    def manifest(self, row, scratch):
        record = self.store.record(row)
        if record.get('format') != 2: raise ValueError('unsupported checkpoint')
        cipher = scratch/'manifest.age'; clear = scratch/'manifest.json'
        self.store.download(record['manifest'], cipher)
        age(['-d','-i',self.identity,'-o',clear,cipher])
        if clear.stat().st_size > CHUNK: raise ValueError('manifest too large')
        manifest = json.loads(clear.read_bytes())
        if manifest.get('format') != 2: raise ValueError('unsupported manifest')
        return manifest

    def capture(self, data, state, stage):
        """Called while app writers are paused; copy online SQLite snapshots."""
        data, state = Path(data), Path(state)
        if any(stage.iterdir()):raise ValueError('capture stage must be empty')
        import shutil
        required=sum(p.stat().st_size for root in (data,state) for p in root.rglob('*') if p.is_file() and not p.is_symlink())
        if required>MAX_BYTES or shutil.disk_usage(stage).free<required+4*CHUNK:
            raise ValueError('insufficient snapshot scratch capacity')
        if data.resolve() == state.resolve() or state.resolve().is_relative_to(data.resolve()) or data.resolve().is_relative_to(state.resolve()):
            raise ValueError('state and data roots must be separate')
        total=0; count=0
        for label, root in (('data',data), ('state',state)):
            for source in sorted(root.rglob('*')):
                relative=source.relative_to(root)
                if label=='data' and relative.parts[0] not in ('videos','index','indexes','experiments','eval','answers','jobs.sqlite','jobs.sqlite-wal','jobs.sqlite-shm'):
                    raise ValueError('unrecognized data; refusing omission')
                if source.is_symlink(): raise ValueError('symlink in application state')
                if not source.is_file(): continue
                relative=source.relative_to(root)
                # These are explicitly ephemeral, never recovery prerequisites.
                if label=='state' and relative.parts[0] in ('backup-health.json',): continue
                if source.name.endswith(('-wal','-shm')):
                    database=source.with_name(source.name[:-4])
                    if database.is_file() and database.suffix in ('.sqlite','.db'):
                        continue # incorporated through SQLite online backup, never omitted
                    raise ValueError('unrecognized database sidecar')
                if source.name.startswith('.') or source.name.startswith('upload-') or '.tmp' in source.name or source.name=='speech.m4a':
                    raise ValueError('unfinished state requires retry before checkpoint')
                if label=='state' and source.name not in ('config-history.json','config-history.backup.json'):
                    raise ValueError('unrecognized configuration state; refusing omission')
                if source.name.startswith('.env') or source.suffix in ('.key','.pem','.agekey'):
                    raise ValueError('credential file in application state')
                target=stage/label/relative;target.parent.mkdir(parents=True,exist_ok=True)
                if source.suffix in ('.sqlite','.db'):
                    db_snapshot(source,target)
                else:
                    import shutil
                    shutil.copyfile(source,target)
                count+=1;total+=target.stat().st_size
                if count>MAX_FILES or total>MAX_BYTES: raise ValueError('backup capacity exceeded')
                if source.suffix in ('.json','.jsonl','.yaml','.yml'):
                    tail=b''
                    with target.open('rb') as stream:
                        while chunk:=stream.read(1024*1024):
                            if SECRET.search(tail+chunk):raise ValueError('credential signature in metadata')
                            tail=chunk[-512:]
        if not count: raise ValueError('empty checkpoint refused')
        self.coverage(stage)

    @staticmethod
    def coverage(root):
        from config.schema import parse_configuration
        config=root/'state/config-history.json'
        if config.exists():
            for entry in json.loads(config.read_text()): parse_configuration(entry)
        data=root/'data'; current=data/'index/CURRENT'
        coverage={'index_revision':None, 'video_count':0, 'index_segments':0}
        for folder in (data/'videos').glob('*'):
            if not folder.is_dir(): raise ValueError('invalid video directory')
            # Uploaded queued files are preserved too. A published library item
            # must include original, proxy, thumbnail, transcript and segments.
            if (folder/'meta.json').exists():
                for name in ('original','video.mp4','thumb.jpg','transcript.json','segments.json'):
                    if not (folder/name).is_file(): raise ValueError('incomplete library item')
                coverage['video_count']+=1
        if current.exists():
            revision=current.read_text().strip()
            if not re.fullmatch('[0-9a-f]{32}',revision): raise ValueError('invalid index revision')
            index=data/'index/revisions'/revision
            manifest=json.loads((index/'manifest.json').read_text())
            segments=json.loads((index/'segments.json').read_text())
            import numpy as np
            for view in manifest['views']:
                matrix=np.load(index/(view+'.npy'),allow_pickle=False,mmap_mode='r')
                if matrix.ndim!=2 or len(matrix)!=len(segments) or matrix.shape[1]!=manifest['dimension'] or not np.isfinite(matrix).all() or (np.linalg.norm(matrix,axis=1)==0).any():
                    raise ValueError('index coverage mismatch')
            for seg in segments:
                video=data/'videos'/seg['video_id']
                if not video.is_dir() or not (video/'segments.json').exists(): raise ValueError('index references missing media')
                if not any(s['id']==seg['id'] and s.get('text')==seg.get('text') for s in json.loads((video/'segments.json').read_text())):
                    raise ValueError('index references inconsistent segment metadata')
            coverage.update(index_revision=revision,index_segments=len(segments),embedding_space=manifest.get('embedding_space'))
        elif (data/'index/manifest.json').exists():
            raise ValueError('legacy unversioned index requires explicit migration')
        return coverage

    def backup(self, stage, progress=lambda **kw:None):
        self.store.verify()
        # Validate the provisioned decryptor matches the encryption recipient
        # before publishing a checkpoint that might otherwise be unrecoverable.
        with tempfile.TemporaryDirectory() as probe:
            probe=Path(probe);(probe/'clear').write_bytes(b'visual-mentor-key-check')
            age(['-r',self.recipient,'-o',probe/'cipher',probe/'clear'])
            age(['-d','-i',self.identity,'-o',probe/'roundtrip',probe/'cipher'])
            if (probe/'roundtrip').read_bytes()!=b'visual-mentor-key-check':raise ValueError('recovery key mismatch')
        checkpoint=time.strftime('%Y%m%dT%H%M%S',time.gmtime())+f'{time.time_ns()%1000000000:09d}-'+uuid.uuid4().hex
        with tempfile.TemporaryDirectory(prefix='vm-encrypt-') as temp:
            temp=Path(temp);previous={}
            rows=self.store.checkpoints()
            if rows: previous=self.manifest(rows[0],temp).get('objects',{})
            objects={};files={};locations={};pending=0
            for source in sorted(stage.rglob('*')):
                if not source.is_file(): continue
                names=[]
                with source.open('rb') as stream:
                    offset=0
                    while chunk:=stream.read(CHUNK):
                        sha=hashlib.sha256(chunk).hexdigest(); names.append(sha)
                        if sha not in objects:
                            objects[sha]=previous.get(sha)
                            if objects[sha] is None:
                                locations[sha]=(source,offset,len(chunk)); pending+=1
                        offset+=len(chunk)
                files[source.relative_to(stage).as_posix()]={'bytes':source.stat().st_size,'sha256':digest(source),'chunks':names}
            progress(pending_uploads=pending)
            release=self.store.release(checkpoint);release_number=0;release_assets=0
            for sha,ref in list(objects.items()):
                if ref is None:
                    clear=temp/'upload.clear';cipher=temp/'upload.age'
                    cipher.unlink(missing_ok=True)
                    source,offset,length=locations[sha]
                    with source.open('rb') as stream:
                        stream.seek(offset);clear.write_bytes(stream.read(length))
                    if digest(clear)!=sha:raise ValueError('staged object changed')
                    age(['-r',self.recipient,'-o',cipher,clear])
                    if release_assets>=ASSETS_PER_RELEASE:
                        release_number+=1;release_assets=0
                        release=self.store.release(checkpoint+f'-{release_number:04d}')
                    objects[sha]=self.store.upload(release,cipher);release_assets+=1
                    pending-=1;progress(pending_uploads=pending)
                else:
                    # A committed reference must still exist and match before
                    # claiming coverage. Missing dedup objects fail closed.
                    self.store.download(ref,temp/'dedup-check.age')
            manifest={'format':2,'checkpoint':checkpoint,'created_at':time.time(),'files':files,'objects':objects,
                      'coverage':self.coverage(stage),'exclusions':['live camera buffers','sessions','environment credentials','backup health cache']}
            clear=temp/'new-manifest.json';clear.write_bytes(encode(manifest))
            if clear.stat().st_size>CHUNK: raise ValueError('manifest capacity exceeded')
            cipher=temp/'new-manifest.age';age(['-r',self.recipient,'-o',cipher,clear])
            if release_assets>=ASSETS_PER_RELEASE:
                release_number+=1
                release=self.store.release(checkpoint+f'-{release_number:04d}')
            ref=self.store.upload(release,cipher)
            self.store.commit(checkpoint,ref)
            return {'checkpoint':checkpoint,'created_at':manifest['created_at'],'files':len(files),
                    'encrypted_bytes_referenced':sum(r['bytes'] for r in objects.values())+ref['bytes'],
                    'coverage':manifest['coverage']}

    def restore(self, destination, checkpoint=None):
        destination=Path(destination)
        if destination.exists(): raise ValueError('recovery destination must be new')
        self.store.verify();rows=self.store.checkpoints()
        if checkpoint:
            rows=[r for r in rows if Path(r['path']).stem==checkpoint]
        if not rows: raise ValueError('no committed recovery point')
        # No silent fallback: a damaged newest checkpoint requires explicit choice.
        with tempfile.TemporaryDirectory(dir=destination.parent,prefix='.vm-recovery-') as temp:
            temp=Path(temp);manifest=self.manifest(rows[0],temp);stage=temp/'recovered';stage.mkdir(mode=0o700)
            files=manifest['files'];total=0
            if len(files)>MAX_FILES: raise ValueError('recovery capacity exceeded')
            for name,info in files.items():
                safe_path(name);total+=info['bytes']
                if info['bytes']<0 or total>MAX_BYTES: raise ValueError('recovery capacity exceeded')
                target=stage/name;target.parent.mkdir(parents=True,exist_ok=True)
                with target.open('xb') as output:
                    for sha in info['chunks']:
                        if not re.fullmatch('[0-9a-f]{64}',sha):raise ValueError('invalid object address')
                        cipher=temp/'chunk.age';clear=temp/'chunk.clear'
                        clear.unlink(missing_ok=True)
                        self.store.download(manifest['objects'][sha],cipher)
                        age(['-d','-i',self.identity,'-o',clear,cipher])
                        if clear.stat().st_size>CHUNK or digest(clear)!=sha:raise ValueError('plaintext checksum mismatch')
                        output.write(clear.read_bytes())
                    output.flush();os.fsync(output.fileno())
                target.chmod(0o600)
                if target.stat().st_size!=info['bytes'] or digest(target)!=info['sha256']:raise ValueError('restored file checksum mismatch')
            for db in stage.rglob('*.sqlite'):
                with sqlite3.connect(db) as conn:
                    if conn.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('restored SQLite invalid')
            if self.coverage(stage)!=manifest['coverage']:raise ValueError('restored coverage mismatch')
            os.rename(stage,destination)
            return {'verified':True,'checkpoint':manifest['checkpoint'],'files':len(files),'coverage':manifest['coverage'],'created_at':manifest['created_at'],'tested_at':time.time()}
