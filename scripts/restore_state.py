"""Verified isolated restore only. No production overwrite or implicit promotion."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from vrag.backup import restore
p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--identity',type=Path,required=True);p.add_argument('--destination',type=Path,required=True);p.add_argument('--assets-root',type=Path,required=True);p.add_argument('--dry-run',action='store_true')
if __name__=='__main__':
    try:print(json.dumps(restore(**vars(p.parse_args()))))
    except Exception:sys.exit('Restore failed: verify checksums, recovery key, available assets and an unused staging destination. Production unchanged.')
