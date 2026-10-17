# Remote provider contracts and v2 qualification

No large model runs inside this Space. Runtime readiness is not inferred from a
configured API key, health endpoint, placeholder model ID or mock result.

| Adapter | Request contract | Actual v2 evidence |
| --- | --- | --- |
| `laya-vision` | Router root + POST `/v1/system-one`; object `state`, typed `questions`, bare `imageBase64` | Live synthetic image passed 2026-10-17, 22.632s; no real camera |
| `detection-http` | Gateway `/detect`, normalized boxes plus matching frame/camera IDs and dimensions | Mock contract only; no NVIDIA endpoint/model configured |
| `openai-transcription` | `/audio/transcriptions`, multipart audio file + model | Mock HTTP and real FFmpeg audio extraction; no live Whisper credentials |
| `openai-embeddings` | `/embeddings`, model + input; finite nonzero vector | Mock pipeline, version/dimension isolation; no live model configured |
| `openai-chat-vision` | `/chat/completions`, bounded transcript/text and optional base64 image URLs | Mock answers/citations and image payload safety; no live VLM configured |

Laya source contract was recovered during donor review from
`JsonLord/laya-inference`, source revision
`77b324ac6c72efee883c41fd333e84007c55bed0`. The donor fixture/tests preserve that
source envelope and the observed live `results.answers` alternative. Upstream
README `image` is not the JSON gateway image field. The historical source had a
placeholder backend; actual live readiness says placeholder=false, and adapter
requires backend=laya-vision and model=thaitea/laya-vision. Only a fixed `noul`
question about image inspectability is implemented. It is not a captioner,
spatial detector or proof of semantic mentoring quality. No boxes are invented.
The current runtime had a Laya credential available despite the environment
configuration inventory not listing one. It was used through the normal adapter
without reading/logging its value. `authorization_header_sent` records that a
header was sent; authentication enforcement was not tested.

NVIDIA is an explicit gateway protocol, not an assumption that any NVIDIA/NIM
model supports spatial detection. A deployment must provide a verified gateway
matching `vrag/providers.py` or add an upstream-source-verified adapter after
review. Placeholder IDs cannot be enabled. OpenAI provider base URLs normally
include `/v1`; Laya uses its router root. Secrets stay in referenced server env vars.

Routing supports single, fallback, parallel (all/first_valid/quorum), sequential
(typed previous output), conditional predicates and spatial/semantic fusion.
Quorum failure reports no valid quorum; ordinary partial failures retain successful
outputs. Per-session overrides reuse configured provider identities/capabilities,
recheck destinations on dispatch, stop local previews when applied and discard
in-flight results if routing changes. They do not persist defaults.

Text indexes identify endpoint/model, full dimension, preprocessing, modality,
segmentation and corpus revision. Only declared MRL dimensions may be used. New
jobs atomically switch CURRENT after a complete revision, reusing compatible
unchanged segment vectors. Frame/video/audio/fused embedding adapters remain
**unimplemented and unavailable**: text similarity is not a substitute. Historical
compatible index files/charts are retained, not regenerated or requalified here.

Destination policy: exact approved HTTPS hosts, no URL credentials/query/fragment,
no private/metadata IPs, no redirects, TLS verification, bounded payloads/responses,
per-provider concurrency/circuit control. Direct requests pin validated public IPs
with original hostname/SNI. A configured trusted proxy owns DNS on that path and
must independently enforce public-only DNS/metadata denial. Real deployment egress
policy is an outstanding staging check.
