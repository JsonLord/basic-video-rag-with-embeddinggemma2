"""Checkpoint the GitHub-configured state. Offline only: stop all app writers first.
The running application uses its protected trigger and shared snapshot lock.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from vrag.backup.service import engine,roots
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--offline-writers-stopped',action='store_true',required=True)
    parser.parse_args()
    backup=engine();_,data,state=roots()
    with tempfile.TemporaryDirectory(prefix='vm-offline-capture-') as temp:
        stage=Path(temp);backup.capture(data,state,stage)
        print(json.dumps(backup.backup(stage)))
