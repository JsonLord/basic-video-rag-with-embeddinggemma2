"use client";
import {AccessToken} from "@/components/AccessToken";

import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import {
  getJSON,
  qs,
  type CompareResponse,
  type CompareViewsResponse,
  type Hit,
  type SearchResponse,
  type View,
} from "@/lib/api";
import { bytes, pct } from "@/lib/format";
import { VIEW_INFO } from "@/lib/views";
import { ClipPlayer, type ClipRef } from "@/components/ClipPlayer";
import { DimPicker, Segmented, ViewPicker, ViewSwatch } from "@/components/Controls";
import { SegmentCard } from "@/components/SegmentCard";

type Mode = "single" | "dims" | "views";
const MODES: readonly Mode[] = ["single", "dims", "views"];
const MODE_LABEL: Record<Mode, string> = { single: "Single", dims: "Compare dims", views: "Compare views" };

const EXAMPLES = [
  "running a model locally on a laptop with no cloud bill",
  "a slide with a benchmark comparison table",
  "speaker diarization who said what",
  "a terminal running a coding agent",
  "voice cloning demo",
];

export function SearchView() {
  const router = useRouter();
  const params = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const [mode, setMode] = useState<Mode>((params.get("mode") as Mode) ?? "single");
  const [view, setView] = useState<View>((params.get("view") as View) ?? "text");
  const [dim, setDim] = useState(Number(params.get("dim") ?? 768));
  const [single, setSingle] = useState<SearchResponse | null>(null);
  const [dims, setDims] = useState<CompareResponse | null>(null);
  const [views, setViews] = useState<CompareViewsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clip, setClip] = useState<ClipRef | null>(null);
  const [imageName, setImageName] = useState<string | null>(null);

  const run = useCallback(
    async (query: string, o: { mode?: Mode; view?: View; dim?: number } = {}) => {
      const { mode: m = mode, view: v = view, dim: d = dim } = o;
      if (!query.trim()) return;
      setLoading(true);
      setError(null);
      setImageName(null);
      router.replace(`/search?${qs({ q: query, mode: m, view: v, dim: d })}`, { scroll: false });
      try {
        if (m === "single") setSingle(await getJSON(`/api/search?${qs({ q: query, view: v, dim: d, k: 10 })}`));
        if (m === "dims") setDims(await getJSON(`/api/compare?${qs({ q: query, view: v, k: 6 })}`));
        if (m === "views") setViews(await getJSON(`/api/compare-views?${qs({ q: query, dim: d, k: 5 })}`));
      } catch (e) {
        setError(String(e));
      } finally {
        setLoading(false);
      }
    },
    [mode, view, dim, router],
  );

  // Changing a setting re-runs the current text query with the new setting.
  const update = (o: { mode?: Mode; view?: View; dim?: number }) => {
    if (o.mode) setMode(o.mode);
    if (o.view) setView(o.view);
    if (o.dim) setDim(o.dim);
    if (q.trim() && !imageName) run(q, o);
  };

  // Deep link: /search?q=... runs on first load.
  const initial = params.get("q");
  useEffect(() => {
    // Syncing from the URL (an external source) on mount is the intended use of an effect here.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (initial) run(initial);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const searchImage = async (file: File) => {
    setLoading(true);
    setError(null);
    setMode("single");
    setImageName(file.name);
    const fd = new FormData();
    fd.append("file", file);
    try {
      setSingle(await getJSON(`/api/search/image?${qs({ view, dim, k: 10 })}`, { method: "POST", body: fd }));
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const play = (h: Hit) => setClip(h);

  return (
    <div className="space-y-6">
      <section>
        <h1 className="text-2xl font-semibold">Search</h1><AccessToken/>
        <p className="mt-1 max-w-3xl text-sm text-ink-2">
          Text queries are embedded with the <code>SearchQuery</code> prefix and scored by cosine similarity against every segment.
          Smaller Matryoshka dims are the first <em>n</em> dimensions of the same vectors, re-normalised.
        </p>
      </section>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(q);
        }}
        className="flex gap-2"
      >
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Describe a moment: something said, shown on screen, or both"
          className="flex-1 rounded-lg border border-line bg-surface px-4 py-2.5 outline-none focus:border-accent"
        />
        <button className="rounded-lg bg-accent px-5 py-2.5 font-medium text-white disabled:opacity-60" disabled={loading}>
          {loading ? "Searching…" : "Search"}
        </button>
        <label className="cursor-pointer rounded-lg border border-line px-4 py-2.5 text-sm text-ink-2 hover:text-ink" title="Query by image: find segments that look like a screenshot">
          Image…
          <input type="file" accept="image/*" className="hidden" onChange={(e) => e.target.files?.[0] && searchImage(e.target.files[0])} />
        </label>
      </form>

      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <Segmented label="Mode" value={mode} options={MODES} onChange={(m) => update({ mode: m })} render={(m) => MODE_LABEL[m]} />
        {mode !== "views" && <ViewPicker value={view} onChange={(v) => update({ view: v })} />}
        {mode !== "dims" && <DimPicker value={dim} onChange={(d) => update({ dim: d })} />}
      </div>

      {!single && !dims && !views && (
        <div className="flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => {
                setQ(ex);
                run(ex);
              }}
              className="rounded-full border border-line px-3 py-1 text-sm text-ink-2 hover:text-ink"
            >
              {ex}
            </button>
          ))}
        </div>
      )}

      {error && <p className="text-sm text-[#e66767]">{error}</p>}

      <div className={loading ? "opacity-50 transition-opacity" : ""}>
        {mode === "single" && single && (
          <section className="space-y-3">
            <div className="text-xs text-muted tabular">
              {imageName ? `Image query: ${imageName}` : `"${single.query}"`} · {VIEW_INFO[single.view].label} @ {single.dim}d
              {single.timing && ` · embed ${single.timing.embed_ms} ms · search ${single.timing.search_ms} ms`}
            </div>
            <div className="grid gap-2 md:grid-cols-2">
              {single.hits.map((h) => (
                <SegmentCard key={h.id} hit={h} onPlay={play} />
              ))}
            </div>
          </section>
        )}

        {mode === "dims" && dims && (
          <section className="space-y-3">
            <p className="text-xs text-muted">
              Same query, same {VIEW_INFO[dims.view].label.toLowerCase()} vectors, truncated to each Matryoshka size. Highlighted cards are
              also in the 768d top-{dims.k}.
            </p>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              {dims.columns.map((col) => {
                const base = new Set(dims.columns[0].hits.map((h) => h.id));
                return (
                  <div key={col.dim} className="space-y-2">
                    <div className="rounded-lg border border-line bg-surface p-3">
                      <div className="flex items-baseline justify-between">
                        <span className="text-lg font-semibold">{col.dim}d</span>
                        <span className="text-xs text-muted">{bytes(col.bytes_per_view)} / view</span>
                      </div>
                      <div className="mt-1 text-xs text-ink-2">
                        {pct(col.overlap_with_768)} overlap with 768d · top-1 {col.top1_matches_768 ? "same" : "differs"}
                      </div>
                    </div>
                    {col.hits.map((h) => (
                      <SegmentCard key={h.id} hit={h} onPlay={play} compact highlight={col.dim !== 768 && base.has(h.id)} />
                    ))}
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {mode === "views" && views && (
          <section className="space-y-3">
            <p className="text-xs text-muted">Same query against each embedding view at {views.dim}d.</p>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {views.columns.map((col) => (
                <div key={col.view} className="space-y-2">
                  <div className="flex items-center gap-2 rounded-lg border border-line bg-surface p-3">
                    <ViewSwatch view={col.view} />
                    <span className="font-medium">{VIEW_INFO[col.view].label}</span>
                    <span className="text-xs text-muted">{VIEW_INFO[col.view].blurb}</span>
                  </div>
                  {col.hits.map((h) => (
                    <SegmentCard key={h.id} hit={h} onPlay={play} compact />
                  ))}
                </div>
              ))}
            </div>
          </section>
        )}
      </div>

      <ClipPlayer clip={clip} onClose={() => setClip(null)} />
    </div>
  );
}
