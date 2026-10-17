# GitHub-native encrypted backup and recovery

The active filesystem is HF CPU Basic ephemeral disk. The private
`JsonLord/visual-mentor-backups` repository is the sole persistent recovery store.
No object store, rclone remote, HF paid disk, or independent media copy is required.
This implementation is prepared for review; production scheduling and HF deployment
remain disabled. See `github-backup-migration.md` for actual test evidence and gates.

## Recovery protocol (format 2)

The Space pauses ingestion/upload and configuration writes using one asyncio lock,
then copies its complete recognized data tree and config history into a private
snapshot directory. SQLite uses the online backup API, integrity check and VACUUM.
The copied index includes CURRENT and all versioned revisions, manifests, vectors
and segments. Coverage validates published videos and referenced index media.
All original videos, proxies, thumbnails, segment frames, transcript files, index
revisions, experiments/evaluation files, saved answer history, queue DB and configuration history travel
with the checkpoint. Unknown data/config files, symlinks, unfinished temporary
files, missing required media, incompatible index layout and capacity violations
fail the checkpoint. No success is reported for an omitted required file.

Uploads happen after releasing the write lock. Files are split into 16 MiB chunks,
addressed by plaintext SHA-256 **inside the encrypted manifest**. Identical chunks
in the same checkpoint and its immediate predecessor reuse existing assets. A
chunk absent from that predecessor may upload again even if an older checkpoint
contains it; this is incremental deduplication, not global garbage collection.
New chunks are age-encrypted before upload. GitHub release asset names are hashes
of ciphertext. Decryptor/recipient compatibility is checked before publication.
Existing objects and new uploads are read back and hash-verified. A manifest
contains file paths, hashes, chunk references, index revision/model space and
coverage. It is itself encrypted and uploaded as a private release asset.

Only after every referenced object verifies does a unique GitHub Contents commit
publish `checkpoints/<namespace>/<year>/<timestamp>-<uuid>.json`. That small record
contains format, creation time, encrypted manifest asset ID/size/hash; it contains
no media, transcript, config, plaintext hashes or key. GitHub also observes repo,
release names, object sizes, timing and access. These operational metadata cannot
be hidden from the storage provider. No plaintext user payload is transmitted.
The repository record is the atomic commit point. Partial releases are uncommitted
orphans, not restore points. Existing records/assets are never overwritten or
pruned. Transient calls retry at most three times; immutable names reconcile
uncertain responses. Snapshot attempts also retry three times, with 90-second
lock acquisition bounds. Concurrent triggers coalesce in the one-worker queue.
Only one application process/replica is supported. Do not run external writers or
CLI ingestion alongside the serving process; use offline CLI after stopping it.

## Space settings (after deployment approval)

HF Variables:

```
VM_BACKUP_ENABLED=true
VM_BACKUP_REPOSITORY=JsonLord/visual-mentor-backups
VM_BACKUP_NAMESPACE=production
VM_RECOVERY_ROOT=/app/work
VRAG_DATA=/app/work/data
VM_STATE_DIR=/app/work/state
VM_BACKUP_RECIPIENT=age1<public-recipient>
```

HF **Secrets**, entered securely in settings:

- `VM_BACKUP_GITHUB_TOKEN`: fine-grained identity limited to the private backup
  repository, Contents read/write and release asset access. Test both
  `api.github.com` and `uploads.github.com`. It requires neither repository
  administration nor Actions permission. Private downloads may redirect to signed
  GitHub release URLs; the client never forwards its bearer token to that host.
- `VM_BACKUP_IDENTITY`: age private identity text matching the public recipient.
  It is materialized with mode 0600 into a temporary file outside the working tree
  before startup; the raw variable is removed from inherited child environment.
  Alternatively provide a securely provisioned `VM_BACKUP_IDENTITY_FILE` outside
  `/app/work`. Protect an independent operator copy of this key: GitHub data alone
  cannot recover without it. This key is intentionally never backed up to GitHub.
- `VM_BACKUP_TRIGGER_TOKEN`: independent random >=32-character token. It authorizes
  backup enqueue/status only, through `X-VM-Backup-Token`. It grants no config,
  inference, media or isolated-recovery-test privileges. `VM_ADMIN_TOKEN` retains
  admin access and is never given to the coordinator.

Keep provider credentials and app role tokens as before. They are excluded from
checkpoints and must be re-provisioned for a recreated Space. Configuration retains
only secret/endpoint environment-variable references; the environment values are
not recovered. If using a custom index path, it must equal the covered data/index.

The supervisor runs recovery **before** importing ConfigStore, index or workers.
On an empty working root it selects the newest committed record, fetches and
decrypts only GitHub-hosted objects, checks every byte/hash, SQLite, config and
index coverage, and renames a sibling staging directory into place atomically.
Failure aborts startup. It never merges into or overwrites nonempty state and never
silently falls back from a corrupt latest checkpoint. To choose an earlier point,
use `python scripts/restore_state.py --destination /new/isolated-root --checkpoint
<checkpoint>` with the same protected environment, then review before promotion.

