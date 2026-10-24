# Gate 05 — asynchronous A2A research

The application now has an official A2A SDK adapter and durable research coordinator.
**GO for fixture-qualified implementation; NO-GO for live research/production
activation until the agent and private deployment pass external qualification.**
No Space, remote worker, DGX service, release, or recurring workflow was changed.

## SDK, discovery, authentication and destination

`a2a-sdk==0.3.26` is pinned in the base manifest, `uv.lock`, and hashed CPU runtime
requirements. Its official PyPI project links to `a2aproject/a2a-python`; license is
Apache-2.0. The 0.3 SDK JSON-RPC ClientFactory is used for `message/send`,
`tasks/get`, and `tasks/cancel`. Non-streaming, non-blocking submission (`polling=True`)
returns a durable remote Task. Newer SDK 1.x is a different protocol/API and is not
silently substituted. No A2A server/worker extras, GPU packages or model weights
are installed. A fresh frozen base runtime import passed without Torch,
Transformers or vLLM; that is not a Docker build result.

All destination validation reuses the existing server-side registry, exact HTTPS
allowlist, public-address checks, trusted proxy/TLS transport and redirect denial.
The transport bounds each response to 128 KiB and admits only the configured RPC
URL and its two discovery paths. SDK AgentCard types validate discovery. The client
tries `/.well-known/agent-card.json`, then `/.well-known/agent.json` only on 404.
The advertised URL must exactly match the configured endpoint (a trailing slash is
normalized). Alternate interfaces, required unsupported extensions, mismatched
transport or agent identity fail closed. Only declared text input is supported.
Card descriptions never become system instructions. Card identity/version/skills
are bounded and credential-checked before being returned or saved.

The user selected:

```text
A2A_URL=https://leon4gr45-openoperator.hf.space/a2a/t-{token}
A2A_TOKEN=<secure setting; never put the value in YAML or chat>
```

Configure this provider with `auth_mode: path_token`, `api_key_secret: A2A_TOKEN`
and `base_url_env: A2A_URL`. Upstream Agent Zero's `helpers/fasta2a_server.py`
and `docs/guides/a2a-setup.md` document `/a2a/t-<key>` routing; its client documents
legacy Agent Card discovery. This establishes a source-backed candidate contract,
not the running Spynel deployment's revision or compatibility. Source qualification
metadata is recorded in `v3-evidence/gate05/source-contract.json`.

For generic agents, `auth_mode: bearer` requires a matching HTTP bearer declaration
in the Agent Card. The adapter does not send an additional guessed bearer header
in path-token mode. Before enabling dispatch, set the provider's `model` field to
its exact verified Agent Card `name`; `agent-card-unqualified` cannot be enabled.
The existing Models & Routing studio includes the A2A authentication selector.
Probe success does not grant permission to send private content.

Actual URL paths and credentials are excluded from SQL, browser metadata and
exception messages. HTTPX path-token logs are redacted; tests assert this at INFO.
Managed proxy credential substitution in a URL path is still an external
qualification requirement. A present proxy placeholder alone is not proof that
path substitution works; do not bypass the proxy or print it to diagnose this.

## Durable lifecycle

POST `/api/research/jobs` requires an owned conversation, explicit consent and a
stable request ID; the public endpoint accepts a question without camera attachments.
The model tool can attach only separately authorized reference IDs. One approved
agent identity, `documentation_research`, resolves through the authoritative
`research.dispatch` route. The model cannot supply a URL or credential.

Dispatch durably inserts `queued` and returns its job ID immediately. The independent
coordinator commits `dispatching` before HTTP IO, uses stable message/idempotency
identities, and records remote task/context IDs. It maps submitted, working,
input-required, completed, failed, rejected, canceled and auth-required into the
application states. GET job/artifacts and POST cancel require the same owner and
conversation. A public authenticated listing supports the UI.

A restarted known task is polled, never resubmitted. Interrupted dispatch without a
remote ID becomes `outcome_unknown`, with no blind replay. Lost submission responses
also remain unknown. Poll/cancel failures have bounded retries (six), exponential
backoff capped at 60 seconds, and a 24-hour local deadline. Authentication,
destination/identity changes and permanent validation failures stop retries.
Cancellation requests are idempotent: queued work cancels locally; known remote
work uses SDK cancellation. Unknown task identity cannot be reported as remotely
cancelled. A disabled/changed route does not send old task IDs to another destination.

The coordinator runs at most two IO operations concurrently. Input-required tasks
are displayed as such; this version does not invent an agent-specific input-resume
protocol. Unknown operations require operator reconciliation through the authorized
agent before any new submission; there is no automatic “retry submit” button.

Final artifacts must be bounded text containing a structured JSON object:

```json
{"text":"Research summary", "citations":[{"url":"https://source.example/page", "title":"Source title"}]}
```

At least one HTTPS citation is required. Arbitrary files, script URLs, credential
URLs, unknown object fields, overlarge output and sensitive metadata fail safely.
Links are never fetched by the application. Valid outputs remain explicitly
untrusted advisory evidence with agent/task/configuration provenance; a valid schema
is not independent verification of the research claims. Completion stores/displays
evidence; only an explicit owned conversation continuation sends it to Qwen.

## Actual qualification and pending live probe

Deterministic tests use the real official SDK against HTTPX JSON-RPC Agent Card/task
fixtures. Local database/API/process execution is real. They cover submit, poll,
cancel, duplicate request IDs, lost submission responses, fresh-interpreter
reconciliation, cancellation without duplicate submits, cross-owner denial,
malicious citations, redirected/auth-denied discovery, bearer declaration validation,
and credential log redaction. The conversation/browser test covers async completion
while camera streams remain active. Real age encryption + destructive local restore
also preserves conversations, research identities and tool idempotency together.
These are mock/local integration categories, not live external agent success.

Secure `A2A_URL` and `A2A_TOKEN` are absent in the actual task process. The saved
cloud draft adds the token requirement scoped only to the selected agent host and
the URL template variable; it requires user review/save/publication. Existing
settings were preserved. Also append that hostname to application `VM_ALLOWED_HOSTS`
without removing the existing destinations. Nothing was published by this task.

After secure settings are available, run the read-only probe:

```bash
/workspace/visual-mentor-venv/bin/python scripts/qualify-a2a.py
```

It prints sanitized Agent Card metadata or an error code, never submits a task,
and never logs credentials. A successful discovery still requires a separately
reviewed synthetic remote research lifecycle test before live qualification. A card
advertising another internal URL, unsupported protocol/auth or a missing durable
Task is a blocker; do not weaken checks, modify the external agent, or deploy a
workaround. Keep production routes/examples and all production schedules inactive.

Run one application API worker, as in the existing CPU supervisor. The startup
reconciliation/coordinator lifecycle is not qualified for multiple API processes
sharing the same working database.
