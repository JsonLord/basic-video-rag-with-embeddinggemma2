"""Export inactive GitHub coordinator tooling; never deploy or activate it."""
import argparse
import shutil
from pathlib import Path
if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('destination',type=Path)
    destination=parser.parse_args().destination
    if destination.exists():raise SystemExit('destination must be new')
    root=Path(__file__).resolve().parent.parent
    shutil.copytree(root/'deploy/backup-repository',destination)
    (destination/'scripts').mkdir(exist_ok=True)
    for name in ('coordinate_backup.py','qualify_private_space.py'):
        shutil.copyfile(root/'scripts'/name,destination/'scripts'/name)
    shutil.copyfile(root/'docs/backup-restore.md',destination/'README.md')
    print('Inactive coordinator exported; activation and production deployment remain separate.')
