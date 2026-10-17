"use client";

import { useEffect, useState } from "react";
import { getJSON, type Experiments, type Stats, type View } from "@/lib/api";
import { bytes, fmtDuration } from "@/lib/format";
import { VIEW_INFO } from "@/lib/views";
import { ViewSwatch } from "@/components/Controls";

/* ---------- diagram primitives ---------- */

function Node({
  title,
  sub,
  tag,
  children,
  accent,
  className = "",
}: {
  title: string;
  sub?: string;
  tag?: string;
  children?: React.ReactNode;
  accent?: string;
  className?: string;
}) {
  return (
    <div
      className={`relative rounded-xl border border-line bg-surface p-4 ${className}`}
      style={accent ? { boxShadow: `inset 3px 0 0 ${accent}` } : undefined}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="font-medium">{title}</div>
        {tag && <span className="shrink-0 rounded bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-ink-2">{tag}</span>}
      </div>
      {sub && <div className="mt-0.5 text-xs text-muted">{sub}</div>}
      {children && <div className="mt-2 space-y-1 text-sm text-ink-2">{children}</div>}
    </div>
  );
}

/** Connector between nodes: horizontal on wide screens, vertical when stacked. */
function Arrow({ label }: { label?: string }) {
  return (
    <div className="flex shrink-0 items-center justify-center py-1 text-muted md:px-1 md:py-0">
      <div className="flex flex-col items-center gap-0.5 md:flex-row">
        {label && <span className="whitespace-nowrap text-[11px] md:order-2 md:hidden">{label}</span>}
        <svg width="28" height="16" viewBox="0 0 28 16" className="hidden md:block" aria-hidden>
          <path d="M1 8h24M19 2l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <svg width="16" height="22" viewBox="0 0 16 22" className="md:hidden" aria-hidden>
          <path d="M8 1v18M2 13l6 6 6-6" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </div>
    </div>
  );
}

function Section({ n, title, blurb, children }: { n: number; title: string; blurb: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <div>
        <div className="flex items-baseline gap-3">
          <span className="font-mono text-sm text-muted">{String(n).padStart(2, "0")}</span>
          <h2 className="text-lg font-semibold">{title}</h2>
        </div>
        <p className="mt-1 max-w-3xl text-sm text-ink-2">{blurb}</p>
      </div>
      {children}
    </section>
  );
}

function Group({ label, children, className = "" }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <div className={`relative rounded-2xl border border-line p-4 pt-7 ${className}`}>
      <span className="absolute -top-2.5 left-4 bg-page px-2 text-xs text-muted">{label}</span>
      {children}
    </div>
  );
}

function Code({ children }: { children: React.ReactNode }) {
  return <code className="rounded bg-surface-2 px-1 py-0.5 font-mono text-[12px] text-ink">{children}</code>;
}

/* ---------- page ---------- */

const EMBED_VIEWS: View[] = ["text", "frame", "video", "audio", "fused"];
const VIEW_INPUT: Record<string, string> = {
  text: "title: {title} | text: {transcript}",
  frame: "{ image: NNN.jpg }",
  video: "{ video: NNN.mp4 }  · ~30 frames × 140 tok",
  audio: "{ audio: NNN.wav }  · 30s × 25 tok",
  fused: "title… | text… <|video|> <|audio|>",
};

