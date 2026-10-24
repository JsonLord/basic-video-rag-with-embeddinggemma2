# Live provider qualification — Gate 06

The current candidate is fixture-qualified. Qwen and A2A live probes are
**BLOCKED_CREDENTIALS**, not passed. Source inspection, mocked SDK traffic, and
local process recovery do not attest to a deployed provider. The dated evidence
is under `docs/v3-evidence/gate06/`; older qualification evidence is preserved.

## Qwen / OpenAI-compatible conversation

`scripts/qualify-qwen.py` reads only the inherited secure environment:

| Entry | Required operator value |
| --- | --- |
| OPENAI_COMPATIBLE_URL | Approved HTTPS gateway root or `/v1`; no credentials/query/fragment |
| OPENAI_COMPATIBLE_MODEL | Exact served model ID; do not infer availability from a model name |
| OPENAI_COMPATIBLE_API_KEY | Dedicated provider credential in secure environment settings |
| VM_ALLOWED_HOSTS | Exact approved gateway hostname, appended to existing approved hosts |

The managed cloud platform may reserve OPENAI_ proxy-secret target names. Use a
supported secure environment mechanism or a trusted operator machine; do not rename
the requested production HF variables or substitute another provider/integration key.

The CLI accepts no credential argument and never reads credential files or source
code for values. It does not start FastAPI, access application state, create a chat,
execute a tool, modify YAML, change trust, or pull a model. A fresh-process fixture
proves it works even when VM_STATE_DIR is an unreadable-as-directory sentinel.
The tool registry now imports its default database only when actually requested;
the diagnostic supplies an inert storage callback and cannot execute handlers.

The qualifier uses existing destination validation, proxy/CA trust and SSE/tool
validation. It permits only `/v1/models` and `/v1/chat/completions` beneath the
approved base, refuses redirects and stops on permanent authorization failures.
There are at most seven requests in a complete run:

1. Bounded model listing; missing `/models` is reported UNSUPPORTED, not fabricated.
2. A bounded basic greeting with `max_tokens=64`.
3. A text stream, recording client time to first text token and total latency.
4. A typed tool-call emission with the existing retrieve_video_evidence schema.
5. A correlated assistant/tool/result continuation using a clearly synthetic result.
6. Client cancellation after the first text delta, checking response closure and
   provider-slot release. Remote compute cancellation remains NOT_OBSERVABLE.
7. A short client deadline (default 100 ms). If the response completes before the
   deadline, timeout behavior is NOT_OBSERVED rather than claimed as tested.

Streaming requests retain the application's 1,024-token limit, response/context
bounds and per-call total deadline. Model/basic JSON has a 1 MiB response cap and
an overall deadline. Configured model identity is checked against both basic and
streamed responses. A missing reported model or unobserved deadline yields PARTIAL;
a model mismatch, malformed output, unavailable tools or failed continuation fails.

Evidence contains booleans, configured public model ID, host, safe request IDs,
HTTP status, closure, counts and timings. It contains no prompts, generated text,
full endpoint URLs, tool arguments/IDs, headers or credentials. Existing evidence
files cannot be overwritten. Exit codes: 0 PASS, 2 BLOCKED, 1 FAIL/PARTIAL.
`PASS` covers these client capabilities; it does not prove provider auth enforcement,
private-media permission, model quality, server identity or production readiness.
The qualifier always uses synthetic text with public_only trust.

Use the existing CPU venv or install the hashed CPU requirements into an isolated
Python 3.12 environment. No Node server, FFmpeg, GPU or model weights are needed
for this script. The CLI itself uses httpx, Pydantic and PyYAML from those pins.
Configure secrets securely before invoking it; do not put the value on the command
line, in an .env file committed to Git, or in the evidence filename.

Linux, from the repository root:

```bash
python3.12 -m venv .venv-qualification
.venv-qualification/bin/python -m pip install --require-hashes -r requirements-runtime.txt
.venv-qualification/bin/python scripts/qualify-qwen.py \
  --backend unknown --timeout-ms 30000 --timeout-probe-ms 100 \
  --output /tmp/qwen-qualification-NEW-RUN.json
```

