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


## Subsequent live qualification (17 October 2026)

This section supersedes the earlier network-policy observations above. Fixes are
based on application `30dbccac29e8056ccffff98f45247515f32edaad` and backup tooling
`96e6391b303e82ca821937c57da5e03776f3eedc`. No production changes or workflow activation
were made. Existing checkpoints/releases were neither deleted nor overwritten.

### Phase 1: host-specific 401 diagnosis

Using the **same GH_TOKEN source**, GitHub user/private repository reads return
200 and new disposable release creation returns 201 on `api.github.com`. The
uploader now consumes the returned `upload_url`, removes its URI-template suffix,
and validates HTTPS, exact uploads host, expected repository/release path, no
userinfo/query/fragment and no redirects before attaching Authorization.

The resulting POST to `uploads.github.com` returns **401**, request ID
`FD3D:10E5C1:CD4E9:E9D17:6AD3D414`. A separate supported `token` authorization-scheme
probe returns 401 (`4CD7:31E81D:C5069:E70BE:6AD3D43C`); the native gh CLI using the
same credential source also returns 401 (`ADAA:355B8B:2A3FE2:3F6FD8:6AD3D43D`). The
upload-host root's 302 is not an authentication test and is not counted as success.

HTTPX confirms Authorization is attached before the outbound proxy. API responses
include GitHub request IDs; the server response header is `envoy`. There is no
available trusted proxy trace that shows the forwarded Authorization value. These
observations localize the rejection to authentication at the upload destination;
they do **not** establish whether the proxy stripped, rewrote, or failed to inject
a credential. No proxy-held credentials were extracted, and no direct connection,
alternate API route or TLS bypass was attempted. Both HTTPX and gh fail, so this
is not demonstrated to be an HTTPX-only request-format issue. The declared scoped
VM_BACKUP_GITHUB_TOKEN binding still has no saved credential, and its variable is
absent in the running environment. A valid credential on both destinations remains
the external prerequisite; changing upload_url alone did not fix the 401.

401 and other permanent 4xx requests now raise sanitized GitHubPermanentError,
without blind upload or outer checkpoint retries. The health report distinguishes
`github_authentication_failed` from a generic retry exhaustion. Transient upload
failures still reconcile the immutable asset name before retrying; a test verifies
that an uncertain 503 with an actually created asset does not produce a duplicate.
Sanitized diagnostics record method/host/status/GitHub request ID and allowlisted
response headers, never Authorization values, request bodies, response payloads or
signed Location URLs. Tests cover destination authorization and credential stripping
on signed downloads.

Evidence:

- [Host probes](evidence/github-auth-probe.json)
- [HTTPX / gh comparison](evidence/github-upload-client-comparison.json)
- [Latest live drill](evidence/github-recovery-live.json)

### Phase 2: attempted real recovery

Namespace `test-recovery-20261017-937e26ae` contains a newly created, uncommitted
release only. Its first encrypted upload failed once with 401. A read-only check
confirmed **zero release assets** and no checkpoint namespace (Contents API 404).
No successful live recovery, incremental checkpoint or file-hash comparison is
claimed. The report is explicitly `status=blocked`, `recovery_verified=false`.
All prior recovery successes remain real age/SQLite/FFmpeg with **mocked GitHub**.

The live drill now persists sanitized diagnostics even on authentication failure.
After credentials work it is ready to record both committed checkpoint IDs, asset
counts, full restored file hashes before application startup, unchanged incremental
dedup, SQLite integrity/logical rows, fresh-process Library/Search/config/index,
authorized media Range and anonymous media denial, and actual FFmpeg media decode.
Search uses a deterministic synthetic query vector, not a live embedding provider;
the recovered index and application Search route perform real retrieval. The test
source and capture stage are deleted before restore, and recovery uses only GitHub
assets plus the isolated age key. Ephemeral test key destruction is intentional;
these disposable points are not production recovery assets.

### Phase 3: private HF staging preparation

Network reachability now works for the supplied production origin and HF metadata.
An anonymous HF metadata response reports **Leon4gr45/openweb private=false**, Docker,
CPU Basic, RUNNING, revision `5a12f98129417859ebddae6d7e74ca4a8d3dd5e4`. Its backup-status
route returns 404. This is not a private-boundary qualification and its privacy or
deployment was not changed. Anonymous metadata access to the proposed separate
staging target returns 401; existence/access cannot be concluded without credentials.

