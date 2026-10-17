"""Independent monitor. Nonzero when last success is absent, late or unverified."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from vrag.backup import stale_status
p=argparse.ArgumentParser();p.add_argument('report',type=Path)
if __name__=='__main__':
    args=p.parse_args();report=json.loads(args.report.read_text()) if args.report.exists() else {}
    status=stale_status(report);print(json.dumps(status));sys.exit(1 if status['stale'] or not status['enabled'] else 0)
