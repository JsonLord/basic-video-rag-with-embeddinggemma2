# GitHub-native backup migration qualification — 17 October 2026

**Implementation prepared; activation is blocked.** No production Space deployment,
secret provisioning, scheduling activation, existing-backup overwrite or DGX service
change was performed. The source changes are on `feature/video-rag-mentor-v2`; backup
coordinator source is on private backup `main`, outside `.github/workflows`.

## Architectural change

The old design required an immutable external store snapshot plus separately stored
media. The new runtime operates on HF CPU Basic ephemeral files, creates consistent
SQLite/config/index/media snapshots, encrypts content-addressed chunks with age,
and uses private GitHub release assets plus atomic repository checkpoint records
as its sole persistent recovery source. No S3, R2, rclone or HF persistent disk is
required. The original Library/Search/Ask/Experiments/Architecture/detail/live/model
routes remain; a backup admin panel is added at `/backups`.

The backup repository now coordinates the Space instead of fetching external data.
The Space holds a scoped GitHub writer and age recovery key; Actions holds only a
scoped HF access token and limited backup-trigger token. This avoids giving the
coordinator configuration/media/inference administrator privileges. Encryption is
performed inside the Space before GitHub transmission, including the recovery
manifest. Only operational ciphertext references/timing/size metadata is public to
the private repository and GitHub itself.

The activation runbook and estimates are in [backup-restore.md](backup-restore.md).
Format-1 snapshots are retained unchanged and never automatically reinterpreted.
Existing data must first be independently restored and imported into a format-2
working root. No automated pruning or history rewriting is included.

## Evidence and its limits

Machine-readable summary: [github-backup-results.json](evidence/github-backup-results.json).

| Check | Result | Evidence boundary |
| --- | --- | --- |
| Backend regression suite | 109 passed | Real CPU media, SQLite and age; provider calls mocked |
| New backup tests | 13 passed (included above) | Successful GitHub storage transport mocked |
| Destructive complete-library recovery | Passed locally | Generated video, original/proxy/frame/thumbnail, transcript, segments, SQLite row, saved answer history, config history, versioned vector index; delete source + capture stage, recover only encrypted mock remote assets + key, compare all file hashes |
| Fresh application startup | Passed locally | Separate Python interpreter loads recovered ConfigStore and index and serves protected library endpoint; no stale in-memory state |
| Incremental backup | Passed locally | Identical original/proxy chunks share objects; unchanged second checkpoint uploads manifest only |
| Safety/failure behavior | Passed locally | Partial upload publishes no record, corrupt/missing objects block restore, wrong key publishes nothing, invalid index/unknown state fail, existing roots are not overwritten; mocked documented HTTP endpoints and cross-origin credential stripping pass |
| Protected administration | Passed locally | Missing/wrong role denied, coordinator token scoped to enqueue/status, browser-origin coordinator rejected |
| Timer and retries | Passed simulated clock | Exercises 12-hour timeout branch, three snapshot attempts, status and zero pending uploads; does not simulate a platform sleep/wake |
| Frontend build/lint | Passed | One existing unused-variable warning in Architecture; zero lint errors |
| Browser parity/camera/routing | 17 passed | Screenshot comparisons and mock API/simulated devices, not physical camera/provider integrations |
| Backup administration browser | 2 passed | Mock status and trigger endpoints; displays actual reported status and distinguishes acceptance from completion |
| GitHub private metadata | Passed live | Repository private; release creation succeeds with existing identity |
| GitHub encrypted asset upload | **Blocked live** | `uploads.github.com` responds 401 Bad credentials; no recovery record committed |
| Private HF reachability | **Blocked live** | Both HF metadata and `leon4gr45-openweb.hf.space` rejected by current network proxy policy; HF test credential absent |
| Actions wake/completion | **Not run / not established** | No deployed trigger on staging, no validated private access route, no activated workflow |

The unsuccessful live attempt created one empty, uniquely named test release:
`vm-test-recovery-20261017-deae94ff-20261017T173832-f8cd66db742745159168b741ea1a751e`.
It is not a checkpoint. No original user data or private credentials were uploaded.
The attempted ciphertext upload and a synthetic header-only diagnostic both failed
with 401. No production namespace was written and old assets were not deleted.

The environment draft now preserves existing domains and adds API/upload/signed
release hosts plus `huggingface.co` and the exact supplied Space origin. It also
records scoped `VM_BACKUP_GITHUB_TOKEN` and optional `HF_SPACE_TOKEN` requirements.
Saving this draft did not apply or publish it, provision credentials, or change HF
settings. Review/save and publish the environment configuration to apply access.
Do not paste tokens into chat. GitHub API access alone does not establish upload
host credentials; both routes must be tested using the same authorized identity.

