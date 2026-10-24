# Private Hugging Face production checklist — Gate 06

**Prepared only. Production is NO-GO.** This task did not create/deploy a Space,
change its visibility, set production secrets, publish an environment draft,
restart DGX/shared services, submit remote research or activate backup schedules.
The existing public Space must remain unchanged. Approve a separate private staging
target before any deployment/settings operation.

## Operator-supplied configuration inventory

The operator supplies and verifies the values below through the intended HF Space's
Variables and Secrets UI. Preserve existing provider/auth/backup values and record
names/revisions only. HF settings do not automatically populate this separate cloud
development environment; qualification commands need their own secure bindings.

| Setting | HF type | Operator value / requirement |
| --- | --- | --- |
| OPENAI_COMPATIBLE_URL | Variable | Existing authorized HTTPS root or /v1; no guessed DGX URL |
| OPENAI_COMPATIBLE_MODEL | Variable | Exact served model ID verified by listing and response identity |
| OPENAI_COMPATIBLE_API_KEY | Secret | Dedicated gateway key; confirm authentication enforcement separately |
| A2A_URL | Variable or Secret | `https://leon4gr45-openoperator.hf.space/a2a/t-{token}` template; token never literal in YAML |
| A2A_TOKEN | Secret | Agent-specific key, available to the actual server process |
| VM_ALLOWED_HOSTS | Variable | Exact approved conversation/agent/detection/embedding/STT hosts; preserve old entries |
| VM_USER_TOKEN | Secret | Existing user-role secret, at least 24 characters |
| VM_ADMIN_TOKEN | Secret | Distinct admin secret, at least 24 characters |
| VM_ALLOWED_ORIGINS | Variable | Exact private staging application origin; review separately for production |
| VRAG_DATA | Variable | `/app/work/data` |
| VM_STATE_DIR | Variable | `/app/work/state` |
| VM_RECOVERY_ROOT | Variable | `/app/work`; backup roots must match this layout |
| VRAG_INDEX_DIR | Optional Variable | Default data/index; external uncovered index paths are rejected |
| LAYA_BASE_URL / LAYA_API_KEY | Existing Variable / Secret | Preserve verified router contract; Laya remains optional |
| NVIDIA_DETECTION_BASE_URL / NVIDIA_DETECTION_API_KEY | Existing Variable / Secret if used | Only an approved detection-http gateway with the verified custom contract; a native NIM URL is not interchangeable |
| STT / embedding / vision model, URL and credential references | Existing Variables / Secrets | Exact names selected by the reviewed YAML; operator supplies actual model IDs and compatible index dimensions |
| VRAG_SAVE_ANSWERS | Existing Variable | Preserve/review answer-history retention consent |
| VM_BACKUP_REPOSITORY | Existing Variable | Private GitHub backup repo; never substitute a public destination |
| VM_BACKUP_NAMESPACE | Existing Variable | Preserve production namespace; disposable qualification uses a separate unique namespace |
| VM_BACKUP_GITHUB_TOKEN | Existing Secret | Dedicated backup token; Contents write + release-asset operations on that private repo, not integration-managed GH_TOKEN |
| VM_BACKUP_RECIPIENT | Existing Variable | Reviewed age public recipient corresponding to protected recovery identity |
| VM_BACKUP_IDENTITY | Existing Secret | Protected age identity; bootstrap provisions a 0600 temporary file outside captured state |
| VM_BACKUP_IDENTITY_FILE | Alternative protected path | Use instead of inline identity where supported; never inside backed-up data/state |
| VM_BACKUP_TRIGGER_TOKEN | Existing Secret | Separate coordinator/trigger credential |
| HF_SPACE_TOKEN | Existing coordinator Secret | Least privilege for approved private target; never reuse as app/provider/backup token |
| VM_SPACE_ID / VM_SPACE_URL | Existing coordinator Variables | Approved private owner/name and canonical URL, only after approval |
| VM_BACKUP_ENABLED | Existing protected operational decision | Preserve current value; first production activation requires recovery qualification and approval |
| VM_BACKUP_ALLOW_EMPTY | Explicit first-start decision | Only after approval for a genuinely new empty namespace; never bypass an expected recovery |

No S3/R2/rclone or HF persistent volume is required. Ephemeral CPU Basic storage
is the working filesystem; encrypted GitHub checkpoints/release assets remain the
sole persistent recovery store. Conversation, research and tool state share
jobs.sqlite and existing encrypted backup coverage. Keep all recurring workflows
inactive until separately approved.

## Configuration acceptance before activation

- [ ] Inventory current Space source revision, visibility, auth, YAML history and
  secret names, without exporting values. Approve private staging owner/name.
- [ ] Resolve the Docker CDN build failure through approved proxy/policy handling.
  Keep pinned bases, CA verification and proxy route. Do not use a mirror or change
  global network settings. Build/start/resource evidence must come from the actual image.
