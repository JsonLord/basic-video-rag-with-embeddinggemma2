# Gate 03 — durable conversational Mentor

Implementation continues from `9e31e867669519cd985562ce63487d760cba6a0d` on
`feature/visual-mentor-v3-live`, Draft PR #3. Gate 02 remains intact. Gate 03 is
operational with configured providers and qualified with synthetic OpenAI transport;
**live Qwen and production deployment remain unqualified**.

## Implemented behavior

The existing authenticated API now creates, lists, reads, exports (GET), deletes,
and cancels owned conversations. POST `/api/mentor/conversations/{id}/turns`
accepts a required client `request_id`, text, selected live-session observation
references, per-turn research consent, and completed owned `research_refs`.
Retries with the same request return its durable turn; different contents conflict.
Only one generation per conversation runs at once. GET `/{id}/events?after=N`
streams authenticated SSE with persistent sequence IDs. A browser disconnect
only detaches the reader. Explicit POST `/{id}/cancel` stops generation and closes
provider IO; it does not silently cancel remote research.

Conversation ownership, turns, provider/model identity, configuration revision,
selected observation metadata, tool calls/results, citations, and statuses live
in existing `jobs.sqlite`. Interrupted generations become `outcome_unknown` on
startup; they are never automatically regenerated. Complete assistant tool-call
messages and correlated tool results are sent back through the existing provider
adapter. A whole, valid stream must finish before any tool executes. Typed argument,
privacy, ownership, egress, and durable idempotency checks remain mandatory.

The production path registers real `retrieve_video_evidence`, `summarize_scene`,
and the three research handlers. Retrieval searches the existing versioned index
with its configured embedding provider and returns video IDs, segment indices,
timestamps, text, and revision/embedding-space provenance. Scene retrieval resolves
only selected owned session references and rechecks session ownership; unavailable
or expired observations fail. No raw frame, microphone data, snapshot, or recording
is attached to chat or research automatically. Observations are uncertain provider
reports. Research and source text are explicitly untrusted evidence, never authority.

The Live panel supports progressive text, history, provider identity, stop,
expandable execution/provenance, clip playback, research progress/results, deletion
and JSON export. The existing bounded push-to-talk transcription can be copied into
the composer through an explicit review button; it is never auto-sent. `/mentor` offers the same panel separately. Conversation and
research network effects clean up on navigation; existing camera ownership and
record/replay/import components remain unchanged. Research polling is independent
of chat streaming. Completed research enters another model generation only through
an explicit “Incorporate completed research” click. Polling never creates turns.

## Bounds and revocation

- Four model generations and five total tool calls per user turn. Reused call IDs
  within a turn fail closed. The ledger is scoped to the durable turn.
- Existing provider concurrency/timeouts and HTTPS destination restrictions apply.
  Conversation/research roles require one explicit provider; no automatic replay
  on a fallback provider after an uncertain generation or submission.
- At most 20 provider context messages / 32K content characters. Prior context keeps
  whole completed turns fitting eight messages / 12K serialized characters.
  Coverage records exact included turn IDs; omitted turns are not silently summarized.
- User input 4K characters, selected context payload 14K, tool arguments 8 KiB,
  tool results 32 KiB, continuation result text 12K. Over-limit context fails clearly.
- Text deltas are coalesced (64 characters or 50 ms after the first delta) before
  SQLite event writes. 4,096 events per turn; browser details retain the newest
  4,096 events. Complete completed-turn messages remain in authenticated export.
- 100 active conversations per owner, 200 turns per conversation. Capacity failures
  are explicit. Deleting a conversation removes content/events, requests owned
  research cancellation, and retains ownership/replay/reconciliation tombstones.
- The 10,000-call ledger reclaims only completed entries in terminal deleted
  conversation namespaces with no unresolved research. Running/unknown calls and
  active namespaces remain retained; exhaustion fails closed.
- Configuration revision, destination hash and resolved model are checked before
  each continuation; changed configuration prevents further sends. Tool dispatch
  rechecks revision and ownership. Credentials and endpoint paths are not persisted.

## Capability probe

The administrator's existing provider Test action now exercises synthetic streaming,
typed tool calls, result correlation, a model continuation, and client-side stream
cancellation. It reports configured and provider-reported model identity separately;
a missing reported model is unverified. A mismatched reported model fails. The
probe never upgrades trust or enables a route. Fixture tests cover 401/403 denial;
a live successful credential probe does not claim a live negative-auth test or
remote compute cancellation.

## Evidence and limitations

See `v3-evidence/gate03-complete/`, Gate 05 report, and the qualification addendum
for final test totals. Backend tests exercise actual SQLite, authenticated API/SSE,
real FFmpeg/age, and fresh-process recovery with synthetic external transports.
The browser integration ingests a synthetic video through real HTTP/FFmpeg/index
creation (explicit supplied transcript for a silent fixture), retrieves a real clip
citation, completes fixture A2A research, incorporates it, reloads history, and
checks both simulated camera stream IDs stay live throughout the conversation.
Only the two deliberately changed Live screenshots are updated.

No actual Qwen endpoint/credential was supplied in this environment. Physical
camera behavior, provider cost/latency, private HF authentication and CPU Docker
startup remain separate release gates. Optional Phonon-2 is unchanged/off.

Run one application API worker, as in the existing CPU supervisor. The startup
reconciliation/coordinator lifecycle is not qualified for multiple API processes
sharing the same working database.
