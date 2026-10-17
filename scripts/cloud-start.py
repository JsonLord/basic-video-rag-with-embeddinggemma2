"""Supervise both services; exit when either dies, forward termination to both."""
import os
import signal
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
# Recovery must precede imports of ConfigStore, index and queue/database startup.
if os.environ.get('VM_BACKUP_ENABLED') == 'true':
    import sys
    sys.path.insert(0, str(root))
    recovery_root = Path(os.environ.get('VM_RECOVERY_ROOT', '/app/work'))
    os.environ.setdefault('VRAG_DATA', str(recovery_root / 'data'))
    os.environ.setdefault('VM_STATE_DIR', str(recovery_root / 'state'))
    from vrag.backup.service import bootstrap
    bootstrap()

children = []
def stop(*_):
    for p in children:
        if p.poll() is None:
            p.terminate()
    for p in children:
        try:
            p.wait(timeout=10)
        except subprocess.TimeoutExpired:
            p.kill()

signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
try:
    children.append(subprocess.Popen([os.sys.executable, '-m', 'uvicorn', 'vrag.api:app', '--host', '127.0.0.1', '--port', '8000', '--no-access-log'], cwd=root))
    node_env = {**os.environ, 'PORT': '7860', 'HOSTNAME': '0.0.0.0', 'NODE_ENV': 'production'}
    children.append(subprocess.Popen(['node', 'server.js'], cwd=root / 'web/.next/standalone', env=node_env))
    while all(p.poll() is None for p in children):
        time.sleep(0.25)
finally:
    stop()
raise SystemExit(next((p.returncode for p in children if p.returncode), 0))