- [ ] Supply Qwen's three environment entries and append its exact hostname to
  VM_ALLOWED_HOSTS. Run the standalone diagnostic with a new evidence filename.
  Record the existing server version/model/parser; do not restart/pull models.
- [ ] Supply A2A_TOKEN securely in the environment actually running the probe and
  add the selected agent hostname to application authorization. Verify read-only
  discovery and URL-path proxy substitution before requesting a research test.
- [ ] Review YAML precedence: an explicit role, including disabled, overrides HF
  defaults. Presence never enables a route. Keep disabled routes disabled.
- [ ] Select schema v2 explicitly. Replace model placeholders with real identities;
  A2A's model field is its exact verified Agent Card name. Conversation/research
  roles require a single provider identity. Preview/validate/CAS-apply via the
  existing admin studio only when approved.
- [ ] Authorize approved_sensitive per provider only after privacy review. Synthetic
  public_only qualification is not authorization to send private media or chat.
- [ ] Verify unavailable credentials/destinations produce explicit errors and leave
  cameras/Library usable. Native NVIDIA and optional Phonon remain unqualified.

## Private access and secret handling

- [ ] On the approved private staging Space, verify anonymous root/API/media access
  is denied at the HF boundary. Do not make the app public as a diagnostic workaround.
- [ ] Verify an authorized HF browser session plus separate application user/admin
  roles. Verify API/backup automation's actual HF bearer route and the distinct
  protected trigger header. Do not assume two authorization layers work from YAML.
- [ ] Confirm wrong app/admin/trigger tokens are denied, ownership remains enforced,
  configuration writes require admin, and cross-origin requests fail appropriately.
- [ ] Confirm provider destination authorization on each dispatch/fallback and that
  Agent Cards cannot redirect credentials or add destinations.
- [ ] Supply no secret as NEXT_PUBLIC_*, build ARG, YAML value or client component
  variable. Gate 06's actual Next build with five synthetic server-secret canaries
  passed a browser-asset scan (26 files / 1,361,945 bytes); source/tests verify
  server-only references. This does not attest to an as-yet-unbuilt Docker image
  or every future custom secret name. Repeat for final deployment inputs/image.
- [ ] Keep recovery keys out of Git, logs, build context and backup payloads.
  Preserve encrypted backup health and failed/unknown outcomes visibly.

## Staging operational evidence still required

- [ ] Separate explicit approval for one bounded harmless live A2A task after Agent
  Card discovery passes. Follow the proposal in live-provider-qualification.md;
  verify submit/get/artifact/cancel behavior and durable restart reconciliation.
- [ ] Verify actual NVIDIA model, numeric geometry and measured frame latency before
  enabling native capability claims. Keep Laya off the required spatial path until
  meaningful latency measurements justify it.
- [ ] Build the CPU image with the documented mounted CA, then run actual container
  startup/auth checks. The existing qualify-release.py and measure-runtime.py cover
  baseline container/auth/HTTP/FFmpeg work, not the entire new mixed workload.
- [ ] Measure the actual image with simultaneous cameras, ingestion while chat
  streams, and A2A coordination. Record sample counts, cold/warm state, startup,
  idle/load/peak RAM, CPU, p50/p95, payloads and error rates. Distinguish synthetic
  protocols from live inference; imports and browser test duration are not benchmarks.
- [ ] Qualify physical built-in + USB devices and browser permission/device-loss
  behavior; simulated cameras do not establish physical hardware acceptance.
- [ ] Complete live encrypted GitHub-only recovery in a disposable namespace,
  including media/index/config/conversation/research state. Do not overwrite or
  delete existing checkpoints/releases. Verify private Actions reachability/wake
  before requesting recurring workflow activation.
- [ ] Keep Phonon disabled unless an isolated CPU/English-ASR/peak-RAM and fallback
  proof succeeds. No first-run model downloads in the default runtime.
- [ ] Approve production deployment, production credential changes and backup
  scheduling separately after the evidence is reviewed. Preserve rollback inputs.

## Commands prepared, not executed against production

See live-provider-qualification.md for Linux/Windows Qwen invocation and read-only
A2A discovery. From this managed Linux environment, after registry access is fixed:

```bash
BUILDX_CONFIG=/tmp/gate06-buildx docker --host=unix:///var/run/docker.sock build \
  --secret id=build_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -t visual-mentor:gate06-review .
python scripts/qualify-release.py --image visual-mentor:gate06-review
VM_RUNTIME_IMAGE=visual-mentor:gate06-review python scripts/measure-runtime.py
```

These last two commands were not run on a Gate 06 image because that image failed
to build. Follow the cloud runtime Docker skill's endpoint-selector and CA guidance;
never change the daemon, use host networking or publish ports to evade restrictions.
A separate approved mixed-workload run is still needed after those baseline checks.
