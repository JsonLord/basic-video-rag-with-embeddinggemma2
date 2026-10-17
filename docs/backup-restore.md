# Private backup and restore runbook

Status: **implemented locally, not activated or live-qualified**. No backup repository
has been created; no credentials provisioned; no GitHub Actions run is claimed.
Proposed separate destination: **JsonLord/visual-mentor-backups (private)**.
Source application branch stays free of private state. Templates live in
`deploy/backup-repository/.github/workflows/`, not the source repo's workflow directory.

## Source boundary and coverage

The authoritative source must be an approved private durable store. HF CPU Basic's
50GB disk is ephemeral. There is deliberately no unauthenticated Space export URL.
An operator must arrange immutable point-in-time snapshots of the durable state.
The current app implements local state and versioned indexes, not a live S3 database:
**a durable snapshot publisher is still an operational integration gate**. Merely
copying a running Space filesystem does not establish cross-file consistency.
SQLite files are individually copied with the online-backup API and integrity check;
that does not create a distributed transaction across SQLite, media and routing.

Required durable layout (rclone private remote selected by BACKUP_REMOTE):

```
current.json                         {snapshot_id, created_at}
snapshots/<id>/source-snapshot.json   {snapshot_id, created_at, files: {relative_path: sha256}}
snapshots/<id>/state/config-history.json
snapshots/<id>/state/config-history.backup.json
snapshots/<id>/data/jobs.sqlite
snapshots/<id>/data/videos/<id>/{meta,segments,transcript}.json
snapshots/<id>/data/index/{CURRENT,revisions/...}
snapshots/<id>/data/experiments/*.json
assets/videos/<id>/{original,video.mp4,thumb.jpg,segments/*.jpg}
```

Publish `current.json` last after the immutable snapshot and assets are complete.
The fetch runner rejects source snapshots older than 14h, checks every supplied
source inventory checksum, and fails closed when storage is inaccessible. The
snapshot exporter includes only known metadata, routing history, jobs database,
index manifests/vectors and experiment results. Unrecognized paths, `.env`, logs,
answer history, ephemeral sessions and live camera captures are excluded. Config
history is revalidated through the strict schema (only secret references allowed).
Known credential signatures cause export failure. No claim that arbitrary user
transcripts can be perfectly scanned for all possible secrets: restrict access,
review imported data, and encrypt both durable storage and snapshots.

Every media file has size/SHA-256/location in the encrypted coverage manifest.
The exporter re-reads the independent asset copy and verifies its hash; restore
requires those copies and checks them again. GitHub metadata alone cannot restore
videos. Assets are not placed in normal Git or Actions artifacts. Private object
storage and its own replication/retention must be approved and tested separately.
No LFS budget is assumed.

## Approval-gated installation

Section 9 of spec.md requires explicit confirmation for repository creation,
credentials and activation. The following is a concrete proposed installation,
**not a record of commands executed**:

1. Review the template and choose private durable storage, access policy, expected
   media size/cost and snapshot publisher. Confirm separate private repo creation.
2. Generate an age recovery identity **outside GitHub and the Space**:
   `age-keygen -o /secure/offline/mentor-recovery.agekey`.
   Store at least two protected offline/secret-manager copies; only recipient/public
   key goes into the backup runner. Never put the decryption key in Actions secrets.
3. Prepare local checkout:
   `python scripts/install_backup_template.py /tmp/visual-mentor-backups`.
   Review generated files. After explicit approval:
   `gh repo create JsonLord/visual-mentor-backups --private --source /tmp/visual-mentor-backups`
   (initialize Git, commit and attach the remote in the local checkout first).
   Use a scoped GitHub App/token only if provisioning requires it; do not request
   broad repo scope. Verify private visibility with `gh repo view --json visibility`.
