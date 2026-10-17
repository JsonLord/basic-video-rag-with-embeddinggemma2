"""Restore from GitHub into a new isolated destination; never overwrites state."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from vrag.backup.service import engine
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--destination',type=Path,required=True);parser.add_argument('--checkpoint')
    args=parser.parse_args();print(json.dumps(engine().restore(args.destination,args.checkpoint)))
