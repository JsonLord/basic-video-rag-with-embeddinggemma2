"""Retention planning; deleting Git files does not erase historical Git blobs.
Archive/compact history only in an approved maintenance procedure after restore.
"""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from vrag.backup import retention_keep
p=argparse.ArgumentParser();p.add_argument('snapshots',type=Path);p.add_argument('--apply',action='store_true')
if __name__=='__main__':
    args=p.parse_args();rows=[(f,json.loads(f.read_text())) for f in args.snapshots.glob('*.json')];keep=retention_keep([e for _,e in rows])
    for f,e in rows:
        if e.get('coverage_verified') and e.get('ciphertext_sha256') not in keep:
            print('Expire',f.name)
            if args.apply:f.with_suffix('.age').unlink();f.unlink()
