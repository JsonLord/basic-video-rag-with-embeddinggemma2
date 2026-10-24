# Hugging Face runtime variables — v3

Set these through the private Space's Variables and Secrets UI when deployment is
separately approved. This implementation does not modify any Space or credentials.
There is no requirement for a local .env file, local Qwen weights or another registry.

| Name | HF setting | Use |
| --- | --- | --- |
| OPENAI_COMPATIBLE_URL | Variable | HTTPS OpenAI-compatible root or /v1 base URL |
| OPENAI_COMPATIBLE_MODEL | Variable | Actual configured Qwen/model identifier; no assumption it is installed |
| OPENAI_COMPATIBLE_API_KEY | Secret | Bearer authentication, server-side only |
| A2A_URL | Variable or Secret | Approved outbound agent URL; use the token template below for Agent Zero |
| A2A_TOKEN | Secret | Server-side agent credential; never export its value |
| VM_ALLOWED_HOSTS | Variable | Exact comma-separated approved inference/agent hostnames |

Existing distinct VM_USER_TOKEN, VM_ADMIN_TOKEN, origin policy, backup/recovery
secrets and other provider variables retain their existing requirements. Do not
reuse application, HF, GitHub, proxy or recovery credentials as provider secrets.

The cloud development platform may reserve names starting OPENAI_. That is a
managed-development binding restriction, not a change to the requested production
HF variable names. No managed secret binding was added or renamed by this work.

## Precedence and activation

1. A persisted YAML role (including an explicitly disabled role) wins over automatic
   environment defaults. Session overrides select already configured providers for
   the allowed live camera role; they cannot introduce destinations or credentials.
2. If no mentor.conversation role exists and the URL is configured, the effective
   registry gains hf-conversation, referencing the exact OPENAI_COMPATIBLE_* names.
   The model is resolved from OPENAI_COMPATIBLE_MODEL at dispatch. A YAML provider
   with an explicit model and no model_env overrides that environment model.
3. If research.dispatch is absent, configured A2A_URL supplies hf-research in the
   same registry. It stays disabled until explicit YAML authorization and Agent Card qualification.
4. Environment presence never enables a route or grants sensitive trust. Defaults
   start public_only and disabled. Review/apply a YAML route and approved_sensitive
   trust before sending private conversation or camera data.
5. “Use HF defaults in draft” explicitly previews schema v2 plus missing defaults;
   it does not save. Validate and CAS apply remain separate administrator actions.

Missing variables leave the application/local cameras operational. Malformed or
unapproved configured environment endpoints produce environment_configuration_invalid
in the authenticated provider API and an explicit error in the admin studio.
An authorized YAML override can remain operational despite an invalid unused default.
URL user-info credentials, query and fragment are rejected. Agent Zero path authentication uses the non-secret {token} template and a separate protected A2A_TOKEN. HTTPS exact-host checks,
public DNS/connect-time checks, TLS verification and no-redirect policy still apply.
The default conversation adapter accepts text, not raw images/audio/video. Standard
root and already-/v1 bases produce exactly /v1/chat/completions, never /v1/v1/....

The studio shows host/model, credential presence as a boolean, and not_checked live
status. Presence is not successful authentication, model availability, native NVIDIA
compatibility or A2A Agent Card validation. YAML exports contain references, not
secret values or endpoint values. A2A_URL may itself be secret; only its host is
shown. Endpoint paths and tokens are never returned in the environment summary.

## Deployment/qualification boundary

All new example profiles are disabled. Replace the detection gateway placeholder
only after its actual custom contract is verified; an arbitrary native NVIDIA URL
cannot be used as detection-http. Temporal reasoning and tracking are separate
capabilities. Research dispatch has an implemented SDK/coordinator path; live qualification and explicit activation remain required. Automatic framing target selection remains reserved/disabled.

CPU Docker remains BLOCKED by the recorded registry manifest policy denial.
Infrastructure approval may be needed for registry-1.docker.io, auth.docker.io,
deb.debian.org, security.debian.org and any actually observed image redirect hosts.
Do not bypass TLS/proxy policy, use arbitrary image mirrors, restart shared services,
publish an allowlist or deploy as part of code qualification.


## Agent Zero / Spynel path authentication

Set `A2A_URL` to the non-secret template
`https://leon4gr45-openoperator.hf.space/a2a/t-{token}` and set `A2A_TOKEN` only
as an HF Secret. Append `leon4gr45-openoperator.hf.space` to `VM_ALLOWED_HOSTS`
without removing other approved destinations. In schema-v2 routing YAML use:

```yaml
agent:
  adapter: a2a
  model: agent-card-unqualified
  base_url_env: A2A_URL
  api_key_secret: A2A_TOKEN
  auth_mode: path_token
  capabilities: [research_dispatch]
  trust: public_only
```

This is a provider stanza, not a complete active configuration. Discover the Agent
Card using the administrator's Test action or `python scripts/qualify-a2a.py`.
Then set `model` to the exact returned Agent Card name. Review privacy authorization
before selecting `approved_sensitive` and enabling the single-provider
`research.dispatch` route. Research is still gated by explicit per-turn consent.
No running Space setting or route is changed by these instructions.

Generic bearer agents use `auth_mode: bearer` and must declare compatible bearer
security in their Agent Card. Authenticated SDK discovery does not prove remote
research submission, polling, structured artifacts or cancellation work. Follow
[v3-gate05-report.md](v3-gate05-report.md) before claiming live qualification.

In this managed development environment, the saved draft contains only the new
A2A_URL requirement and A2A_TOKEN requirement scoped to the agent hostname.
Review/save, secure value entry and environment publication are user actions.
Proxy-backed substitution in URL paths remains to be tested; a placeholder variable
alone is neither a usable local credential nor evidence of failure. Production HF
Secrets are direct environment delivery. Never paste a full credential-bearing URL
into chat, YAML, screenshots or logs.

Conversation endpoints use the existing VM_USER_TOKEN. Provider qualification and
routing changes use the distinct VM_ADMIN_TOKEN. No additional authentication
system or inbound A2A callback is needed. Conversation/research metadata is included
in existing encrypted jobs.sqlite backup scope; recurring workflows remain inactive.