## Scheduling decision

The inactive Actions template has 00:17/12:17 UTC schedule and manual dispatch,
concurrency and outer timeout. It requires explicit approval plus validated private
routing; it checks HF metadata privacy, uses HF bearer authentication and separate
app trigger header, then polls for a newly completed checkpoint. YAML existence
and a 202-style enqueue response are never reported as schedule success.

The local resident timer and important-state-change triggers are implemented and
covered with mock-clock/local tests. They run only while the Space is awake. They
are useful as a local fallback but cannot meet a sleeping-Space wake guarantee.
No secure alternative wake path is validated in this environment. Reliable
12-hour scheduling remains blocked pending a real private staging sleep/wake test.
The implementation does not create a public endpoint, restart the Space, change
hardware, buy persistent storage or expose additional ports to evade that blocker.

## Capacity estimate

Example 64 MiB original + 20 MiB proxy + 1 MiB transcript/images + 3 MiB index:
approximately 88 MiB initial encrypted storage. One hundred similar videos:
roughly 8.5 GiB media plus index revisions/manifests. A 10k x 768 float32 view is
29.30 MiB; five views are 146.48 MiB/revision. Twenty single-view revisions add
about 586 MiB. Age adds small framing overhead and does not compress media.
A configuration-only change uploads changed chunks and a small encrypted manifest;
unchanged chunks are reused but read back for coverage. Older removed/reintroduced
chunks may upload again because the dedup catalog is the preceding manifest.

Enforce 20 GiB / 100k-file plaintext ceiling and source-size + 64 MiB free scratch
preflight. HF's 50 GB includes app, active files, processing and backup/restore
staging. Keep operational usage below the theoretical limit. Check GitHub account
quotas and release-asset acceptable use before treating the estimate as approval.
GitHub listings fail closed at capacity instead of silently dropping files; rotate
reviewed namespaces before a year shard reaches 1000 records. No deletion is automatic.

## Activation checklist — requires separate production approval

1. Review the two commits and storage/key policy; keep all existing backup data.
2. Apply the saved environment network settings. Provision a fine-grained private
   repository token in secure settings with Contents read/write, authenticated on
   **both** API and uploads hosts. Provision read-only HF access for the supplied
   private Space. Do not provide a broad app administrator token to Actions.
3. Rerun `AGE_BIN=/path/to/age python tests/live_github_recovery.py`. It creates a
   fresh `test-recovery-*` namespace, backs up real generated video/index/config,
   checks unchanged dedup, destroys source + snapshot stage, starts a fresh Python
   application instance and recovers using GitHub + protected ephemeral test key.
   Require `docs/evidence/github-recovery-live.json` with all hashes matching.
   The protected test key is deleted at drill end; test assets are disposable and
   must never be mistaken for production recovery points.
4. Obtain staging deployment approval. Configure the age identity as an HF Secret,
   keep an independent protected operator recovery copy, configure roots exactly as
   documented, and import reviewed existing data with writers stopped. First-start
   empty authorization is temporary and is forbidden for a failed recovery.
5. Deploy only to the approved private staging Space. Verify anonymous denial,
   correct HF identity access, user/admin separation and scoped coordinator access.
6. Run the coordinator manually against staging with approved secrets. Let staging
   sleep, then repeat from an actual GitHub Actions runner. Require verified private
   access, wake, accepted trigger **and a new committed checkpoint**. Record run URL,
   timestamps and restore-point ID. Do not claim these tests from local mock results.
7. Destroy staging state and start its clean container. Verify complete library,
   media/Range, index queries, YAML history and health from GitHub + age key only.
   Run an isolated admin recovery test and capture its result in `/backups`.
8. Exercise ingestion-complete and config-apply/rollback triggers, failed uploads,
   exhausted retries, revoked credentials, capacity failure and stale health.
   Check the existing inference/camera/routing/UI flows with unchanged providers.
9. After explicit approval, move the reviewed inactive coordinator into
   `.github/workflows`, provision the protected environment and set
   `COORDINATOR_VALIDATED=true` and `BACKUPS_APPROVED=true`. First observe manual
   completion, then actual scheduled runs. No such activation was performed here.
10. Obtain a distinct production deployment/scheduling approval before applying any
    changes to `Leon4gr45/openweb`. Retain a tested previous source and recovery
    checkpoint; rollback into an isolated root, never overwrite active data.
