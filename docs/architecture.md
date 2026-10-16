# Visual Mentor architecture

## M0 baseline (2026-10-16)

Baseline commit: 7f8922cad8adb7e73a5f95ecfbf5b1a73e5bd46f. There are no automated tests or CI workflows. Next.js 16.4 / React 19.3 provide client-side library, search, Ask, experiments and dynamic video details. FastAPI mounts Range-capable media and exposes those views' data APIs. Existing startup eagerly imports torch and initializes a CUDA SentenceTransformer; it fails in a CPU runtime before serving health. The NumPy index also assumes files exist. RAG sends local file URLs to vLLM. Offline ingestion and evaluation remain valuable legacy tools.

## Milestones

1. M1: split CPU runtime from optional offline/local inference, remote adapters and compatible indexes, preserve data routes and graceful empty states.
2. M2: standalone Next.js and FastAPI behind a single port 7860; Docker health and resource validation.
3. M3: explicit dual-camera capture, bounded sampling, correlated observations and overlays.
4. M4: strict routing configuration, admin APIs, atomic history and Models UI.
5. M5: typed remote perception/routing, provider contract tests and transcription.
6. M6: observation-to-guidance interfaces, regression/security checks and deployment documentation.

Each milestone receives tests and a commit. No production deployment or DGX modification is included. Real USB cameras, real providers and private Space access require external validation.

## Design

Keep the existing Next.js application and data APIs. The CPU backend owns configuration snapshots, destination validation, adapters, routing and ephemeral sessions. Browser cameras never belong to the server. Secrets remain server-side environment references. Remote embedding spaces require explicit index metadata; legacy indexes remain inspectable but cannot be searched with a different remote model. The standalone frontend is necessary because existing video detail routes are dynamic and cannot be exported without knowing the complete library at build time.
