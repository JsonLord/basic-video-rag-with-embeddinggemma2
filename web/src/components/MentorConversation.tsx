"use client";

import { useEffect, useRef, useState } from "react";
import { api, token, download, Observation } from "@/lib/mentor";
import { ClipPlayer, ClipRef } from "@/components/ClipPlayer";

type Turn = {
  id: string;
  status: string;
  error?: string;
  payload: {
    text?: string;
    provider?: string;
    model?: string;
    history_revision?: number;
  };
  messages: { role: string; content: string }[];
};
type Conversation = { id: string; title: string; turns: Turn[] };
type Research = {
  id: string;
  status: string;
  error?: string;
  cancel_requested: boolean;
  result?: {
    text: string;
    authority: string;
    citations: { url: string; title: string }[];
  };
};
type Event = {
  seq: number;
  turn: string;
  type: string;
  data: {
    text?: string;
    name?: string;
    model?: string;
    result?: { citations?: ClipRef[] };
    [key: string]: unknown;
  };
};
const root = "/api/mentor/conversations";
const terminal = new Set([
  "completed",
  "failed",
  "cancelled",
  "outcome_unknown",
]);

async function readEvents(
  id: string,
  after: number,
  signal: AbortSignal,
  receive: (e: Event) => void,
) {
  const response = await fetch(`${root}/${id}/events?after=${after}`, {
    headers: { Authorization: `Bearer ${token()}` },
    signal,
  });
  if (!response.ok)
    throw new Error(`Conversation events unavailable (${response.status})`);
  if (!response.body)
    throw new Error("Streaming is unavailable in this browser");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let pending = "";
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      pending += decoder.decode(value, { stream: true });
      let boundary: number;
      while ((boundary = pending.indexOf("\n\n")) >= 0) {
        const packet = pending.slice(0, boundary);
        pending = pending.slice(boundary + 2);
        const data = packet
          .split("\n")
          .filter((line) => line.startsWith("data: "))
          .map((line) => line.slice(6))
          .join("\n");
        if (data) receive(JSON.parse(data) as Event);
      }
      if (pending.length > 65536)
        throw new Error("Conversation event exceeded the safety limit");
    }
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}

