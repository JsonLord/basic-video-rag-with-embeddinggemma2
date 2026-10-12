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
          How the pieces fit: an offline pipeline turns {vids} videos into {seg} segments embedded five ways by EmbeddingGemma 2;
          at query time the same model embeds the question, a cosine search (at any Matryoshka size) picks segments, and Gemma 4
          12B watches those clips to answer. Everything runs on one box with an RTX PRO 6000 (96 GB).
        </p>
      </section>

      {/* 1. Runtime topology */}
      <Section
        n={1}
        title="Runtime topology"
        blurb="Three processes. Only the Next.js server is reachable over Tailscale; it proxies /api and /media to FastAPI, which talks to vLLM on loopback."
      >
        <div className="flex flex-col items-stretch md:flex-row md:items-center">
          <Node title="Browser" sub="any device on the tailnet" tag="tailscale" className="md:w-48">
            <div className="font-mono text-xs">&lt;tailnet-host&gt;:3000</div>
          </Node>
          <Arrow label="HTTP" />
          <Group label="this box · RTX PRO 6000 Blackwell · 96 GB" className="flex-1">
            <div className="flex flex-col items-stretch lg:flex-row lg:items-center">
              <Node title="Next.js 16" sub="web/ · pages + proxy" tag=":3000" className="lg:w-52">
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
                <Node title="EmbeddingGemma 2" sub="in-process · bf16 · ~2.6 GB VRAM" accent="var(--series-1)" tag="740M">
                  <div className="text-xs">query + corpus embeddings, 768d</div>
                </Node>
                <Node title="Vector index" sub="numpy · brute-force cosine" accent="var(--series-3)" tag={`${EMBED_VIEWS.length}×${seg}×768`}>
                  <div className="text-xs">data/index/&#123;view&#125;.npy · {bytes(perView768)} per view</div>
                </Node>
                <Node title="vLLM · Gemma 4 12B" sub="QAT w4a16 + MTP drafter · serve/ venv" accent="var(--series-5)" tag=":8001">
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
        blurb="uv run vrag build. Each stage is idempotent and writes plain files under data/, so any step can be re-run on its own."
      >
        <div className="flex flex-col items-stretch xl:flex-row xl:items-stretch">
          <Node title="Source files" sub="sams-videos/*.mp4" tag="input" className="xl:w-44">
            <div>{vids} creator exports</div>
            <div className="text-xs text-muted">1080p60, ~1 GB each</div>
          </Node>
          <Arrow />
          <Node title="ingest" sub="vrag/ingest.py" tag="ffmpeg" className="xl:flex-1">
            <div>480p NVENC proxy (faststart)</div>
            <div>match to upload by duration (YouTube rounds up)</div>
            <div className="text-xs text-muted">→ video.mp4 · thumb.jpg · meta.json</div>
          </Node>
          <Arrow />
          <Node title="transcribe" sub="vrag/transcribe.py" tag="gemma 4" accent="var(--series-5)" className="xl:flex-1">
            <div>Gemma 4 12B via vLLM (audio in)</div>
            <div>cut at pauses into ≤28s chunks, pad to 30s</div>
            <div className="text-xs text-muted">→ transcript.gemma.json · Whisper kept for comparison</div>
          </Node>
          <Arrow />
          <Node title="segment" sub="vrag/segment.py" tag="~30s" className="xl:flex-1">
            <div>pack cues into ~30s windows</div>
            <div>never cut mid-sentence</div>
            <div className="text-xs text-muted">→ NNN.mp4 · NNN.wav · NNN.jpg</div>
          </Node>
          <Arrow />
          <Node title="embed" sub="vrag/embed.py" tag="5 views" className="xl:flex-1">
            <div>{seg} segments × 5 views</div>
            <div>bf16, unit-norm, 768d</div>
            <div className="text-xs text-muted">→ &#123;view&#125;.npy · manifest.json</div>
          </Node>
        </div>
      </Section>

      {/* 3. Embedding views */}
      <Section
        n={3}
        title="One segment, five embeddings"
        blurb="Every segment's media goes through EmbeddingGemma 2 five different ways into the same 768d space, so one text query can be compared against any of them. Hybrid adds a sixth retrieval mode by fusing rankings instead of vectors."
      >
        <div className="grid gap-4 lg:grid-cols-[260px_auto_1fr] lg:gap-0">
          <Node title="Segment 2RA7jWJvQ1U_006" sub="Which is The Best Qwen3.8-27B? · 3:20–3:57">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/media/2RA7jWJvQ1U/segments/006.jpg" alt="" className="mt-1 aspect-video w-full rounded-md bg-black object-cover" />
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
        blurb="Search stops after step 4. Ask continues: the retrieved clips themselves (not just their text) go to Gemma 4, which answers with citations the UI turns into playable clips."
      >
        <div className="flex flex-col items-stretch xl:flex-row xl:items-stretch">
          <Node title="1 · Question" sub="text, or an image for screenshot search" className="xl:flex-1">
            <div className="text-xs">“what did Sam think about 3-bit models for coding?”</div>
          </Node>
          <Arrow />
          <Node title="2 · Embed query" sub="EmbeddingGemma 2" accent="var(--series-1)" tag={exp ? `${exp.query_embed_ms.toFixed(0)} ms` : undefined} className="xl:flex-1">
            <div>
              prefix <Code>task: search result | query:</Code>
            </div>
            <div className="text-xs text-muted">→ 768d unit vector</div>
          </Node>
          <Arrow />
          <Node title="3 · Truncate" sub="Matryoshka" tag="768/512/256/128" className="xl:flex-1">
            <div>keep first d dims of query and corpus</div>
            <div>re-normalise both</div>
          </Node>
          <Arrow />
          <Node title="4 · Cosine top-k" sub="matmul over one view" accent="var(--series-3)" tag="<1 ms" className="xl:flex-1">
            <div>{seg} scores per query</div>
            <div className="text-xs text-muted">hybrid: RRF over 3 rankings</div>
          </Node>
          <Arrow />
          <Node title="5 · Gemma 4 watches" sub="vLLM, k clips" accent="var(--series-5)" tag="~4–5 s" className="xl:flex-1">
            <div>per clip: transcript + frames</div>
            <div className="text-xs text-muted">(+ audio optional) · ~10k prompt tokens</div>
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
        blurb="Only 768d vectors are stored. Smaller sizes are prefixes of the same vector, so every dim can be compared on identical data with no re-embedding."
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
        blurb="Gemma 4 doubles as the benchmark author: it watches sampled segments and writes queries, so every query has a known source segment to score against."
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
  ingest.py      sams-videos → 480p proxy + meta
  transcribe.py  Gemma 4 / Whisper → transcripts
  segment.py     ~30s windows + clip/wav/jpg
  embedder.py    EmbeddingGemma 2 + view inputs
  embed.py       → data/index/{view}.npy
  index.py       cosine, MRL truncate, RRF
  rag.py         retrieve → Gemma 4 → answer
  evalset.py     synthetic spoken/visual queries
  experiments.py view × dim metrics grid
  api.py         FastAPI for the site
serve/           vLLM env + serve.sh / stop.sh
web/             this site
scripts/dev.sh   start everything`}</pre>
        </div>
      </Section>
    </div>
  );
}