4. Keep repository Actions disabled before uploading workflows, and keep repository
   variable `BACKUPS_APPROVED` absent/false. Both jobs enforce that explicit activation
   flag, so bootstrap cannot start backups or notifications. For an approved account,
   disable repository Actions via `gh api --method PUT repos/JsonLord/visual-mentor-backups/actions/permissions -F enabled=false` before pushing.
   Create protected Actions environment `private-backup`. Add environment variables
   `BACKUP_REMOTE` (e.g. `private:mentor-production`) and `AGE_RECIPIENT`.
   Add scoped read-only object-store rclone configuration as
   `RCLONE_CONFIG_BASE64` secret. Use least privilege and no source-repo data tokens.
   The workflow uses its own GITHUB_TOKEN with contents:write and issues:write
   (issues permission is for operational alerts). No public releases/Pages.
5. Push reviewed bootstrap with activation still disabled. Only after separate
   credential/data/scheduler approval, enable Actions, set repository variable
   `BACKUPS_APPROVED=true`, and run
   `gh workflow run backup-12h.yml --repo JsonLord/visual-mentor-backups`.
   Inspect encrypted snapshot, ciphertext verification and actual successful run.
   Schedule is **17 0,12 * * * UTC** (02:17/14:17 Berlin during daylight saving,
   01:17/13:17 in winter). Actions can run late/skip; it is a target cadence.
6. Download a committed encrypted snapshot and envelope onto an isolated recovery
   host. Verify ciphertext SHA, decrypt and dry-run using the offline identity:

```
python scripts/restore_state.py --archive snapshots/<timestamp>.age \
  --identity /secure/offline/mentor-recovery.agekey --assets-root /private/media-copy \
  --destination /isolated/restore-001 --dry-run
python scripts/restore_state.py --archive snapshots/<timestamp>.age \
  --identity /secure/offline/mentor-recovery.agekey --assets-root /private/media-copy \
  --destination /isolated/restore-001
```

7. Verify SQLite integrity/content, index manifests/model IDs, config history and
   playback. Record independent restore evidence SHA-256 as repository variable
   `RESTORE_EVIDENCE_SHA256` only after verification; publish the signed-off report
   to approved durable monitoring storage. Set `VM_BACKUP_STATUS_FILE` to a locally
   refreshed **trusted external report**, never inference YAML. The app only reads
   sanitized administrator status. The operator must arrange that refresh; a stale
   file remains stale and cannot imply live status.
8. Promote only with explicit operator confirmation: stop the staging app, point
   VRAG_DATA and VM_STATE_DIR at restored `data/` and `state/`, verify index CURRENT,
   and restart staging. Restore never overwrites production or starts deployment.
9. Simulate missing source, denied credentials, corrupt asset and missed schedule;
   confirm failed runs/issues. Monitor runs hourly at minute 47, alerts once for an
   open stale/unverified incident. Configure GitHub issue notifications to operators;
   independent external uptime monitoring is recommended because GitHub itself can
   delay both schedules. No notifications have been sent by this implementation.

## Retention and costs

Each encrypted snapshot is capped at 40MiB, individual metadata files at 32MiB.
Large vector indexes require an explicitly reviewed object-store policy; export
fails rather than silently omitting them. Plan 28 twelve-hourly snapshots, 8 weekly,
6 monthly (some overlap); `scripts/prune_backups.py snapshots` prints a plan,
`--apply` removes expired working-tree files while preserving newest verified copy.
Before any independent restore is verified, retention keeps every verified copy.
Mark the exact restored snapshot envelope `restore_verified: true` in a reviewed
private-repository commit after recording restore evidence; retention then preserves
that last restorable copy as well as the newest verified snapshot.
The template does **not** automatically rewrite Git history. Deleting Git files
alone does not reclaim old blobs. Budget repository growth and schedule approved
history archival/compaction only after independent restore verification. Media
copies, GET egress, full hash verification, Actions minutes and durable publisher
costs depend on the corpus; measure before activation. Rclone currently downloads
all asset copies for integrity verification, which can be expensive for large corpora.

The local test uses disposable age identities and a separate fake object-store
folder, real encryption/decryption and SQLite backup. It demonstrates implementation
behavior, not private repository visibility, scheduled execution, durable storage
rebuild survival or off-Space recovery. Those remain mandatory live gates.
