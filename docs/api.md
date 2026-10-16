# API v1

The application publishes OpenAPI at `/openapi.json` and interactive schema documentation at `/docs` on the internal FastAPI service (or request the OpenAPI JSON through `/api/openapi.json` on the single public origin). API version is returned by `/api/health` and OpenAPI info.version. Configuration schema `version: 1` is separate from the monotonic configuration revision.

| Endpoints | Authorization / behavior |
| --- | --- |
| GET `/api/health` | lightweight, no inference or secrets |
| GET `/api/providers` | user bearer; redacted capability/destination registry |
| POST `/api/providers/{id}/test` | admin bearer; synthetic text/image only |
| GET `/api/config`, `/api/config/template`, `/api/config/profiles` | admin bearer; redacted configuration and examples |
| POST `/api/config/validate`, `/api/config/apply` | admin; `{yaml, expected_version}`; validation/diff or atomic apply |
| POST `/api/config/rollback` | admin; `{version, expected_version}`; creates a new revision from history |
| POST `/api/routing/dry-run` | admin; `{feature, camera_id}`; synthetic inputs only |
| POST `/api/live/sessions` | user; `{consent:true}`; explicit sensitive transfer consent |
| DELETE `/api/live/sessions/{id}` | owning principal; discard observations and late results |
| POST `/api/live/sessions/{id}/frames` | owner; typed FrameInput/Observation models in OpenAPI |
| GET `/api/live/sessions/{id}/events` | owner; bounded in-memory observation timeline |
| POST `/api/live/sessions/{id}/transcribe` | owner; `{audio:base64WebM, duration_ms}`; max 15 seconds/2 MB |
| PUT `/api/live/sessions/{id}/task` | owner; `{goal,step,completed}` advisory task state |
| POST `/api/live/sessions/{id}/guidance` | owner; remote mentor from recent typed observations/task state |
| `/api/videos`, `/api/videos/{id}`, `/api/stats`, `/api/answers`, `/api/experiments`, `/media/*` | retained library/evaluation APIs, protected by Space privacy |
| `/api/search`, `/api/search/image`, `/api/compare`, `/api/compare-views`, `/api/ask` | user bearer; preserved contracts, unsupported embeddings explicitly unavailable |

Frame requests include logical `camera_id`, monotonic numeric `frame_id`, browser performance.now `captured_at`, JPEG/WebP data URI, configured feature, configuration revision and request_id. Responses correlate those identifiers, receipt time, source dimensions, typed detections/decisions, provider latency/status and warnings. Browser device IDs never enter server YAML.

Status codes distinguish authentication (401), origin/destination access (403 or provider destination_denied), stale revision/frame (409), upload cap (413), strict input validation (422), rate/concurrency (429), and unavailable inference (503). Providers in a multi-route may fail independently; always inspect provider_results and warnings even on HTTP 200.

The extension-only `vrag.research.ResearchWorker` protocol defines future authenticated outbound jobs. No research service is deployed or called automatically.
