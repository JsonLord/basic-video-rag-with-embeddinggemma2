# Visual Mentor v3 implementation architecture

This branch extends v2. Gate 01 adds browser capture and framing; it does not
implement the complete v3 conversation/research/ASR system in spec.md.

## Browser media ownership and consent

Each existing Camera owns one getUserMedia video stream. CameraRecorder clones
its video track for original recording, or captures the actual FramingViewport
canvas at 15 fps for the explicitly labeled canvas output. It requests a separate
microphone stream only after audio consent. Each camera has an independent encoder,
state machine and local clip. Original source tracks are never stopped by normal
recorder finalization. Camera stop/device change/hidden tab interrupts the recorder;
navigation releases all owned tracks, pending microphone grants and blob URLs.
Interactive media controls stay disabled until client hydration.

MediaRecorder negotiates WebM VP9/VP8 or MP4. Chunks accumulate in bounded browser
RAM: one clip per camera, 128 MiB and 30 minutes of wall time per clip, including
pauses. A quota overflow discards that recording; encoder interruptions retain
produced data with a playback warning. Nothing is written to a server automatically.
RAM is ephemeral; closing/navigating away loses clips. Download is the local export.
Two clips can use up to 256 MiB plus codec/blob overhead; this is a quota, not a
measured memory bound or a disk-backed recording implementation.

Authenticated import requires a separate per-clip consent, reuses /api/ingest,
retains the authoritative 64 MiB limit and follows the existing jobs endpoint.
Upload can be cancelled; jobs may still require a transcript or approved provider
configuration. No bare device identity is uploaded. The import processes only the
chosen output, so original recordings never acquire CSS-only overlays by implication.
No research upload is added.

## Spatial association and crop

AssociationTracker accepts only normalized spatial detections from an already
correlated observation. It associates same-camera/source/label boxes with greedy
one-to-one IoU matching, with compatible upstream object IDs where present. IDs
never recycle in a camera component. Empty updates mark missing tracks; stale frame
timestamps cannot replace newer state. It retains at most 128 tracks and considers
at most 64 detections per frame. This is deterministic association, not optical
flow, motion prediction, calibrated multi-camera tracking or NVIDIA tracker proof.

FramingViewport polls current tracks without blocking preview/network work. Manual
keyboard selection or one-time highest-confidence auto selection keeps the chosen
ID; loss never switches to an unrelated object. Margin, minimum crop, exponential
smoothing and lost timeout are bounded browser-local controls. Crops use native
source pixels and preserve native aspect ratio with edge constraints. Resolution
changes reset crop geometry. Mirror transforms presentation rather than source
boxes. Canvas annotations are actually drawn and therefore included in canvas
recordings. Inactive previews clear the canvas. The original exact-frame still
overlay and its stale-result checks remain intact.

Limits: no PiP/composite recording mode yet; manual selection uses a labeled select
rather than clickable live boxes. No rotation sensor metadata is consumed; crop
uses decoded video dimensions. Physical camera/browser combinations remain untested.

## Importing streaming WebM

A non-seekable MediaRecorder WebM may omit its duration header. Ingestion now accepts
that case by converting to a seekable MP4 with a hard 1801-second output ceiling and
an existing 600-second FFmpeg process timeout. It probes the result and rejects any
proxy over the 1800-second limit before publishing it. Known invalid durations still
fail early. The original upload is retained for retry; no truncated over-limit proxy
or index is published. HTTP body limits, job ownership, indexes and backup paths
are unchanged.

## Configuration and subsequent gates

Gate 01 adds no YAML fields. Existing schema version 1 and stored history/rollback
remain authoritative. config/examples/v3-disabled.yaml is executable version-1 YAML
with every route disabled; Qwen there is only the existing reasoning adapter, not
a claim of streaming/tools. Browser recording consent does not enable server-side
recording via the legacy privacy.record_video setting, which remains false.

Gate 02 now implements separate strict ProviderV2/ConfigurationV2 models and an
explicit migration preview. Old v1 models remain unchanged. Version-dispatched
readers load mixed histories, preserve original v1 object fields when appending,
export protected historical revisions and roll back to their original schema.
Schema, history, session routing and provider capability versions are distinct.
Both encrypted backup validators accept the versioned configuration objects;
formats, destinations and scheduling remain unchanged. Real encrypted restore tests
cover mixed history and the initial tool ledger.

HF OPENAI_COMPATIBLE_* and A2A_* references overlay the same registry only when a
YAML role has not already selected a provider. Defaults are disabled/public_only;
model selection resolves at dispatch and secret presence is not health. The studio
shows sanitized defaults, migration preview and the explicit feature roles. See
[hf-runtime-variables.md](hf-runtime-variables.md) for precedence and activation.

Routing preserves captured timestamps and revisions and rejects results after
history/session changes. Conservative same-label overlap suppression retains all
contributor evidence and preserves distinct IDs from a single tracker. It does not
prove physical identity across providers/cameras. Custom detection-http and narrow
Needle Router imageBase64/noul remain the only spatial/decision contracts here;
there is no native NVIDIA adapter. A2A and automatic framing-target dispatch roles
remain disabled until qualified implementations exist.

After Gate 02 checks passed, Gate 03 began with a bounded OpenAI SSE adapter and
strict typed tool execution boundary. It uses shared egress and concurrency limits,
fully validates complete tool calls and never executes a streaming delta. Only
registered server-side handlers can run after session ownership/privacy checks.
Idempotency state lives in existing jobs.sqlite and survives encrypted recovery;
interrupted calls remain outcome_unknown. No real research handler is registered.
Full conversation HTTP/UI orchestration, durable turns, grounded tools, lifecycle
cleanup and capability probes are still pending. See [v3-gate02-report.md](v3-gate02-report.md)
for evidence, limits and the remaining Gate 03/Phonon/A2A work.


## Gate 03 / Gate 05 implemented continuation

The earlier foundation/reserved descriptions are historical checkpoints. The active
implementation now adds `conversation.py`, `mentor_state.py`, `research_jobs.py`,
and the official SDK adapter in `research.py` to the existing authentication,
provider registry and application lifespan. Owned chat turns execute independently
of SSE readers and use durable event cursors. Whole validated assistant tool-call
messages precede correlated tool outputs and bounded model continuations.
`retrieve_video_evidence` queries the existing versioned index; `summarize_scene`
reads selected owned observation metadata without raw frames.

Conversation, tool and research tables share jobs.sqlite and its encrypted backup
scope. Crashed generations remain unknown, known remote tasks reconcile, and
ambiguous submissions never replay. A separate bounded asynchronous coordinator
uses official A2A SDK submit/get/cancel. Agent Cards cannot redirect the configured
endpoint or choose authentication. Completed structured research is untrusted
advisory evidence and enters Qwen only through an explicit owned continuation.

Live embeds the reusable MentorConversation panel without changing camera lifetime
ownership; `/mentor` offers the panel separately. The existing YAML studio remains
authoritative, with explicit A2A bearer/path-token selection. Defaults/examples stay
disabled; actual model, agent and deployment qualification are separate from fixture
acceptance. See v3-gate03-report.md and v3-gate05-report.md for bounds and evidence.