On a brand-new namespace with no checkpoint, startup refuses by default. A reviewed
first initialization may temporarily set `VM_BACKUP_ALLOW_EMPTY=true`; remove it
immediately after the first verified checkpoint. A namespace with prior data must
never use this escape hatch to conceal a recovery failure.

## Triggers, administration and coordinator

Backup requests occur on startup, accepted media upload, completed ingestion,
applied/rolled-back configuration, authenticated manual trigger and the resident
12-hour timer. The timer continues only while the Space process is running. It
cannot wake a sleeping Space and is **not** an independently durable scheduler.
The queue reports failure codes, attempt time, pending encrypted uploads, latest
successful checkpoint, inventory bytes including historical/orphan assets, restore
points, and last isolated recovery result. `/backups` is the administration panel;
server routes require administrator or the deliberately limited coordinator token.
The panel does not claim enqueue acceptance is backup success.

`deploy/backup-repository/inactive-workflows/backup-12h.yml` runs at 00:17 and 12:17
UTC (02:17/14:17 Berlin summer time; 01:17/13:17 Berlin winter time). It is outside
`.github/workflows` and cannot run. It also requires both `BACKUPS_APPROVED` and
`COORDINATOR_VALIDATED` to equal `true`, plus the protected `private-backup`
environment. No workflow is activated by source upload.

The coordinator verifies Space privacy using the HF API, sends the scoped HF
bearer token through the private Space access boundary, and sends the independent
app trigger token in a separate header. It refuses redirects and unexpected URL
origins. It probes up to ten nominal minutes for a sleeping instance, then triggers
and waits for a **new completed checkpoint**, not just HTTP acceptance. Network
calls have timeouts and attempts are bounded; Actions has a 35-minute outer timeout.
A failed private route/wake/authentication test is a deployment blocker. Do not
replace it with a public Space, arbitrary proxy, app admin token or unauthenticated
export. The resident timer is a tested local fallback while awake only; it is not
claimed as a validated sleeping-Space alternative.

## Limits, retention and recovery point objective

Current application upload limit is 64 MiB/video, 30 minutes, 10k indexed segments.
Backup plaintext capacity is 20 GiB / 100k files. Capture needs free scratch space
at least the source size plus 64 MiB; source+snapshot and restore staging compete
with HF's 50 GB ephemeral allowance. Actual usable capacity is lower after image,
processing scratch and previous index revisions. Budget below 20 GiB, monitor
usage and fail explicitly at capacity. Objects are 16 MiB plus age overhead,
well below GitHub's 2 GiB per-asset limit. Uploads shard at 800 assets per release
to stay below the 1000-assets/release limit. GitHub release policy, API quotas,
Acceptable Use and private-account storage entitlements still need operator review;
release assets must not be assumed an unlimited general-purpose storage service.
Checkpoint metadata is sharded by namespace/year and refuses a 1000-entry listing;
rotate to a reviewed namespace before reaching that limit (12h plus event triggers
can reach it sooner than a year). No destructive retention is automated.

Unchanged chunks cost no new payload assets, but dedup readback downloads referenced
ciphertext to ensure it still exists. Checkpoints add an encrypted manifest and a
small repository commit. A 64 MiB original plus 20 MiB proxy, 1 MiB images/transcript
and a 3 MiB index starts around 88 MiB; compressed media does not shrink under age.
At 100 similarly sized videos, media is roughly 8.5 GiB plus accumulated indexes.
A 10k x 768 float32 text matrix is 30.72 MB (29.30 MiB) per revision. Five views are
153.6 MB (146.48 MiB) per revision. Twenty retained single-view revisions add about
586 MiB, excluding JSON. Metadata-only edits upload only changed chunks and a new
manifest; changed full matrix files can upload most chunks again.

Ephemeral disk losses can destroy uncheckpointed uploads. Event triggers reduce
but do not eliminate that window; backups are asynchronous and a sleeping Space
cannot expose lost disk to Actions. GitHub downtime, token expiry, key loss, disk
capacity and quotas can prevent recovery. Require a successful staging drill and
real sleep/wake run before asserting a 12-hour recovery objective.

## Migration and activation

Retain format-1 archives unchanged. They used external asset coverage and are not
self-contained format-2 checkpoints. Import their verified full restored data into
an isolated format-2 root while writers are stopped, then create and independently
recover a GitHub-native checkpoint before retiring external copies. Never delete
old assets as part of this refactor. Old helper functions remain only for format-1
compatibility tests; the exporter and active external-source templates are retired.
Production activation checklist is in `github-backup-migration.md`.
