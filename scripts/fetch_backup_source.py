"""Materialize an immutable snapshot and separate asset copies from a private rclone remote.
The exporter must publish current.json only after all snapshot files are durable.
"""
import argparse,hashlib,json,re,subprocess,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--remote',required=True);p.add_argument('--output',type=Path,required=True)
if __name__=='__main__':
    a=p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+:[A-Za-z0-9_./-]+',a.remote):raise SystemExit('Invalid durable remote reference')
    def rclone(*args):return subprocess.run(['rclone',*args],check=True,capture_output=True,timeout=1800).stdout
    current=json.loads(rclone('cat',a.remote+'/current.json'))
    sid=current['snapshot_id']
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',sid):raise SystemExit('Invalid durable snapshot ID')
    if not 0<=time.time()-current['created_at']<=14*3600:raise SystemExit('Durable source snapshot stale')
    if a.output.exists():raise SystemExit('Output must be new')
    rclone('copy',a.remote+'/snapshots/'+sid,str(a.output),'--transfers','2','--checkers','2')
    marker=json.loads((a.output/'source-snapshot.json').read_text())
    if marker['snapshot_id']!=sid or marker.get('created_at')!=current['created_at']:raise SystemExit('Snapshot pointer mismatch')
    if not marker.get('files'):raise SystemExit('Source inventory missing')
    for name,checksum in marker['files'].items():
        path=a.output/name
        if not path.resolve().is_relative_to(a.output.resolve()) or path.is_symlink() or not path.is_file():raise SystemExit('Unsafe/missing source inventory entry')
        if hashlib.file_digest(path.open('rb'),'sha256').hexdigest()!=checksum:raise SystemExit('Source checksum mismatch')
    rclone('copy',a.remote+'/assets',str(a.output/'assets'),'--transfers','2','--checkers','2')
    # Only safe identifier on stdout; provider/credential details never logged.
    print(sid)
