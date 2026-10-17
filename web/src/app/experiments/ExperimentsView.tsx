"use client";

import { useEffect, useMemo, useState } from "react";
import { getJSON, type Experiments, type GridRow, type PerQuery, type View } from "@/lib/api";
import { bytes, fmtTs, pct } from "@/lib/format";
import { VIEW_INFO, VIEW_ORDER } from "@/lib/views";
import { ClipPlayer, type ClipRef } from "@/components/ClipPlayer";
import { Segmented, ViewSwatch } from "@/components/Controls";
import { Heatmap } from "@/components/charts/Heatmap";
import { MetricByDimChart, type Point } from "@/components/charts/MetricByDimChart";

const METRICS = ["recall@1", "recall@5", "recall@10", "mrr@10", "neighbor_recall@5", "video_hit@1"] as const;
type Metric = (typeof METRICS)[number];
const METRIC_HELP: Record<Metric, string> = {
  "recall@1": "Exact source segment ranked first",
  "recall@5": "Exact source segment in the top 5",
  "recall@10": "Exact source segment in the top 10",
  "mrr@10": "Mean reciprocal rank of the source segment (0 if outside top 10)",
  "neighbor_recall@5": "Source segment or an adjacent one (±30s) in the top 5",
  "video_hit@1": "Top result comes from the right video",
};
const QTYPES = ["all", "spoken", "visual"] as const;
type QType = (typeof QTYPES)[number];

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-2">{sub}</div>}
    </div>
  );
}

function rankCell(rank: number | undefined) {
  if (rank == null) return <td />;
  const good = rank === 1 ? "bg-[#1c5cab] text-white" : rank <= 5 ? "bg-[#104281] text-white" : rank <= 10 ? "bg-surface-2 text-ink-2" : "text-muted";
  return <td className={`rounded px-2 py-1 text-right text-xs tabular ${good}`}>{rank > 99 ? "99+" : rank}</td>;
}

