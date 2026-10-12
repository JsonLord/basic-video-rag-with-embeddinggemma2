"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { getJSON, type Stats, type VideoMeta } from "@/lib/api";
import { bytes, compact, fmtDuration } from "@/lib/format";
import { VIEW_INFO, VIEW_ORDER } from "@/lib/views";
import { ViewSwatch } from "@/components/Controls";

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="text-xs text-muted">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {sub && <div className="mt-0.5 text-xs text-ink-2">{sub}</div>}
    </div>
  );
}

export function Library() {
  const [videos, setVideos] = useState<VideoMeta[] | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getJSON<VideoMeta[]>("/api/videos").then(setVideos).catch((e) => setError(String(e)));
    getJSON<Stats>("/api/stats").then(setStats).catch(() => {});
  }, []);

  if (error) return <p className="text-ink-2">Backend unavailable ({error}). Start it with <code>uv run vrag api</code>.</p>;

  const s768 = stats?.storage.find((s) => s.dim === 768)?.bytes_per_view ?? 0;
  const s128 = stats?.storage.find((s) => s.dim === 128)?.bytes_per_view ?? 0;

  return (
    <div className="space-y-8">
      <section>
        <h1 className="text-2xl font-semibold">Library</h1>
        <p className="mt-1 max-w-3xl text-sm text-ink-2">
          The latest uploads, cut into ~30s segments. Every segment is embedded five ways by EmbeddingGemma 2 (transcript, a
          keyframe, the frames, the raw audio, and all three fused) into one shared 768d space, so a text query can land on any of them.
        </p>
      </section>

      {stats && (
        <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Tile label="Videos" value={String(stats.videos ?? videos?.length ?? "–")} sub={fmtDuration(stats.total_duration_s) + " of footage"} />
          <Tile label="Segments" value={String(stats.segments ?? "–")} sub={`${stats.views.length} retrieval views`} />
          <Tile label="Vectors" value={compact((stats.segments ?? 0) * Object.keys(stats.views_built ?? {}).length)} sub="segments × embedding views" />
          <Tile label="Index size per view" value={bytes(s768)} sub={`${bytes(s128)} at 128d (MRL)`} />
        </section>
      )}

      {stats?.views_built && (
        <section className="rounded-xl border border-line bg-surface p-4">
          <h2 className="text-sm font-medium">Embedding views</h2>
          <div className="mt-3 grid gap-x-6 gap-y-2 text-sm md:grid-cols-2">
            {VIEW_ORDER.filter((v) => stats.views.includes(v)).map((v) => {
              const b = stats.views_built?.[v];
              return (
                <div key={v} className="flex items-center gap-2">
                  <ViewSwatch view={v} />
                  <span className="w-14 font-medium">{VIEW_INFO[v].label}</span>
                  <span className="flex-1 text-ink-2">{stats.view_descriptions[v]}</span>
                  {b && <span className="text-xs text-muted tabular">{b.ms_per_segment} ms/seg</span>}
                </div>
              );
            })}
          </div>
        </section>
      )}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {(videos ?? []).map((v) => (
          <Link key={v.id} href={`/videos/${v.id}`} className="group overflow-hidden rounded-xl border border-line bg-surface transition-colors hover:bg-surface-2">
            <div className="relative">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={v.thumb} alt="" className="aspect-video w-full object-cover" loading="lazy" />
              <span className="absolute bottom-2 right-2 rounded bg-black/80 px-1.5 py-0.5 text-xs tabular">{fmtDuration(v.duration)}</span>
            </div>
            <div className="space-y-1 p-3">
              <div className="line-clamp-2 text-sm font-medium">{v.title}</div>
              <div className="flex flex-wrap gap-x-3 text-xs text-muted">
                <span>{v.num_segments} segments</span>
                {v.view_count != null && <span>{compact(v.view_count)} views</span>}
                {!v.youtube_id && <span>not matched to an upload</span>}
              </div>
            </div>
          </Link>
        ))}
        {!videos && <p className="text-sm text-muted">Loading…</p>}
      </section>
    </div>
  );
}
