# Selective porting decisions

Donor: feature/visual-mentor at 245b686. Keep main web pages/components/styles as baseline.

- Port config/schema.py, vrag settings/providers/egress/routing/remote/research/mentor_api,
  CPU api/index/config adaptations and all 77 backend tests; retain security and contract fixtures.
- Port camera lifecycle and voice consent code plus browser safety tests; restyle in main tokens.
- Port Controls capability-aware selectors and truthful Ask/Search copy only, preserving markup.
- Port reproducible runtime lock, Docker base pins, process supervisor and test tooling.
  Add FFmpeg for bounded media jobs. Resource target is 2 CPU / 16GB, not old RSS target.
- Reject donor homepage, nav replacement, generic global vm styles and minimal Models editor.
- Rewrite Models as provider/route studio; extend durable ingestion and encrypted backup tools.
- Deployment PR audit: README SDK metadata and .hfignore useful; reject competing .mjs config,
  unrelated Agent.md and redundant API-doc toggle. Keep one next.config.ts, same-origin rewrites.
- Historical donor release reports are historical evidence only; never represent v2 validation.

Gates: seeded original UI screenshots and interactions before new feature work; backend/provider
and safety regression tests; real media Range/seek; ingestion mock integration; encrypted clean
restore; final build and Docker resource test. External activation and live credentials remain gates.
