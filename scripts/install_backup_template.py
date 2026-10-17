"""Prepare a reviewable local private-repository checkout. Never creates/pushes a repo."""
import argparse,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('destination',type=Path)
if __name__=='__main__':
    dest=p.parse_args().destination
    if dest.exists():raise SystemExit('Destination must be new')
    root=Path(__file__).resolve().parent.parent
    shutil.copytree(root/'deploy/backup-repository',dest)
    for folder in ('vrag/backup','config'):
        shutil.copytree(root/folder,dest/folder,ignore=shutil.ignore_patterns('__pycache__','examples'))
    (dest/'vrag/__init__.py').touch()
    (dest/'scripts').mkdir()
    for name in ('backup_state.py','restore_state.py','fetch_backup_source.py','check_backup.py','prune_backups.py'):
        shutil.copyfile(root/'scripts'/name,dest/'scripts'/name)
    shutil.copyfile(root/'docs/backup-restore.md',dest/'README.md')
    print('Local template ready; private repo creation, credential provisioning and activation require approval.')
