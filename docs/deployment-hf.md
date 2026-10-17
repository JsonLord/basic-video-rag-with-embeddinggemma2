# Visual Mentor v2: private Hugging Face staging and rollback

**Prepared only. No Space has been created, uploaded or modified.** Current
production target `Leon4gr45/openweb` is protected by explicit approval and a staging
UI review. No DGX/Needle/inference infrastructure change is required.

## Local package and evidence

Docker runs Node/Next.js and one FastAPI worker, supervised by `scripts/cloud-start.py`.
Only port **7860** is exposed. FastAPI binds loopback 8000. One authoritative
`web/next.config.ts` preserves `/api` and `/media`, with Range seeking and bounded
65MB proxy buffering for the application's 64MiB upload cap. Node/Python bases are
pinned. No torch, transformers, Whisper weights, CUDA runtime or GPU device is
required. FFmpeg/age are CPU media/encryption tools, not inference models.

Build in this managed environment (session CA is mounted only during install):

```
BUILDX_CONFIG=/tmp/v2-buildx docker --host=unix:///var/run/docker.sock build \
  --secret id=build_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t video-rag-mentor:v2-review .
python scripts/qualify-release.py --image video-rag-mentor:v2-review
VM_RUNTIME_IMAGE=video-rag-mentor:v2-review python scripts/measure-runtime.py
```

These checks publish no host ports, run with network=none and a 2-vCPU/16GiB limit,
and remove their own containers/volumes. Qualification checks application bearer
roles, origin rejection, configuration CAS/rollback and volume recreation. A Docker
volume in a test is not evidence that HF supplies durable storage.

## Configuration before staging

Use HF Settings / Secrets (do not put values in YAML or browser bundles):

- `VM_USER_TOKEN`, `VM_ADMIN_TOKEN`: separate random tokens, >=24 characters.
  The user token opens private library/capture operations; admin token opens config
  and backup status only. This is a shared-role app, not per-person accounts/SSO.
- `VM_ALLOWED_ORIGINS=https://<staging-app-host>`: exact external origin.
- `VM_ALLOWED_HOSTS`: exact approved inference hostnames only.
- `VRAG_DATA=/app/data`, `VM_STATE_DIR=/app/data/state`; default index under
  `/app/data/index` so durable snapshot coverage includes it. Do not configure an
  uncovered index path outside the approved durable source layout.
- `LAYA_BASE_URL` is the router root; OpenAI-compatible VLM/embedding/Whisper
  base URLs generally include `/v1`. Credential environment references are the
  exact `api_key_secret` fields in the reviewed profile. Do not assume all endpoints
  share a protocol or that NVIDIA's public API implements this `/detect` gateway.
- `VM_BACKUP_STATUS_FILE`: optional sanitized trusted monitor report refreshed from
  approved external storage. No timer or unauthenticated backup export is exposed.
- Decide whether answer-history persistence (`VRAG_SAVE_ANSWERS`) is permitted.
  It is excluded from backup by default and may contain private research text.

All profile examples are disabled until model IDs, endpoints, capabilities,
privacy trust and credentials are explicitly verified. Active placeholder IDs are
rejected. Load/import YAML, review form/diff, validate, then apply using the current
revision. Credentials remain server-only references. Transcripts/keyframes uploaded
through Import may be sent to the selected authorized providers.

## Mandatory approval and external gates

1. Approve a **private staging** Space (proposed `Leon4gr45/openweb-v2-staging`),
   storage budget and durable backing-store integration. Obtain a fine-grained HF
   identity limited to intended repos. The current environment has no configured HF
   identity; openweb source, visibility, settings and screenshots were not inspected.
2. Before touching production, snapshot the existing Space Git revision, settings
   inventory (secret names only), private access policy and all data. Verify restore.
3. Establish external durable media/state storage and its immutable snapshot publisher
   before treating local state as durable. HF CPU Basic has 50GB ephemeral disk; no
   persistent mount is assumed. Complete the separate private GitHub backup workflow
   run, media verification and off-Space restore described in backup-restore.md.
4. Review `docs/v2-evidence/main/` against current Playwright screenshots. Confirm
   original workflows remain recognizable at desktop/laptop/tablet/mobile sizes.
5. With explicit staging approval, create a private Docker Space and upload the
   reviewed source, using the official SDK and environment-provisioned HF_TOKEN:

```python
import os
from huggingface_hub import HfApi
api = HfApi(token=os.environ['HF_TOKEN'])
repo = 'Leon4gr45/openweb-v2-staging'  # approved staging name
api.create_repo(repo_id=repo, repo_type='space', space_sdk='docker', private=True)
api.upload_folder(
    repo_id=repo, repo_type='space', folder_path='.',
    allow_patterns=['README.md', 'Dockerfile', 'requirements-runtime.txt',
                    'vrag/**', 'config/**', 'scripts/cloud-start.py', 'web/**'],
    ignore_patterns=['**/.env*', '**/*.pem', '**/*.key', '**/*.agekey', '**/*.age',
                     '**/__pycache__/**', '**/node_modules/**', '**/.next/**',
                     'web/tests/**', 'web/test-results/**', 'web/playwright-report/**'],
    commit_message='Stage reviewed Video RAG Visual Mentor v2',
)
```

6. Configure secrets/variables in staging, select CPU Basic (2 vCPU/16GB), inspect
   logs and health. Verify actual Space privacy by anonymous page/API/media requests;
   verify logged-in access with app user/admin roles and no access cross-over.
   Exercise `/`, `/search`, `/ask`, `/experiments`, `/architecture`, detail/clip Range
   seeking, `/live` and `/models`. Public sample assets are synthetic but still sit
   behind the private HF page/access boundary.
7. From a physical laptop browser over HTTPS, test laptop + USB simultaneous
   selection, permission denial/contention, disconnect, hidden-tab cleanup and
   stale results. Verify each real provider and costs using approved media only.
   Run real upload→Whisper→segments→embeddings→Search/Ask and verify citations/playback.
8. Recreate staging and restore from external state. Confirm actual recent GitHub
   backup and separate object-store assets survive Space recreation. Local tests
   alone do not pass this gate.
9. Present actual staging screenshots, provider test table, storage/backup/restore
   history and performance; obtain explicit approval before changing openweb.

## Controlled production switch / rollback

Save the existing production Space commit and tested external snapshot IDs before
upload. Obtain UI and deployment approval. Deploy the reviewed v2 source using the
same procedure targeted at openweb; do not merge the deployment PR wholesale.
Keep previous image/source and compatible snapshot available. On failure, pause
writes, restore the previous Space revision and point at an isolated verified
compatible state snapshot. Do not overwrite current data by automated restore or
run the legacy `serve/` scripts. Recheck private access, API/media and clips after
rollback. Production promotion and rollback execution are operator actions.
