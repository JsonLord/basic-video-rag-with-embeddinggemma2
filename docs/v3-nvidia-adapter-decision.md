# Gate 06 NVIDIA detector / adapter decision

**Decision: preserve detection-http; do not invent or activate a native NVIDIA
adapter. Native NVIDIA qualification is BLOCKED_ENDPOINT_AND_CONTRACT.** No NVIDIA
URL, credential or deployed model identifier is available in this environment.
No model was deployed/pulled and no inference service was restarted.

## Source-backed candidate versus deployed provider

NVIDIA NV-Grounding-DINO is a plausible text-conditioned, per-image object detector
for an operator's requested framing categories. It produces spatial detections.
Cosmos spatial/video reasoning is a different capability and is not evidence of
high-frequency detection, persistent tracking identities, or acceptable frame latency.
No source inspection establishes which model is deployed on the user's DGX.

Inspected primary sources, with blob hashes in `gate06/upstream-sources.json`:

- [NVIDIA/Multi-Model-Workflows native sample](https://github.com/NVIDIA/Multi-Model-Workflows/blob/453688dfb8b0b8ba1d0755fcb611d1576fbb11d8/cv_nim/gdino_nim.py).
- [NVIDIA-Omniverse Grounding DINO function](https://github.com/NVIDIA-Omniverse/usd-content-agents/blob/0709377ed35fb066361a0d6735d21984b885fe36/world_understanding/functions/cv/grounding_dino.py).

These sources use `https://ai.api.nvidia.com/v1/cv/nvidia/nv-grounding-dino` with
an asset-upload operation at api.nvcf.nvidia.com, a returned signed upload URL,
NVCF asset-reference headers, a Grounding-Dino message/media_url payload, optional
202 task polling and a ZIP containing a .response JSON file. The sample extracts
`choices[0].message.content.boundingBoxes`; its annotation describes phrase,
bboxes and confidence, with boxes described as x/y/width/height. It is not the
application's normalized XYXY `/detect` JSON contract. The source is not a live
numeric response proving coordinate units, origin, model version or latency.

The published examples also include unbounded/long IO and archive extraction
patterns that should not be copied into this application. A future native client
would need verified numeric output, public destination authorization for each
asset/poll stage, safe bounded archive parsing, frame/dimension correlation and
privacy/retention review. A presigned upload URL must not grant arbitrary egress.
Without an actual selected authorized endpoint, adding this client would introduce
an unqualified integration rather than qualify the existing one.

## Current executable contract

An operator may provide an existing approved gateway matching detection-http:
normalized [x1,y1,x2,y2] in [0,1], positive area, matching camera/frame/source
width/height, bounded multiple detections, and genuine upstream IDs only when
object_tracking is declared. Pixel XYWH values must not be silently relabelled as
normalized XYXY. Conversion must use the verified original image dimensions and
upstream coordinate semantics. No new wrapper/service was installed here.

The browser tracker associates sampled detections within a camera/source; it does
not infer motion between frames or prove physical identity. Mirroring is a display
transform and does not rewrite canonical source boxes. Automatic framing already
selects the highest-confidence available track once and keeps it until explicit
reset/mode change; expiration returns full frame. Gate 06 adds a browser test that
checks this with two objects, reordered confidence, two camera namespaces and loss.
This is browser framing policy, not the reserved model-driven target-selection role.

| Required behavior | Actual evidence | Qualification category |
| --- | --- | --- |
| Coordinates, dimensions, frame correlation | Existing provider/live contract and Gate 02 routing tests | Mock HTTP + real local validation |
| Scale, aspect, contain/cover, mirroring | framing.spec.ts; recording.spec.ts; live.spec.ts | Pure geometry + simulated browser |
| Multiple/duplicate boxes and result fusion | test_v3_configuration.py; test_v3_routing.py | Synthetic detector transport |
| Stable per-camera/source/upstream IDs | framing.spec.ts; recording.spec.ts; new gate06-framing.spec.ts | Browser association fixtures |
| Delayed, stale or changed-revision results | release.spec.ts; test_v3_routing.py | Simulated browser/local HTTP |
| Timeout, fallback, partial failure, Hybrid | test_routing.py; test_v3_routing.py | Mock NVIDIA gateway + Laya |
| Automatic target selection / retention / loss | gate06-framing.spec.ts | Two simulated cameras, mock boxes |
| Native model response / throughput | NOT TESTED | No authorized inference endpoint |
| Native p50 / p95 latency | UNMEASURED | No values inferred from fixture timings |

## Critical-path recommendation

Keep the NVIDIA/gateway spatial role independent of Laya. Laya is optional semantic
scoring, cannot supply boxes and is not required for the browser preview/framing.
All distributed routes remain disabled until operator activation. For a live
low-latency spatial path, qualify the detector-only profile first. Hybrid parallel
all-results intentionally waits for both providers; it is not a latency benchmark
or a recommendation to put a slow scorer on the critical path. The historical
single Laya synthetic-image result (22.632 s) does not establish a useful live FPS
or a current latency distribution.

Once an authorized detector exists, record actual model revision and endpoint
contract, source dimensions, request/response sizes, sample count, cold/warm state,
per-frame p50/p95, timeout/partial-failure rate and resource impact while both cameras
and ingestion/chat are active. Do not benchmark invented native requests or claim
native NVIDIA acceptance from the mock-box tests above.