export function ArchitectureView() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [exp, setExp] = useState<Experiments | null>(null);

  useEffect(() => {
    getJSON<Stats>("/api/stats").then(setStats).catch(() => {});
    getJSON<Experiments>("/api/experiments").then(setExp).catch(() => {});
  }, []);

  const seg = stats?.segments ?? 427;
  const vids = stats?.videos ?? 15;
  const built = stats?.views_built ?? {};
  const perView768 = seg * 768 * 4;

  return (
    <div className="space-y-14">
      <section>
        <h1 className="text-2xl font-semibold">Architecture</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-2">
          {vids} videos and {seg} segments. CPU media processing and remote inference share the original Video RAG interface. Text indexes, model identity and dimensions stay versioned; multimodal research views below require compatible historical indexes.
        </p>
      </section>

      {/* 1. Runtime topology */}
      <Section
        n={1}
        title="Runtime topology"
        blurb="Two supervised processes. Next.js exposes port 7860; FastAPI stays on loopback. Inference uses authorized remote HTTPS providers."
      >
        <div className="flex flex-col items-stretch md:flex-row md:items-center">
          <Node title="Browser" sub="HTTPS · laptop and USB cameras" tag="HTTPS" className="md:w-48">
            <div className="font-mono text-xs">private-space.hf.space</div>
          </Node>
          <Arrow label="HTTP" />
          <Group label="HF CPU Basic · 2 vCPU / 16 GB RAM" className="flex-1">
            <div className="flex flex-col items-stretch lg:flex-row lg:items-center">
              <Node title="Next.js 16" sub="web/ · pages + proxy" tag=":7860" className="lg:w-52">
                <div>Library · Search · Ask</div>
                <div>Experiments · Architecture</div>
                <div className="text-xs text-muted">rewrites /api, /media → :8000</div>
              </Node>
              <Arrow />
              <Node title="FastAPI" sub="vrag/api.py · uv venv" tag=":8000" className="lg:w-56">
                <div>search · compare · ask</div>
                <div>experiments · range-served mp4</div>
              </Node>
              <Arrow />
              <div className="grid flex-1 gap-2">
                <Node title="Remote embeddings" sub="approved HTTPS · model-versioned" accent="var(--series-1)" tag="remote">
                  <div className="text-xs">query + corpus text embeddings</div>
                </Node>
                <Node title="Vector index" sub="numpy · brute-force cosine" accent="var(--series-3)" tag={`${stats?.views.length??0}×${seg}×${stats?.dims[0]??"–"}`}>
                  <div className="text-xs">data/index/&#123;view&#125;.npy · {bytes(stats?.storage[0]?.bytes_per_view??0)} per view</div>
                </Node>
                <Node title="Remote VLM / LLM" sub="no local weights or DGX dependency" accent="var(--series-5)" tag="HTTPS">
                  <div className="text-xs">answers · transcription · eval queries</div>
                </Node>
              </div>
            </div>
          </Group>
        </div>
      </Section>

      {/* 2. Offline pipeline */}
      <Section
        n={2}
        title="Build pipeline"
        blurb="Browser import creates a persisted job. One bounded CPU worker prepares media; remote transcription/embedding failures are visible and retryable."
      >
        <div className="flex flex-col items-stretch xl:flex-row xl:items-stretch">
          <Node title="Source files" sub="Browser upload" tag="input" className="xl:w-44">
            <div>{vids} library videos</div>
            <div className="text-xs text-muted">64 MiB / 30 minute limit</div>
          </Node>
          <Arrow />
          <Node title="ingest" sub="vrag/jobs.py" tag="ffmpeg" className="xl:flex-1">
            <div>640px CPU H.264 proxy (faststart)</div>
            <div>SHA-256 deduplication; resumable job stages</div>
            <div className="text-xs text-muted">→ video.mp4 · thumb.jpg · meta.json</div>
          </Node>
          <Arrow />
          <Node title="transcribe" sub="vrag/jobs.py → remote STT" tag="remote STT" accent="var(--series-5)" className="xl:flex-1">
            <div>Whisper-compatible remote endpoint</div>
            <div>bounded 30s audio chunks</div>
            <div className="text-xs text-muted">→ transcript.json · manual transcript retry supported</div>
          </Node>
          <Arrow />
          <Node title="segment" sub="vrag/jobs.py → CPU keyframes" tag="~30s" className="xl:flex-1">
            <div>pack cues into ~30s windows</div>
            <div>preserve chunk timestamps; cue overlap is explicit</div>
            <div className="text-xs text-muted">→ timestamped metadata and keyframe JPEGs</div>
          </Node>
          <Arrow />
          <Node title="Remote text index" sub="vrag/jobs.py" tag="text only" className="xl:flex-1">
            <div>{seg} transcript segments</div>
            <div>validated dimension · normalized float32</div>
            <div className="text-xs text-muted">→ revision/text.npy · atomic CURRENT</div>
          </Node>
        </div>
      </Section>

      {/* 3. Embedding views */}
      <Section
        n={3}
        title="Historical research · five embedding views"
        blurb="Historical multimodal design: only valid for a verified shared embedding space. Current remote text adapters cannot reproduce these views. The UI enables only actually loaded indexes."
      >
        <div className="grid gap-4 lg:grid-cols-[260px_auto_1fr] lg:gap-0">
          <Node title="Segment 2RA7jWJvQ1U_006" sub="Which is The Best Qwen3.8-27B? · 3:20–3:57">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/sample/thumb-1.jpg" alt="" className="mt-1 aspect-video w-full rounded-md bg-black object-cover" />
            <div className="grid grid-cols-3 gap-1 pt-1 text-center text-[11px]">
              <span className="rounded bg-surface-2 py-0.5">transcript</span>
              <span className="rounded bg-surface-2 py-0.5">frames</span>
              <span className="rounded bg-surface-2 py-0.5">audio</span>
            </div>
          </Node>
          {/* Fan-out: stretches to the list height; curves end on the centres of the 5 embedding rows (of 6 equal rows). */}
          <div className="relative hidden w-14 lg:block">
            {/* Absolutely positioned so the SVG's intrinsic aspect ratio doesn't drive the row height. */}
            <svg viewBox="0 0 56 600" preserveAspectRatio="none" className="absolute inset-0 h-full w-full text-muted" aria-hidden>
              {EMBED_VIEWS.map((_, i) => {
                const y = (i + 0.5) * 100;
                return (
                  <path
                    key={i}
                    d={`M2 250 C 30 250, 26 ${y}, 54 ${y}`}
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                    vectorEffect="non-scaling-stroke"
                  />
                );
              })}
            </svg>
          </div>
          <div className="grid auto-rows-fr gap-2">
            {EMBED_VIEWS.map((v) => (
              <div key={v} className="grid items-center gap-3 rounded-lg border border-line bg-surface px-3 py-2 md:grid-cols-[110px_1fr_auto]">
                <span className="flex items-center gap-2 font-medium">
                  <ViewSwatch view={v} />
                  {VIEW_INFO[v].label}
                </span>
                <span className="font-mono text-xs text-ink-2">{VIEW_INPUT[v]}</span>
                <span className="text-xs text-muted tabular">
                  {built[v] ? `${built[v].ms_per_segment} ms/seg` : ""}
                </span>
              </div>
            ))}
            <div className="grid items-center gap-3 rounded-lg border border-dashed border-line px-3 py-2 md:grid-cols-[110px_1fr]">
              <span className="flex items-center gap-2 font-medium">
                <ViewSwatch view="hybrid" />
                {VIEW_INFO.hybrid.label}
              </span>
              <span className="text-xs text-ink-2">no extra vectors · reciprocal rank fusion of the text, video and audio rankings at query time</span>
            </div>
          </div>
        </div>
        <p className="text-xs text-muted">
          All inputs share one 8,192-token window: ~30 frames × 140 + ~750 audio tokens + transcript fits. Media gets no task
          prefix; text uses <Code>title: … | text: …</Code>.
        </p>
      </Section>

      {/* 4. Query path */}
      <Section
        n={4}
        title="Query → answer"
        blurb="Search retrieves timestamped transcript evidence. Ask sends transcripts and optional bounded keyframes to a configured remote model; citations open playable clips."
      >
        <div className="flex flex-col items-stretch xl:flex-row xl:items-stretch">
          <Node title="1 · Question" sub="text, or an image for screenshot search" className="xl:flex-1">
            <div className="text-xs">“what did Sam think about 3-bit models for coding?”</div>
          </Node>
          <Arrow />
          <Node title="2 · Embed query" sub="configured remote text model" accent="var(--series-1)" tag={exp ? `${exp.query_embed_ms.toFixed(0)} ms` : undefined} className="xl:flex-1">
            <div>
              <Code>model-specific input preparation</Code>
            </div>
            <div className="text-xs text-muted">→ model dimension, normalized vector</div>
          </Node>
          <Arrow />
          <Node title="3 · Validate dimension" sub="MRL only when declared" tag="versioned" className="xl:flex-1">
            <div>match model, view and index dimensions</div>
            <div>re-normalise both</div>
          </Node>
          <Arrow />
          <Node title="4 · Cosine top-k" sub="matmul over one view" accent="var(--series-3)" tag="NumPy" className="xl:flex-1">
            <div>{seg} scores per query</div>
            <div className="text-xs text-muted">hybrid: RRF over 3 rankings</div>
          </Node>
          <Arrow />
          <Node title="5 · Remote model answers" sub="transcripts + optional keyframes" accent="var(--series-5)" tag="provider latency" className="xl:flex-1">
            <div>per clip: transcript + frames</div>
            <div className="text-xs text-muted">raw audio reasoning unavailable; transcribe first</div>
          </Node>
          <Arrow />
          <Node title="6 · Cited answer" sub="markdown + [n]" className="xl:flex-1">
            <div>[n] → plays clip n at its timestamp</div>
            <div className="text-xs text-muted">saved to answers/history.jsonl</div>
          </Node>
        </div>
      </Section>

      {/* 5. Matryoshka */}
      <Section
        n={5}
        title="Matryoshka truncation"
        blurb="Historical MRL illustration. Truncation is enabled only when the model/index manifest explicitly declares supported dimensions. Remote text defaults use their full dimension."
      >
        <div className="space-y-2 rounded-xl border border-line bg-surface p-5">
          {[768, 512, 256, 128].map((d) => (
            <div key={d} className="grid grid-cols-[56px_1fr_120px] items-center gap-3">
              <span className="text-sm tabular">{d}d</span>
              <div className="h-5 rounded bg-surface-2">
                <div className="h-5 rounded" style={{ width: `${(d / 768) * 100}%`, background: "var(--series-1)", opacity: 0.35 + (d / 768) * 0.65 }} />
              </div>
              <span className="text-right text-xs text-muted tabular">
                {bytes(seg * d * 4)} / view {d !== 768 && `· ÷${(768 / d).toFixed(1)}`}
              </span>
            </div>
          ))}
          <p className="pt-2 text-xs text-muted">
            Re-normalising after slicing is required: a truncated unit vector is no longer unit length and silently skews cosine scores
            (<Code>vrag/index.py: truncate</Code>).
          </p>
        </div>
      </Section>

      {/* 6. Eval loop */}
      <Section
        n={6}
        title="Evaluation loop"
        blurb="Historical evaluation workflow. Preserve model labels and source provenance; synthetic sample scores demonstrate UI only and are not measured quality."
      >
        <div className="flex flex-col items-stretch lg:flex-row lg:items-stretch">
          <Node title="Sample segments" sub="vrag/evalset.py" className="lg:flex-1">
            <div>8 per video, skip intro/outro</div>
            <div className="text-xs text-muted">{exp ? `${exp.num_queries / 2} segments` : ""}</div>
          </Node>
          <Arrow />
          <Node title="Gemma 4 writes queries" sub="watches clip + reads transcript" accent="var(--series-5)" className="lg:flex-1">
            <div>spoken: something Sam says</div>
            <div>visual: something only on screen</div>
            <div className="text-xs text-muted">+ data/eval/manual.jsonl for your own</div>
          </Node>
          <Arrow />
          <Node title="Grid" sub="vrag/experiments.py" className="lg:flex-1">
            <div>6 views × 4 dims × {exp?.num_queries ?? "…"} queries</div>
            <div className="text-xs text-muted">R@1/5/10 · MRR@10 · ±1-seg · video hit</div>
          </Node>
          <Arrow />
          <Node title="Experiments page" sub="results.json → charts" className="lg:flex-1">
            <div>line chart · heatmap · per-query ranks</div>
          </Node>
        </div>
      </Section>

      {/* 7. Stack + files */}
      <Section n={7} title="Stack & files" blurb="Two Python environments keep vLLM's pinned torch/transformers away from the embedding stack.">
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-line bg-surface p-5">
            <table className="w-full text-sm">
              <tbody className="[&_td]:py-1.5 [&_tr]:border-t [&_tr]:border-line [&_tr:first-child]:border-0">
                <tr><td className="text-muted">Embedding</td><td>google/embeddinggemma-2 · sentence-transformers 6.1 · torchcodec</td></tr>
                <tr><td className="text-muted">Generator</td><td>google/gemma-4-12B-it-qat-w4a16-ct · vLLM 0.23 · MTP</td></tr>
                <tr><td className="text-muted">ASR</td><td>Gemma 4 12B (default, ~100 s for 3.9 h) · Whisper large-v3-turbo (alt, ~35 min)</td></tr>
                <tr><td className="text-muted">Index</td><td>numpy float32 · brute-force cosine</td></tr>
                <tr><td className="text-muted">API</td><td>FastAPI · uvicorn · range-served media</td></tr>
                <tr><td className="text-muted">Web</td><td>Next.js 16 · React 19 · Tailwind 4 · Recharts</td></tr>
                <tr><td className="text-muted">Corpus</td><td>{vids} videos · {stats ? fmtDuration(stats.total_duration_s) : "…"} · {seg} segments</td></tr>
              </tbody>
            </table>
          </div>
          <pre className="overflow-x-auto rounded-xl border border-line bg-surface p-5 font-mono text-xs leading-relaxed text-ink-2">{`vrag/            pipeline + API
  jobs.py        bounded upload → CPU proxy → remote STT → index
  providers.py   remote vision / detection / STT / embeddings
  mentor_api.py  live sessions, consent and authorized routing
  settings.py    atomic profile history and rollback
  backup/        encrypted snapshots and isolated restore
  index.py       cosine, MRL truncate, RRF
  remote.py      evidence → remote LLM → cited answer
  evalset.py     synthetic spoken/visual queries
  experiments.py view × dim metrics grid
  api.py         FastAPI for the site
serve/           historical offline research; not cloud runtime
web/             this site
scripts/dev.sh   CPU web + API only; no inference services`}</pre>
        </div>
      </Section>
    </div>
  );
}
