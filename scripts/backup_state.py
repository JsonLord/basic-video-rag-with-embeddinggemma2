"""Run only against an immutable durable-store snapshot, outside the HF process."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from vrag.backup import snapshot
p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--state-root',type=Path,required=True);p.add_argument('--assets-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--recipient',required=True);p.add_argument('--source-snapshot-id',required=True);p.add_argument('--source-revision',default='unknown')
if __name__=='__main__':
    try:print(json.dumps(snapshot(**vars(p.parse_args()))))
    except Exception:sys.exit('Backup failed: verify durable source, asset coverage, size budget and encryption configuration. No success recorded.')
