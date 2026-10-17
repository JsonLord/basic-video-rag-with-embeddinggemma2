"""Atomic configuration history. Defaults are read-only unless storage is configured."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
from config.schema import Configuration

class ConfigStore:
    def __init__(self, path=None):
        self.path = Path(path or os.environ['VM_STATE_DIR']) if path or os.environ.get('VM_STATE_DIR') else None
        self.lock = asyncio.Lock()
        self.history = [Configuration()]
        self.version = 1
        if self.path:
            self.path.mkdir(parents=True, exist_ok=True)
            state = self.path / 'config-history.json'
            if state.exists():
                self.history = [Configuration.model_validate(c) for c in json.loads(state.read_text())]
                self.version = len(self.history)
    def snapshot(self):
        # Deep copy prevents nested mutation of in-flight snapshots.
        return self.version, self.history[-1].model_copy(deep=True)
    async def apply(self, config, expected):
        if not self.path:
            raise ValueError('VM_STATE_DIR is required for configuration updates; defaults are read-only')
        async with self.lock:
            if expected != self.version:
                raise ValueError('configuration changed; reload before applying')
            if len(self.history) >= 100:
                raise ValueError('configuration history limit reached; archive state before more updates')
            history = self.history + [config]
            fd, tmp = tempfile.mkstemp(dir=self.path, prefix='.config-')
            try:
                with os.fdopen(fd, 'w') as f:
                    json.dump([c.model_dump() for c in history], f)
                    f.flush()
                    os.fsync(f.fileno())
                # Persist the previous complete history before switching the active file.
                if (self.path / 'config-history.json').exists():
                    import shutil
                    backup = self.path / '.config-history.backup.tmp'
                    shutil.copyfile(self.path / 'config-history.json', backup)
                    with backup.open('rb') as previous:
                        os.fsync(previous.fileno())
                    os.replace(backup, self.path / 'config-history.backup.json')
                os.replace(tmp, self.path / 'config-history.json')
                directory_fd = os.open(self.path, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if os.path.exists(tmp):
                    os.unlink(tmp)
            self.history, self.version = history, len(history)
        return self.version

store = ConfigStore()