Windows PowerShell, with the same variables already provided securely:

```powershell
py -3.12 -m venv .venv-qualification
.\.venv-qualification\Scripts\python.exe -m pip install --require-hashes -r requirements-runtime.txt
.\.venv-qualification\Scripts\python.exe scripts\qualify-qwen.py --backend unknown --timeout-ms 30000 --timeout-probe-ms 100 --output "$env:TEMP\qwen-qualification-NEW-RUN.json"
```

Choose a new filename for every run. Preserve corporate proxy and CA settings.
Neither TLS verification nor application host authorization can be bypassed by a
CLI flag. The environment provider being probed may differ from an explicit YAML
route; that route still wins and needs its own qualification before activation.

### Ollama and vLLM are separate server contracts

Pinned upstream source references are in `gate06/upstream-sources.json`.
Ollama's OpenAI compatibility document declares chat streaming and tools, but marks
`tool_choice` unsupported. It documents that local Ollama ignores the API key;
therefore a successful request cannot prove gateway authentication enforcement.
vLLM's tool documentation requires a compatible model/chat template and selected
tool parser for automatic calls (documented flags include enable-auto-tool-choice
and tool-call-parser). Their availability varies by server/model version.

The diagnostic uses the common tools schema without forcing tool_choice, parallel
execution options or a particular reasoning parser. `--backend ollama|vllm` is an
operator declaration, not server attestation. A whitelisted response-header hint
is recorded separately; no flags or deployments are changed to make a probe pass.
Do not restart DGX or pull a model. Record the existing server version/parser/model
with the operator and interpret failures against that actual installation.

## Agent Zero / Spynel A2A discovery

Run the existing read-only `python scripts/qualify-a2a.py` after securely supplying:

```text
A2A_URL=https://leon4gr45-openoperator.hf.space/a2a/t-{token}
A2A_TOKEN=<secure secret, never a literal in the URL setting>
VM_ALLOWED_HOSTS=<existing approved hosts plus leon4gr45-openoperator.hf.space>
```

The braces in `{token}` are literal template syntax. HF Space Secrets and this
managed development environment's secret bindings are separate. A named binding
or proxy placeholder alone is not proof of readiness. Do not extract proxy-held
credentials to form a raw local URL.

The official SDK remains pinned to 0.3.26. Discovery validates the typed Agent Card,
protocol version, name/version/skills, declared input/transport, exact advertised
URL, auth compatibility and required extensions. It never follows a card to another
host/interface. Legacy Agent Zero agent.json discovery is attempted only after a
404 on agent-card.json. Path-token mode sends no guessed bearer header. The
128 KiB decoded-response limit, compressed-response handling, redirects/auth denial,
card destination checks and INFO log redaction are fixture-tested.

For the current real process: A2A_URL is present, A2A_TOKEN is absent, and the agent
host is absent from VM_ALLOWED_HOSTS. The script exits before an HTTP request.
Actual protocol, agent identity/skills, advertised URL and URL-path proxy secret
substitution remain NOT_TESTED. A discovery pass alone would not qualify research.

### Separate approval required for a remote task

No live research job was submitted. After discovery succeeds, the proposed bounded
qualification question is: “Explain HTTP byte Range requests in one short paragraph,
using the official RFC 9110 source, and return its HTTPS citation.” No cameras,
recordings, transcripts or library attachments would be sent. The proposed test
would submit once, retain its message/task/context IDs, poll with a bounded watcher,
verify the structured cited artifact, and reopen only a disposable local coordinator
process to prove reconciliation. Ambiguous submissions would not be repeated.

This is a reviewable proposal only. Obtain separate explicit authorization before
submitting it, testing cancellation on a live task, or creating remote agent state.
Continue using the existing mocked SDK lifecycle/restart tests until then.