export function ExperimentsView() {
  const [data, setData] = useState<Experiments | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [metric, setMetric] = useState<Metric>("recall@5");
  const [qtype, setQtype] = useState<QType>("all");
  const [heatMode, setHeatMode] = useState<"absolute" | "retained">("absolute");
  const [hoverView, setHoverView] = useState<View | null>(null);
  const [tableDim, setTableDim] = useState(768);
  const [filter, setFilter] = useState("");
  const [clip, setClip] = useState<ClipRef | null>(null);
  const [transcripts, setTranscripts] = useState<string | null>(null);

  useEffect(() => {
    getJSON<Experiments>(`/api/experiments${transcripts ? `?transcripts=${transcripts}` : ""}`)
      .then(setData)
      .catch((e) => setError(String(e)));
  }, [transcripts]);

  const views = useMemo(() => VIEW_ORDER.filter((v) => data?.views.includes(v)), [data]);
  const dimsAsc = useMemo(() => [...(data?.dims ?? [])].sort((a, b) => a - b), [data]);
  const cell = useMemo(() => {
    const m = new Map<string, GridRow>();
    data?.grid.forEach((g) => m.set(`${g.view}|${g.dim}|${g.query_type}`, g));
    return (view: View, dim: number) => m.get(`${view}|${dim}|${qtype}`);
  }, [data, qtype]);

  if (error) return <p className="text-sm text-ink-2">{error}</p>;
  if (!data) return <p className="text-sm text-muted">Loading…</p>;

  const points: Point[] = dimsAsc.map((d) => ({ dim: d, ...Object.fromEntries(views.map((v) => [v, cell(v, d)?.[metric] ?? 0])) }));
  const best = data.grid.filter((g) => g.query_type === qtype).sort((a, b) => b[metric] - a[metric])[0];
  const best768 = (v: View) => cell(v, 768)?.[metric] ?? 0;
  const fused256 = cell("fused", 256)?.[metric];
  const fused768 = best768("fused");
  const bestView = views.reduce((a, v) => (best768(v) > best768(a) ? v : a), views[0]);

  const queries = data.per_query.filter(
    (q) => (qtype === "all" || q.type === qtype) && (!filter || q.query.toLowerCase().includes(filter.toLowerCase())),
  );

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl font-semibold">Experiments</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-2">
          {data.model} · {data.num_queries} queries across {data.num_segments} segments. Historical results retain their original model labels. Synthetic fixtures illustrate the interface and are not measured retrieval quality. Run {new Date(data.created_at).toLocaleString()}.
        </p>
      </section>

      {/* Filters: one row, scope everything below */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-xl border border-line bg-surface p-3">
        <Segmented label="Metric" value={metric} options={METRICS} onChange={setMetric} />
        <Segmented label="Queries" value={qtype} options={QTYPES} onChange={setQtype} />
        {data.variants && data.variants.length > 1 && data.transcripts && (
          <Segmented
            label="Transcripts"
            value={data.transcripts}
            options={data.variants}
            onChange={setTranscripts}
            render={(e) => (e === "gemma" ? "Gemma 4" : e === "whisper" ? "Whisper" : e)}
          />
        )}
        <span className="text-xs text-muted">{METRIC_HELP[metric]}</span>
      </div>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile label={`Best config · ${metric}`} value={best ? best[metric].toFixed(3) : "–"} sub={best ? `${VIEW_INFO[best.view].label} @ ${best.dim}d` : ""} />
        <Tile label="Best view at 768d" value={VIEW_INFO[bestView].label} sub={`${best768(bestView).toFixed(3)} ${metric}`} />
        <Tile
          label="Fused at 256d keeps"
          value={fused256 != null && fused768 ? pct(fused256 / fused768) : "–"}
          sub={`of 768d ${metric} at 1/3 the storage`}
        />
        <Tile label="Query embed" value={`${data.query_embed_ms.toFixed(1)} ms`} sub="per query (batched, bf16)" />
      </section>

      <section className="rounded-xl border border-line bg-surface p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-medium">
            {metric} by Matryoshka dimension <span className="text-sm font-normal text-muted">· {qtype} queries</span>
          </h2>
        </div>
        {/* Legend (always present for >1 series); hover a key to emphasise its line. */}
        <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1">
          {views.map((v) => (
            <button
              key={v}
              onMouseEnter={() => setHoverView(v)}
              onMouseLeave={() => setHoverView(null)}
              onFocus={() => setHoverView(v)}
              onBlur={() => setHoverView(null)}
              className="flex items-center gap-1.5 text-sm text-ink-2"
            >
              <span className="inline-block h-0.5 w-4 rounded" style={{ background: VIEW_INFO[v].color }} />
              {VIEW_INFO[v].label}
              <span className="text-xs text-muted">{VIEW_INFO[v].blurb}</span>
            </button>
          ))}
        </div>
        <MetricByDimChart data={points} views={views} metric={metric} highlight={hoverView} />
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_380px]">
        <div className="rounded-xl border border-line bg-surface p-5">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-medium">
              {heatMode === "absolute" ? metric : `% of 768d ${metric} retained`}{" "}
              <span className="text-sm font-normal text-muted">· {qtype} queries</span>
            </h2>
            <Segmented label="Show" value={heatMode} options={["absolute", "retained"] as const} onChange={setHeatMode} />
          </div>
          <Heatmap
            views={views}
            dims={[...dimsAsc].reverse()}
            value={(v, d) => {
              const x = cell(v, d)?.[metric];
              if (x == null) return undefined;
              if (heatMode === "absolute") return x;
              const base = cell(v, 768)?.[metric];
              return base ? x / base : undefined;
            }}
            format={(x) => (heatMode === "absolute" ? x.toFixed(3) : pct(x))}
          />
        </div>
        <div className="rounded-xl border border-line bg-surface p-5">
          <h2 className="mb-3 font-medium">Storage (float32)</h2>
          <table className="w-full text-sm">
            <thead>
              <tr className="text-xs text-muted">
                <th className="pb-2 text-left font-normal">Dims</th>
                <th className="pb-2 text-right font-normal">Per vector</th>
                <th className="pb-2 text-right font-normal">Per view</th>
                <th className="pb-2 text-right font-normal">All views</th>
              </tr>
            </thead>
            <tbody className="tabular">
              {data.storage.map((s) => (
                <tr key={s.dim} className="border-t border-line">
                  <td className="py-2">
                    {s.dim}d <span className="text-xs text-muted">{s.dim === 768 ? "" : `÷${(768 / s.dim).toFixed(1)}`}</span>
                  </td>
                  <td className="py-2 text-right">{bytes(s.bytes_per_vector)}</td>
                  <td className="py-2 text-right">{bytes(s.bytes_per_view)}</td>
                  <td className="py-2 text-right">{bytes(s.bytes_all_views)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-muted">
            Tiny at this corpus size; the ratios are what matter at scale. Model card: ~lossless to 256d, 128d drops sharply for
            multimodal inputs.
          </p>
        </div>
      </section>

      <section className="rounded-xl border border-line bg-surface p-5">
        <div className="mb-3 flex flex-wrap items-center gap-4">
          <h2 className="font-medium">Per-query ranks</h2>
          <Segmented label="Dims" value={tableDim} options={data.dims} onChange={setTableDim} render={(d) => `${d}d`} />
          <input
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter queries…"
            className="ml-auto w-64 rounded-lg border border-line bg-page px-3 py-1.5 text-sm outline-none focus:border-accent"
          />
        </div>
        <p className="mb-3 text-xs text-muted">Rank of the source segment for each view (1 = perfect). Click a row to play the source segment.</p>
        <div className="max-h-[560px] overflow-y-auto">
          <table className="w-full border-separate text-sm" style={{ borderSpacing: "2px" }}>
            <thead className="sticky top-0 bg-surface">
              <tr className="text-xs text-muted">
                <th className="py-1 text-left font-normal">Query</th>
                <th className="py-1 text-left font-normal">Type</th>
                {views.map((v) => (
                  <th key={v} className="py-1 text-right font-normal">
                    <span className="inline-flex items-center gap-1">
                      <ViewSwatch view={v} />
                      {VIEW_INFO[v].label}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {queries.map((q: PerQuery, i) => (
                <tr
                  key={i}
                  onClick={() => q.segment && setClip({ ...q.segment, text: q.evidence ? `On screen: ${q.evidence}` : undefined })}
                  className="cursor-pointer hover:bg-surface-2"
                >
                  <td className="py-1 pr-3">
                    <div>{q.query}</div>
                    {q.segment && (
                      <div className="text-xs text-muted">
                        {q.segment.title} @ {fmtTs(q.segment.start)}
                      </div>
                    )}
                  </td>
                  <td className="py-1 pr-2 text-xs text-ink-2">{q.type}</td>
                  {views.map((v) => (
                    <RankTd key={v} rank={q.ranks[`${v}@${tableDim}`]} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <ClipPlayer clip={clip} onClose={() => setClip(null)} />
    </div>
  );
}

function RankTd({ rank }: { rank?: number }) {
  return rankCell(rank);
}
