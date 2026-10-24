# Gate 06 optional Phonon-2 feasibility

**SOURCE_REVIEW_ONLY; disabled/not installed.** Existing remote transcription and
its fallback stay unchanged. Phonon does not block Qwen/A2A qualification.

Primary sources are pinned in `v3-evidence/gate06/upstream-sources.json` and
`phonon-source-review.json`: fermionresearch/phonon at
36760a4f5281f7d94d20c37387381af4dda5184c, its CPU/install documentation and
Phonon-2 CPU Docker recipe, plus FermionResearch/Phonon-2 model metadata at
3e6ab3a81d73b4d424ff34cc72535deb606378ef. No upstream script was executed.

| Area | Source finding / actual limit |
| --- | --- |
| Code license | Apache-2.0 |
| Weights license | CC-BY-4.0, derived from NVIDIA parakeet-tdt-0.6b-v3; retain attribution/NOTICE obligations |
| Package | fermion-research, PyPI metadata inspected at 0.2.14; module/CLI fermion |
| CPU packaging | Upstream Phonon-2 CPU recipe uses CPU Torch, Transformers, soundfile/scipy/zstandard/safetensors and HF tooling; not the default application's lightweight stack |
| Input envelope | English, 16 kHz mono/stereo; formats outside the envelope require bounded conversion or rejection |
| Linux CPU | x86-64 SSE4.1+ or supported Arm64 NEON; faster tiers need additional ISA support |
| Model artifact | Upstream-declared 163,515,201 compressed bytes, 177,716,675 unpacked bytes; no weights downloaded or hash verification performed on weights |
| Memory | Expanded artifact is about 169.5 MiB on disk; this is NOT resident/peak RAM. Runtime libraries, activations and decode buffers add memory; actual HF peak RSS is unmeasured |
| Published performance | Vendor hardware results are not this app's CPU Basic measurements; no extrapolated p50/p95 or FPS |
| Current result | No install, model loading, inference, CPU POC or Space change |

The managed development CPU's architecture/features were recorded for planning,
not treated as the future HF machine's ISA. The upstream CPU documentation includes
Phonon-2 and later families; this review does not silently select Phonon-2.5 or
substitute its multilingual behavior for the requested Phonon-2 English envelope.
Package/latest-release metadata is not a guarantee that a particular binary/CPU
combination is compatible.

A proof of concept is deferred because the Docker candidate cannot build and adding
Torch/Transformers or first-run model downloads would change the default runtime
being qualified. If separately authorized later, use an isolated environment and
pinned package/model hashes, disable automatic downloads, limit threads to the
actual CPU budget, convert bounded audio to the verified envelope, and measure
idle/load RSS and ASR p50/p95 alongside camera/ingestion/chat workloads. Prove timeout,
cancellation and remote transcription fallback before introducing any opt-in adapter.
No local ASR capability or performance is claimed by this source review.
