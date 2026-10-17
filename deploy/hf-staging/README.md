# Private staging qualification package (not deployed)

Proposed target: **Leon4gr45/openweb-v2-staging**, private Docker Space, CPU Basic.
Production `Leon4gr45/openweb` is excluded. A live anonymous HF metadata probe on
17 October 2026 reported production `private=false`, Docker/CPU Basic/RUNNING and
no deployed backup-status route (404). This package never changes that Space.

Upload only the application allowlist from docs/deployment-hf.md, using the reviewed
feature-branch commit and an HF identity authorized to write this staging repository.
A credential restricted to an existing staging repository is preferred: create the
private staging repository separately first, then grant write only to that target.
Creation itself requires repository-creation rights for the Leon4gr45 namespace.
No deployment command has been executed and no HF credential is currently present.

HF staging Variables:

```
VM_BACKUP_ENABLED=true
VM_BACKUP_REPOSITORY=JsonLord/visual-mentor-backups
VM_BACKUP_NAMESPACE=staging-qualification
VM_RECOVERY_ROOT=/app/work
VRAG_DATA=/app/work/data
VM_STATE_DIR=/app/work/state
VM_ALLOWED_ORIGINS=https://leon4gr45-openweb-v2-staging.hf.space
VM_BACKUP_RECIPIENT=<public age recipient>
```

Secrets: independent VM_USER_TOKEN / VM_ADMIN_TOKEN (>=24 characters),
VM_BACKUP_TRIGGER_TOKEN (>=32 characters), VM_BACKUP_GITHUB_TOKEN (backup repository
Contents read/write, Metadata read, API + upload-host access), VM_BACKUP_IDENTITY
(age private recovery identity, direct HF Secret; do not proxy this value).
Keep the independent operator recovery key copy. Provider settings remain disabled
unless an explicitly authorized synthetic-provider test needs them. Source and
media/index fixtures must come from a separate disposable test namespace.

For a reviewed first initialization of this *new staging namespace only*, temporarily
set VM_BACKUP_ALLOW_EMPTY=true; remove it after the first verified checkpoint.
Never use this override to hide a failed restore of a previously initialized root.
Use synthetic video ingestion or the offline fixture exporter with writers stopped.

After the deployment is ready, execute the read-only private boundary probe:

```
python scripts/qualify_private_space.py \
  --space Leon4gr45/openweb-v2-staging \
  --url https://leon4gr45-openweb-v2-staging.hf.space
```

It requires HF_SPACE_TOKEN (read access to this private staging repo, plus direct
private app route access) and VM_BACKUP_TRIGGER_TOKEN from secure settings.
Add `--trigger` only when ready for an actual new checkpoint; it uses the bounded
coordinator. It records anonymous denial, authorized status, rejection of a wrong
trigger token, initial runtime stage, and checkpoint outcome. An already running
Space cannot establish a sleep/wake claim. Do not call restart/resume/hardware APIs;
wait for a naturally sleeping staging instance and test the authenticated route.

The backup repository's `inactive-workflows/qualify-private-staging.yml` is a
**manual-only** test workflow, with separate `private-backup-staging` environment
and STAGING_* variables/secrets. No production timer is activated. Once staging
credentials and routing work locally, review and install only this manual workflow,
dispatch from an actual runner, then record its run URL/checkpoint. The 12-hour
production workflow stays in inactive-workflows with approval guards unset.

Final drill: delete only this staging test working root, start its clean container,
and verify restored Library/Search/media/config/index from GitHub + protected key.
Record initial/final file hashes, SQLite integrity/logical rows, Range response and
actual media decoding. Production and pre-existing backups/releases remain untouched.
