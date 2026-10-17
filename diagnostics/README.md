# Standalone GitHub encrypted-release probe

Copy **only `qualify_github_release.py`** to your trusted laptop/server if desired.
It needs Python 3.10+ and the official `age` / `age-keygen` executables on PATH.
No Visual Mentor installation, pip packages, GitHub CLI or application models are
required. It works with Linux and native Windows Python; Windows execution has not
been tested in this managed Linux environment.

Inject `VM_BACKUP_GITHUB_TOKEN` using your trusted machine's secure secret manager.
The script reads **only this environment variable** for credentials; it never reads
GH_TOKEN, credential files or command-line token arguments. Use the same permitted
credential as in the managed test, not a copied proxy placeholder. Limit it to the
private JsonLord/visual-mentor-backups repository, Contents read/write and Metadata
read. Do not paste credentials into command history, reports or chat.

The script keeps the machine's approved proxy/CA/TLS settings. Execute it on the
independent trusted machine normally; do not disable this managed environment's
proxy, firewall or certificate checks. Optional `--age` and `--age-keygen` arguments
accept executable paths when those tools are not on PATH.

## Linux / Debian: standalone upload test

Install the local prerequisites on your trusted Debian/Ubuntu server if needed:

```sh
sudo apt-get update
sudo apt-get install --no-install-recommends python3 age ca-certificates
```

With the credential already injected securely, run from the downloaded script's
folder (or use its absolute path):

```sh
python3 qualify_github_release.py --output standalone-upload.json
```

From the repository checkout the equivalent command is:

```sh
python3 diagnostics/qualify_github_release.py --output standalone-upload.json
```

Exit 0 means the new encrypted asset's SHA-256 was verified by downloading it.
Exit 2 means NO-GO; stop and inspect the sanitized evidence. No request is retried.
Without `--output`, a unique `github-release-qualification-<UTC timestamp>-<UUID>.json` is written in
the current directory. `--output /path/to/new.json` selects a new file explicitly;
an existing file is refused before any network call. Missing tools/credentials
also fail before creating a release.

## Windows: standalone upload test

Use Python 3.10+ (`py -3`) and PowerShell 7. Install the official pinned age tools
if they are not already on PATH:

```powershell
$tools = Join-Path $env:LOCALAPPDATA 'VisualMentorDiagnosticTools'
New-Item -ItemType Directory -Force -Path $tools | Out-Null
$zip = Join-Path $tools 'age-v1.2.1-windows-amd64.zip'
Invoke-WebRequest -Uri 'https://github.com/FiloSottile/age/releases/download/v1.2.1/age-v1.2.1-windows-amd64.zip' -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $tools -Force
$env:Path = "$(Join-Path $tools 'age');$env:Path"
Get-Command age.exe, age-keygen.exe
```

These commands are for x64 Windows; use the matching official age release for
other architectures. They contain no credential values. With the dedicated token
already injected securely into this PowerShell session, run:

```powershell
py -3 .\qualify_github_release.py --output .\standalone-upload.json
if ($LASTEXITCODE -ne 0) { throw 'Upload qualification failed; inspect the new JSON evidence.' }
```

From the application checkout use `py -3 .\diagnostics\qualify_github_release.py --output .\standalone-upload.json`.
Do not add a token argument. Paths with spaces work with `--age` / `--age-keygen`:

```powershell
py -3 .\qualify_github_release.py --age "$tools\age\age.exe" --age-keygen "$tools\age\age-keygen.exe"
```

## What the probe does

1. Generates a small synthetic payload and a disposable age identity in a temporary
   directory, encrypts the payload, and verifies a local decryption roundtrip.
2. Confirms the repository is private. Explicit denial of reported push permission
   stops the run; successful creation of the new test release proves an actual
   Contents-write operation (no repository file or checkpoint is edited).
3. Creates exactly one uniquely named `vm-credential-test-*` prerelease.
4. Validates and uses GitHub's returned upload_url for exactly one encrypted asset.
5. Downloads the asset by API ID and compares its ciphertext SHA-256 and byte count.
   Signed release redirects are allowlisted and receive **no Authorization header**.
6. Saves method, host, status, GitHub request ID, release/asset IDs and hash results.
   Tokens, plaintext payloads, recovery identities, response bodies and signed URLs
   are never printed or written to evidence. The temporary identity is destroyed.

