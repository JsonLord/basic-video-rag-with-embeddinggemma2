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

Before adding v2 fields, use a distinct strict ConfigurationV2 model and explicit
v1-to-v2 migration preserving original serialized history and version tags. Readers
must accept both versions; exports retain the version; CAS and rollback validate
the selected original version. Do not relabel unknown v2 YAML as v1 or silently
ignore new fields. Migration tests must cover history restart/rollback and backup
restore before switching writers. This migration is designed, not implemented here.

Gate 02 retains the verified custom detection-http gateway and narrow Needle Router
imageBase64/noul contracts. Existing mock transport tests cover parallel provenance
and partial failures. No native NVIDIA adapter or new upstream schema is invented.
Gate 03 requires streaming conversation/tool contracts; Gate 04 optional pinned
Phonon engine qualification; Gate 05 official A2A SDK and durable jobs. Those remain
implementation work, separate from unavailable live integrations. Default Docker
and encrypted backup architecture are unchanged and no external service is enabled.
