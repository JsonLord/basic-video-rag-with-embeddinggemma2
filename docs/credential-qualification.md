# Dedicated credential qualification: NO-GO (18 October 2026)

The dedicated secure binding is now present and reports ready. Every qualification
request in this run used **VM_BACKUP_GITHUB_TOKEN**. The integration-managed GH_TOKEN
was not substituted. No backup architecture or application code was changed.

## Actual live results

| Check | Result |
| --- | --- |
| Private backup repository read, api.github.com | 200; private=true, read/write reported |
| New disposable release creation, api.github.com | 201 |
| First small age-encrypted asset POST, uploads.github.com | **404**, one attempt |
| Uploaded assets / committed checkpoints | **0 / 0**, verified by read-only queries |
| Destructive recovery and incremental checkpoint | Blocked by upload failure |
| Trusted-machine comparison | Unavailable: no independent trusted machine attached |
| Secure HF credential | Absent; private staging remains unqualified |

Upload request ID: `FE93:319F8B:36F88A:4FB435:6AD3F6B8`.
Disposable namespace: `test-recovery-20261017-745d0278` (the harness uses UTC host
clock naming; this qualification report uses the client Berlin date).
The new release is uncommitted and empty; no pre-existing release or checkpoint
was altered or deleted. No recurring workflow or production setting changed.

The client used GitHub's returned upload_url, validated its destination and
attached the dedicated authorization header. A GitHub response/request ID proves
an HTTPS service response, not which credential the proxy ultimately forwarded.
The earlier missing-binding problem is resolved. The former integration-token 401
is not reused as evidence about this token. The new 404 may conceal a private
resource/permission rejection or reflect credential propagation differences
between hosts. **Scope versus injection/proxy attribution remains undetermined.**
API release creation proves a successful write through that route; it does not
prove that the same upstream identity was used on the upload route.

Evidence:

- [Dedicated API probe](evidence/dedicated-token-api.json)
- [Current live upload/recovery attempt](evidence/github-recovery-live.json)
- [Qualification decision](evidence/credential-qualification.json)
- [Prior blocked attempt retained](evidence/github-recovery-prior-blocked.json)

## Exact next step: trusted-machine comparison

Use an independently trusted machine outside this managed proxy, provision the
**same permitted dedicated credential** there from its secure store, and check out
application branch feature/video-rag-mentor-v2. Do not export a proxy placeholder,
copy integration-managed credentials, paste credentials into chat, disable TLS,
or bypass this managed environment's network controls.

With Python 3.12+, uv, FFmpeg and age/age-keygen available, run from the checkout:

```sh
if [ -z "${VM_BACKUP_GITHUB_TOKEN:-}" ]; then
  echo 'Dedicated backup credential required' >&2
  exit 2
fi
uv run --frozen --group dev python tests/live_github_recovery.py
```

The guard prevents the harness's legacy GH_TOKEN fallback. The drill creates a new
disposable namespace and never deletes existing remote releases. Successful upload
continues to readback, committed checkpoints, unchanged incremental dedup and full
recovery after destroying local source/staging state, with fresh-process Library,
Search, config/index and media checks. Compare sanitized evidence JSON only.

- Outside succeeds while managed fails: managed credential propagation or proxy
  behavior is implicated; header stripping versus rewriting still needs trusted
  proxy observability. Do not weaken or work around its security controls.
- Outside also fails: review the credential's resource owner, selected private
  repository JsonLord/visual-mentor-backups, Contents read/write, Metadata read,
  expiry and any applicable organization authorization. Matching failures alone
  do not conclusively distinguish every GitHub policy/resource issue.

Private staging package remains prepared at deploy/hf-staging/README.md. Secure HF
credentials are still absent, and the existing public Space remains unchanged.
**NO-GO for first private staging deployment** until a dedicated-token asset upload
and complete GitHub-only recovery succeed and private staging access is qualified.
