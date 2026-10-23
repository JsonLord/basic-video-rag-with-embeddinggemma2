# Hugging Face runtime variables — v3

Set these through the private Space's Variables and Secrets UI when deployment is
separately approved. This implementation does not modify any Space or credentials.
There is no requirement for a local .env file, local Qwen weights or another registry.

| Name | HF setting | Use |
| --- | --- | --- |
| OPENAI_COMPATIBLE_URL | Variable | HTTPS OpenAI-compatible root or /v1 base URL |
| OPENAI_COMPATIBLE_MODEL | Variable | Actual configured Qwen/model identifier; no assumption it is installed |
| OPENAI_COMPATIBLE_API_KEY | Secret | Bearer authentication, server-side only |
| A2A_URL | Variable or Secret | Reserved approved outbound agent endpoint; SDK dispatch remains Gate 05 |
| A2A_TOKEN | Secret | Reserved agent credential |
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
   same registry. It stays disabled and its adapter fails closed until Gate 05.
4. Environment presence never enables a route or grants sensitive trust. Defaults
   start public_only and disabled. Review/apply a YAML route and approved_sensitive
   trust before sending private conversation or camera data.
5. “Use HF defaults in draft” explicitly previews schema v2 plus missing defaults;
   it does not save. Validate and CAS apply remain separate administrator actions.

Missing variables leave the application/local cameras operational. Malformed or
unapproved configured environment endpoints produce environment_configuration_invalid
in the authenticated provider API and an explicit error in the admin studio.
An authorized YAML override can remain operational despite an invalid unused default.
No raw URL with credentials, query or fragment is accepted. HTTPS exact-host checks,
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
capabilities. Research dispatch and automatic framing target-selection contracts
remain reserved/disabled until their typed execution is implemented/qualified.

CPU Docker remains BLOCKED by the recorded registry manifest policy denial.
Infrastructure approval may be needed for registry-1.docker.io, auth.docker.io,
deb.debian.org, security.debian.org and any actually observed image redirect hosts.
Do not bypass TLS/proxy policy, use arbitrary image mirrors, restart shared services,
publish an allowlist or deploy as part of code qualification.