Any HTTP rejection stops immediately, including 401/403/404. The unique release
and any successful synthetic upload remain for inspection; nothing is deleted.
Existing releases/checkpoints and all workflow settings remain untouched. The
probe does not dispatch workflows or deploy anything. Its upload GO alone does
not establish a complete recovery or private-HF staging GO.

## Only after upload GO: complete destructive GitHub recovery

The full existing drill requires the application checkout, Python 3.12, uv, FFmpeg,
age/age-keygen and the same dedicated credential. It does not require HF access.
Only the disposable local fixture is destroyed. All previous remote backups remain.
The commands below reuse the preceding `standalone-upload.json`; they do not create
another standalone probe release. If you selected a different output filename,
substitute that filename in the evidence check.
Its query embedding is a deterministic synthetic stub; index retrieval is real.

**Linux**, from the application checkout:

```sh
set -e
if [ -z "${VM_BACKUP_GITHUB_TOKEN:-}" ]; then
  echo 'Dedicated credential required; refusing integration fallback' >&2
  exit 2
fi
python3 -c 'import json; r=json.load(open("standalone-upload.json")); assert r["status"] == "passed" and r["asset_readback_verified"] and r["credential_source"] == "VM_BACKUP_GITHUB_TOKEN"'
# set -e stops unless the preceding standalone report proves upload + readback.
archive=$(mktemp -d "$PWD/docs/evidence/trusted-recovery-XXXXXXXX")
if [ -f docs/evidence/github-recovery-live.json ]; then
  cp docs/evidence/github-recovery-live.json "$archive/before.json"
fi
set +e
uv run --frozen --group dev --python 3.12 python tests/live_github_recovery.py
result=$?
set -e
if [ -f docs/evidence/github-recovery-live.json ]; then
  cp docs/evidence/github-recovery-live.json "$archive/after.json"
fi
if [ "$result" -ne 0 ]; then
  echo "NO-GO: recovery failed; evidence saved under $archive" >&2
  exit "$result"
fi
echo "GitHub recovery GO; evidence saved under $archive"
```

**Windows PowerShell 7**, from the application checkout with uv, FFmpeg and age on
PATH and Python 3.12 installed:

```powershell
if (-not $env:VM_BACKUP_GITHUB_TOKEN) { throw 'Dedicated credential required; refusing integration fallback.' }
py -3 -c "import json; r=json.load(open('standalone-upload.json')); assert r['status'] == 'passed' and r['asset_readback_verified'] and r['credential_source'] == 'VM_BACKUP_GITHUB_TOKEN'"
if ($LASTEXITCODE -ne 0) { throw 'NO-GO: upload/readback report missing or failed; do not run recovery.' }
$archive = Join-Path (Get-Location) ('docs\evidence\trusted-recovery-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $archive | Out-Null
$evidence = '.\docs\evidence\github-recovery-live.json'
if (Test-Path $evidence) { Copy-Item $evidence (Join-Path $archive 'before.json') }
uv run --frozen --group dev --python 3.12 python tests\live_github_recovery.py
$result = $LASTEXITCODE
if (Test-Path $evidence) { Copy-Item $evidence (Join-Path $archive 'after.json') }
if ($result -ne 0) { throw "NO-GO: recovery failed; evidence saved under $archive" }
Write-Host "GitHub recovery GO; evidence saved under $archive"
```

The harness creates another disposable namespace, commits two verified checkpoints,
checks unchanged incremental dedup, deletes source and staging, recovers using
GitHub plus the protected test identity, and checks every restored file hash,
SQLite integrity/logical rows, fresh-process Library/Search/config/index, authorized
media Range, anonymous media denial and FFmpeg decoding. It never deletes remote
releases or activates workflows. Archive copies preserve pre-existing local evidence
before the existing harness writes its fixed report filename.

Return only the new standalone JSON and the archived `after.json` for review.
Outside success with managed failure implicates host-specific credential/proxy
handling; matching failures require repository/permission/policy investigation.
Neither result alone proves whether a proxy strips versus replaces Authorization.

## Recorded managed result

The first standalone run reproduced API write success and upload **404**; full
recovery was therefore **not run**. See the immutable unique JSON under
`docs/evidence/standalone-probes/` and the qualification report. No outside-machine
or Windows live run is claimed. Four stdlib unittest cases validate the mocked
success/security/failure paths (`python -m unittest discover -s diagnostics/tests -v`).
Production workflows stay inactive. First private staging deployment remains NO-GO
until complete live recovery and the remaining private-HF checks are established.