export function MentorConversation({
  session = null,
  observations = [],
  transcript = "",
}: {
  session?: string | null;
  observations?: Observation[];
  transcript?: string;
}) {
  const [history, setHistory] = useState<{ id: string; title: string }[]>([]);
  const [id, setId] = useState("");
  const [conversation, setConversation] = useState<Conversation | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [research, setResearch] = useState<Research[]>([]);
  const [text, setText] = useState("");
  const [consent, setConsent] = useState(false);
  const [refs, setRefs] = useState<string[]>([]);
  const [error, setError] = useState("");
  const [sending, setSending] = useState(false);
  const [hasRetry, setHasRetry] = useState(false);
  const [clip, setClip] = useState<ClipRef | null>(null);
  const [provider, setProvider] = useState(
    "Select an enabled conversation route in Models & Routing",
  );
  const mounted = useRef(false);
  const retry = useRef<{
    conversation: string;
    request: {
      request_id: string;
      text: string;
      live_session: string | null;
      observation_refs: string[];
      allow_research: boolean;
      research_refs: string[];
    };
  } | null>(null);
  const active =
    sending || !!conversation?.turns.some((t) => !terminal.has(t.status));

  useEffect(() => {
    mounted.current = true;
    const controller = new AbortController();
    if (!token())
      return () => {
        mounted.current = false;
        controller.abort();
      };
    void api<{ id: string; title: string }[]>(
      root,
      undefined,
      false,
      undefined,
      controller.signal,
    )
      .then((rows) => {
        setHistory(rows);
        if (rows[0]) setId(rows[0].id);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => {
      mounted.current = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    let cursor = 0;
    let initial = true;
    const refresh = async () => {
      while (!controller.signal.aborted) {
        try {
          const state = await api<Conversation>(
            `${root}/${id}`,
            undefined,
            false,
            undefined,
            controller.signal,
          );
          if (initial) {
            setEvents([]);
            initial = false;
          }
          setConversation(state);
          const latest = state.turns.at(-1)?.payload;
          if (latest?.model)
            setProvider(
              `${latest.provider} · ${latest.model} · config ${latest.history_revision}`,
            );

          await readEvents(id, cursor, controller.signal, (event) => {
            if (event.seq <= cursor) return;
            cursor = event.seq;
            setEvents((old) => [...old, event].slice(-4096));
          });
        } catch (e) {
          if (controller.signal.aborted) return;
          setError(
            e instanceof Error
              ? e.message
              : "Connection interrupted; retrying from the saved event cursor",
          );
        }
        await new Promise<void>((resolve) => {
          const timer = setTimeout(resolve, 1200);
          const abort = () => {
            clearTimeout(timer);
            resolve();
          };
          controller.signal.addEventListener("abort", abort, { once: true });
          setTimeout(
            () => controller.signal.removeEventListener("abort", abort),
            1201,
          );
        });
      }
    };
    void refresh();
    return () => controller.abort();
  }, [id]);

  useEffect(() => {
    if (!id) return;
    const controller = new AbortController();
    const refresh = () =>
      void api<Research[]>(
        `/api/research/jobs?conversation_id=${id}`,
        undefined,
        false,
        undefined,
        controller.signal,
      )
        .then(setResearch)
        .catch((e) => {
          if (!controller.signal.aborted) setError(e.message);
        });
    refresh();
    const timer = setInterval(refresh, 1500);
    return () => {
      clearInterval(timer);
      controller.abort();
    };
  }, [id]);

  async function newConversation() {
    const created = await api<{ id: string; title: string }>(root, {
      title: "Mentor conversation",
    });
    setHistory((old) => [created, ...old]);
    setId(created.id);
    setConversation(null);
    return created.id;
  }
  async function send(message = text, researchRefs: string[] = []) {
    if (!message.trim() || active) return;
    setSending(true);
    setError("");
    try {
      let pending = retry.current;
      if (!pending) {
        const cid = id || (await newConversation());
        pending = {
          conversation: cid,
          request: {
            request_id: crypto.randomUUID(),
            text: message,
            live_session: session,
            observation_refs: observations
              .slice(0, 10)
              .map((o) => `${o.camera_id}:${o.frame_id}:${o.request_id}`)
              .filter((ref) => refs.includes(ref)),
            allow_research: consent,
            research_refs: researchRefs,
          },
        };
        retry.current = pending;
        setHasRetry(true);
      }
      await api(`${root}/${pending.conversation}/turns`, pending.request);
      retry.current = null;
      setHasRetry(false);
      setText("");
      setConsent(false);
      setRefs([]);
      const next = await api<Conversation>(`${root}/${pending.conversation}`);
      setConversation(next);
    } catch (e) {
      setError(
        `${e instanceof Error ? e.message : "Send failed"}. Retry sends the same request ID; it cannot start a duplicate turn.`,
      );
    } finally {
      if (mounted.current) setSending(false);
    }
  }
  async function remove() {
    if (!id) return;
    try {
      await api(`${root}/${id}`, undefined, false, "DELETE");
      setHistory((old) => old.filter((item) => item.id !== id));
      setId("");
      setConversation(null);
      setEvents([]);
      setResearch([]);
      retry.current = null;
      setHasRetry(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Deletion failed");
    }
  }
  const eventTurns = new Set(events.map((e) => e.turn));
  return (
    <section
      aria-label="Mentor conversation"
      className="mt-8 space-y-4 rounded-xl border border-line bg-surface p-5"
    >
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="text-xl">Mentor conversation</h2>
        <span className="text-xs text-muted">{provider}</span>
      </div>
      <p className="text-sm text-muted">
        Advisory conversation. Only selected observation metadata is shared.
        Research requires separate consent. Earlier completed turns are bounded
        by the context budget.
      </p>
      <div className="flex flex-wrap gap-2">
        <select
          aria-label="Conversation history"
          value={id}
          disabled={sending}
          onChange={(e) => {
            retry.current = null;
            setHasRetry(false);
            setId(e.target.value);
          }}
          className="rounded border border-line bg-bg p-2"
        >
          <option value="">New conversation</option>
          {history.map((item) => (
            <option key={item.id} value={item.id}>
              {item.title} · {item.id.slice(0, 6)}
            </option>
          ))}
        </select>
        <button
          disabled={active}
          onClick={() => {
            retry.current = null;
            setHasRetry(false);
            setId("");
            setConversation(null);
            setEvents([]);
            setResearch([]);
          }}
          className="rounded border border-line px-3"
        >
          New
        </button>
        <button
          disabled={!conversation}
          onClick={() =>
            download(
              `mentor-${id}.json`,
              JSON.stringify({ conversation, research }, null, 2),
            )
          }
          className="rounded border border-line px-3"
        >
          Export
        </button>
        <button
          disabled={!id}
          onClick={() => void remove()}
          className="rounded border border-line px-3"
        >
          Delete conversation
        </button>
      </div>
      <div
        aria-live="polite"
        aria-label="Conversation transcript"
        className="max-h-[32rem] space-y-4 overflow-auto"
      >
        {conversation?.turns.map((turn) => {
          const streamed = events
            .filter((e) => e.turn === turn.id && e.type === "text")
            .map((e) => e.data.text || "")
            .join("");
          const saved = turn.messages
            .filter((m) => m.role === "assistant")
            .map((m) => m.content)
            .join("\n");
          return (
            <article
              key={turn.id}
              className="space-y-2 border-b border-line pb-4"
            >
              <p>
                <strong>You: </strong>
                {turn.payload.text}
              </p>
              <p className="whitespace-pre-wrap">
                <strong>Mentor: </strong>
                {turn.status === "completed"
                  ? saved
                  : streamed || "Waiting for provider…"}
              </p>
              <p className="text-xs text-muted">
                {turn.status}
                {turn.error && ` · ${turn.error}`}
              </p>
              {eventTurns.has(turn.id) && (
                <details>
                  <summary className="cursor-pointer text-sm">
                    Tool execution and provenance
                  </summary>
                  {events
                    .filter((e) => e.turn === turn.id && e.type !== "text")
                    .map((e) => (
                      <div key={e.seq} className="mt-2">
                        <pre className="max-h-48 overflow-auto whitespace-pre-wrap text-xs">
                          {JSON.stringify({ type: e.type, ...e.data }, null, 2)}
                        </pre>
                        {e.data.result?.citations
                          ?.filter((c) => c.video_id)
                          .map((c) => (
                            <button
                              key={`${c.video_id}-${c.start}`}
                              className="mr-3 underline"
                              onClick={() => setClip(c)}
                            >
                              {c.title} · {c.start}s
                            </button>
                          ))}
                      </div>
                    ))}
                </details>
              )}
            </article>
          );
        })}
      </div>
      {session && (
        <fieldset className="space-y-1 text-sm">
          <legend>Share selected camera observations with the Mentor</legend>
          {observations.slice(0, 10).map((o) => {
            const ref = `${o.camera_id}:${o.frame_id}:${o.request_id}`;
            return (
              <label key={ref} className="block">
                <input
                  type="checkbox"
                  checked={refs.includes(ref)}
                  onChange={(e) =>
                    setRefs((old) =>
                      e.target.checked
                        ? [...old, ref]
                        : old.filter((r) => r !== ref),
                    )
                  }
                />{" "}
                {o.camera_id} · frame {o.frame_id} ·{" "}
                {o.provider_results.map((r) => r.status).join(", ")}
              </label>
            );
          })}
        </fieldset>
      )}
      {transcript && (
        <button
          type="button"
          onClick={() => setText(transcript.slice(0, 4000))}
          className="rounded border border-line px-3 py-2"
        >
          Use speech transcript in message
        </button>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void send();
        }}
        className="space-y-3"
      >
        <label className="block">
          Message to Mentor
          <textarea
            aria-label="Message to Mentor"
            value={text}
            onChange={(e) => setText(e.target.value)}
            maxLength={4000}
            rows={3}
            className="mt-1 w-full rounded border border-line bg-bg p-3"
          />
        </label>
        <label className="block text-sm">
          <input
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
          />{" "}
          Allow the approved research agent to receive this turn’s research
          question and selected reference IDs
        </label>
        <div className="flex gap-3">
          <button
            type="submit"
            disabled={active || !text.trim()}
            className="rounded border border-line px-4 py-2"
          >
            {hasRetry ? "Retry same message" : "Send message"}
          </button>
          <button
            type="button"
            disabled={!active || !id}
            onClick={() =>
              void api(`${root}/${id}/cancel`, {}).catch((e) =>
                setError(e.message),
              )
            }
            className="rounded border border-line px-4"
          >
            Stop generation
          </button>
        </div>
      </form>
      {error && (
        <p role="alert" className="text-sm">
          {error}
        </p>
      )}
      <div aria-label="Research jobs" className="space-y-3">
        <h3>Research jobs</h3>
        <p className="text-xs text-muted">
          Stopping chat does not cancel research. Results are untrusted advisory
          evidence; source links are not independently verified.
        </p>
        {research.map((job) => (
          <article key={job.id} className="rounded border border-line p-3">
            <p>
              {job.id} · <strong>{job.status}</strong>
              {job.cancel_requested && " · cancellation requested"}
            </p>
            {job.error && <p role="alert">{job.error}</p>}
            {!new Set(["completed", "failed", "cancelled"]).has(job.status) && (
              <button
                onClick={() =>
                  void api(`/api/research/jobs/${job.id}/cancel`, {}).catch(
                    (e) => setError(e.message),
                  )
                }
                className="underline"
              >
                Cancel research
              </button>
            )}
            {job.result && (
              <>
                <p className="whitespace-pre-wrap">{job.result.text}</p>
                <ul>
                  {job.result.citations.map((citation) => (
                    <li key={citation.url}>
                      <a
                        href={citation.url}
                        rel="noopener noreferrer"
                        target="_blank"
                        className="underline"
                      >
                        {citation.title}
                      </a>
                    </li>
                  ))}
                </ul>
                <button
                  disabled={active}
                  onClick={() =>
                    void send(
                      "Incorporate this completed research into an updated answer. Explain uncertainty and cite the supplied sources.",
                      [job.id],
                    )
                  }
                  className="mt-2 rounded border border-line px-3 py-2"
                >
                  Incorporate completed research
                </button>
              </>
            )}
          </article>
        ))}
      </div>
      <ClipPlayer clip={clip} onClose={() => setClip(null)} />
    </section>
  );
}
