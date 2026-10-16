"use client";
import {AccessToken} from "@/components/AccessToken";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { getJSON, type AskResponse, type Hit, type View } from "@/lib/api";
import { fmtTs } from "@/lib/format";
import { VIEW_INFO } from "@/lib/views";
import { ClipPlayer, type ClipRef } from "@/components/ClipPlayer";
import { DimPicker, Segmented, ViewPicker } from "@/components/Controls";
import { SegmentCard } from "@/components/SegmentCard";

const SUGGESTIONS = [
  "What did Sam think about running heavily quantized models for coding?",
  "Which videos show a model controlling a computer UI, and what did it do?",
  "How does Nemotron 3 handle speaker diarization?",
  "What was shown on screen when comparing the Qwen3.8 27B variants?",
];

/** Turn [1] / [1, 3] citations into links the markdown renderer maps to clip buttons. */
function linkCitations(md: string): string {
  return md.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (_, nums: string) =>
    nums
      .split(",")
      .map((n) => `[${n.trim()}](#clip-${n.trim()})`)
      .join(""),
  );
}

function Answer({ res, onPlay }: { res: AskResponse; onPlay: (h: Hit) => void }) {
  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-line bg-surface p-5">
        <div className="prose-answer text-[15px] text-ink-2">
          <ReactMarkdown
            components={{
              a: ({ href, children }) => {
                const n = href?.startsWith("#clip-") ? Number(href.slice(6)) : NaN;
                const clip = res.clips[n - 1];
                if (!clip) return <a href={href}>{children}</a>;
                return (
                  <button
                    onClick={() => onPlay(clip)}
                    title={`${clip.title} @ ${fmtTs(clip.start)}`}
                    className="mx-0.5 rounded bg-surface-2 px-1.5 text-xs font-medium text-accent hover:bg-accent hover:text-white"
                  >
                    {n}
                  </button>
                );
              },
            }}
          >
            {linkCitations(res.answer)}
          </ReactMarkdown>
        </div>
        <div className="mt-4 flex flex-wrap gap-x-4 border-t border-line pt-3 text-xs text-muted tabular">
          <span>
            {VIEW_INFO[res.settings.view].label} @ {res.settings.dim}d · k={res.settings.k}
          </span>
          <span>
            inputs: transcript{res.settings.use_video ? " + video" : ""}
            {res.settings.use_audio ? " + audio" : ""}
          </span>
          <span>retrieve {(res.timing.retrieve_s * 1000).toFixed(0)} ms</span>
          <span>generate {res.timing.generate_s.toFixed(1)} s</span>
          <span>
            {res.usage.prompt_tokens.toLocaleString()} prompt → {res.usage.completion_tokens.toLocaleString()} output tokens
          </span>
        </div>
      </div>
      <div className="grid gap-2 md:grid-cols-2">
        {res.clips.map((c, i) => (
          <SegmentCard key={c.id} hit={{ ...c, rank: i + 1 }} onPlay={onPlay} />
        ))}
      </div>
    </div>
  );
}

export function AskView() {
  const [question, setQuestion] = useState("");
  const [view, setView] = useState<View>("text");
  const [dim, setDim] = useState(768);
  const [k, setK] = useState(4);
  const [useVideo, setUseVideo] = useState(true);
  const [useAudio, setUseAudio] = useState(false);
  const [current, setCurrent] = useState<AskResponse | null>(null);
  const [history, setHistory] = useState<AskResponse[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clip, setClip] = useState<ClipRef | null>(null);

  useEffect(() => {
    getJSON<AskResponse[]>("/api/answers").then(setHistory).catch(() => {});
  }, []);

  const ask = async (qText: string) => {
    if (!qText.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await getJSON<AskResponse>("/api/ask", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ question: qText, view, dim, k, use_video: useVideo, use_audio: useAudio }),
      });
      setCurrent(res);
      setHistory((h) => [res, ...h]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="grid gap-8 lg:grid-cols-[1fr_300px]">
      <div className="space-y-6">
        <section>
          <h1 className="text-2xl font-semibold">Ask / Mentor</h1><AccessToken/>
          <p className="mt-1 max-w-3xl text-sm text-ink-2">
            EmbeddingGemma 2 retrieves the top-k segments; Gemma 4 12B then reads each transcript and <em>watches</em> the clip
            (sampled frames, optionally the raw audio) before answering with citations.
          </p>
        </section>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(question);
          }}
          className="space-y-3"
        >
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                ask(question);
              }
            }}
            rows={2}
            placeholder="Ask anything about the videos…"
            className="w-full resize-none rounded-lg border border-line bg-surface px-4 py-3 outline-none focus:border-accent"
          />
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
            <ViewPicker value={view} onChange={setView} />
            <DimPicker value={dim} onChange={setDim} />
            <Segmented label="k" value={k} options={[2, 4, 6] as const} onChange={setK} />
            <label className="flex items-center gap-1.5 text-sm text-ink-2">
              <input type="checkbox" checked={useVideo} onChange={(e) => setUseVideo(e.target.checked)} /> send video
            </label>
            <label className="flex items-center gap-1.5 text-sm text-ink-2">
              <input type="checkbox" checked={useAudio} onChange={(e) => setUseAudio(e.target.checked)} /> send audio
            </label>
            <button className="ml-auto rounded-lg bg-accent px-5 py-2 font-medium text-white disabled:opacity-60" disabled={loading}>
              {loading ? "Watching clips…" : "Ask"}
            </button>
          </div>
        </form>

        {!current && !loading && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => {
                  setQuestion(s);
                  ask(s);
                }}
                className="rounded-full border border-line px-3 py-1 text-left text-sm text-ink-2 hover:text-ink"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {error && <p className="text-sm text-[#e66767]">{error}</p>}
        {current && (
          <div className={loading ? "opacity-50" : ""}>
            <h2 className="mb-3 text-lg font-medium">{current.question}</h2>
            <Answer res={current} onPlay={setClip} />
          </div>
        )}
      </div>

      <aside className="space-y-2">
        <h2 className="text-sm font-medium">History</h2>
        {history.length === 0 && <p className="text-xs text-muted">No answers yet.</p>}
        {history.map((h, i) => (
          <button
            key={`${h.created_at}-${i}`}
            onClick={() => setCurrent(h)}
            className={`block w-full rounded-lg border p-2 text-left text-sm hover:bg-surface-2 ${current === h ? "border-accent" : "border-line"}`}
          >
            <div className="line-clamp-2">{h.question}</div>
            <div className="mt-1 text-xs text-muted">
              {VIEW_INFO[h.settings.view].label} @ {h.settings.dim}d · {h.timing.generate_s.toFixed(1)}s
            </div>
          </button>
        ))}
      </aside>

      <ClipPlayer clip={clip} onClose={() => setClip(null)} />
    </div>
  );
}