A concrete [private staging package](../deploy/hf-staging/README.md), restricted
probe `scripts/qualify_private_space.py`, and manual-only inactive
`qualify-private-staging.yml` are prepared. The probe rejects production targets,
requires private metadata, verifies anonymous denial plus correct HF/scoped-trigger
access and wrong-trigger rejection, and can run the bounded checkpoint coordinator.
It records an actual Actions run URL when executed on a runner and only claims a
sleep/wake test when initial runtime was sleeping and the authenticated route plus
new checkpoint succeeded. No restart/resume/hardware API is called.

The present task authorizes private staging qualification; it does not authorize
production changes. No HF credential is available, so staging deployment, authorized
HF access, actual runner dispatch and sleep/wake testing could not proceed. This is
a missing capability, not a request to reconfirm the task. The manual test workflow
and 12-hour production workflow both remain outside `.github/workflows`.

Evidence: [HF observation](evidence/hf-space-observation.json) and
[staging probe result](evidence/private-staging-live.json).

### Exact remaining credential and activation steps

1. In secure cloud environment settings, supply **VM_BACKUP_GITHUB_TOKEN**: a
   fine-grained GitHub token authorized only for JsonLord/visual-mentor-backups,
   **Contents read/write and Metadata read**. Configure proxy substitution for both
   `api.github.com` and `uploads.github.com`; signed release downloads deliberately
   receive no bearer token. Apply the saved environment configuration and confirm
   both hosts with the same binding. Never paste values or expose the proxy-held
   token. The existing integration's API access does not prove upload authentication.
2. Rerun `AGE_BIN=/path/to/age python tests/live_github_recovery.py`. Require a
   passed evidence file with real asset readback, two committed checkpoints,
   incremental manifest-only upload, all pre-startup file hashes equal, and fresh
   application/media checks. Until then the sole-store live recovery gate fails.
3. Provision an HF identity with write access to the **separate private staging**
   repository. Repository creation requires rights in the Leon4gr45 namespace; if
   avoiding broad creation rights, create the private Docker staging repository
   first and issue a token limited to its contents/settings. Use the staging package
   and existing deployment allowlist, not a production upload. Set staging backup
   namespace, protected key/trigger and independent role tokens in HF settings.
4. Give the coordinator a **separate read-only HF token** authorized to access the
   private staging repository and its authenticated app route, plus its own staging
   trigger token. Add the exact staging origin to allowed network/credential
   destinations. No paid inference or production-repository write scope is needed.
   Run the private probe locally, then install only the reviewed manual workflow
   with its `private-backup-staging` environment, STAGING_SPACE_ID/URL variables and
   STAGING_HF_TOKEN / STAGING_BACKUP_TRIGGER_TOKEN secrets. Keep workflow permissions
   at Contents read; GitHub writes occur inside the Space with its scoped writer.
5. Dispatch the manual workflow, record its run URL and new committed point, then
   test a naturally sleeping staging instance through the same authenticated route.
   Destroy only staging working state and verify clean startup recovery. Do not
   equate an awake run, a local mock, or enqueue acceptance with wake/schedule success.
6. Leave the production timer inactive and approval guards unset. Production Space
   deployment or production scheduling still requires explicit approval.

Current follow-up regression: **116 backend tests passed** (20 backup tests),
including permanent-error retry suppression, transient reconciliation, sanitized
headers and private staging boundary mocks. These new tests do not convert the
blocked live gates into passes. No application UI or inference feature was redesigned.


## Dedicated credential recheck — 18 October 2026

The dedicated VM_BACKUP_GITHUB_TOKEN is now provisioned and ready. All requests
in this recheck used it, with no integration GH_TOKEN fallback. Private repository
read succeeded (200) and a new disposable release was created (201), but its first
age-encrypted asset upload returned **404** from uploads.github.com. Request ID:
`FE93:319F8B:36F88A:4FB435:6AD3F6B8`. The permanent rejection was not retried.

Namespace `test-recovery-20261017-745d0278` has zero assets and zero committed
checkpoints, verified after the failure. Recovery/dedup were not reached. No
existing remote release/checkpoint was changed. Scope versus host-specific
credential propagation remains undetermined until the same permitted token is
compared on an independent trusted machine; none is attached here. No security
bypass or credential extraction was attempted. HF credentials remain absent.

The first private staging deployment remains **NO-GO**. See
[credential qualification](credential-qualification.md) for sanitized evidence,
exact comparison steps and attribution boundaries. Earlier statements that the
dedicated binding was absent are historical and superseded by this recheck.
