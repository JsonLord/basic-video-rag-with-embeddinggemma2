"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";
import { getJSON, qs, type Hit, type SearchResponse, type VideoDetail, type View } from "@/lib/api";
import { compact, fmtDuration, fmtTs, youtubeAt } from "@/lib/format";
import { DimPicker, Segmented, ViewPicker } from "@/components/Controls";
import { SegmentCard } from "@/components/SegmentCard";

export function VideoDetailView() {
  const { id } = useParams<{ id: string }>();
  const [error,setError]=useState("");
  const [video, setVideo] = useState<VideoDetail | null>(null);
  const [time, setTime] = useState(0);
  const [q, setQ] = useState("");
  const [view, setView] = useState<View>("text");
  const [dim, setDim] = useState(768);
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [engine, setEngine] = useState<string | null>(null);
  const player = useRef<HTMLVideoElement>(null);
  const transcriptBox = useRef<HTMLDivElement>(null);

  useEffect(() => {
    getJSON<VideoDetail>(`/api/videos/${id}`).then(setVideo).catch(e=>setError(String(e)));
  }, [id]);

  const seek = (t: number) => {
    if (!player.current) return;
    player.current.currentTime = t;
    player.current.play();
  };

  // Which engine's transcript to show: the active one unless the user picks another.
  const engines = useMemo(() => Object.keys(video?.transcripts ?? {}), [video]);
  const shownEngine = engine ?? video?.transcript_engine ?? engines[0] ?? null;
  const cues = useMemo(
    () => (shownEngine && video?.transcripts?.[shownEngine]) || video?.transcript || [],
    [video, shownEngine],
  );
  const activeSeg = useMemo(() => video?.segments.find((s) => time >= s.start && time < s.end), [video, time]);
  const activeCue = useMemo(() => cues.findIndex((c) => time >= c.start && time < c.end), [cues, time]);

  useEffect(() => {
    const el = transcriptBox.current?.querySelector<HTMLElement>(`[data-cue="${activeCue}"]`);
    if (el && transcriptBox.current) {
      const box = transcriptBox.current;
      box.scrollTo({ top: el.offsetTop - box.offsetTop - box.clientHeight / 3, behavior: "smooth" });
    }
  }, [activeCue]);

  const searchHere = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!q.trim()) return;
    const r = await getJSON<SearchResponse>(`/api/search?${qs({ q, view, dim, k: 5, video_id: id })}`);
    setHits(r.hits);
  };

  if(error)return <p role="alert">{error}</p>;
  if (!video) return <p className="text-sm text-muted">Loading…</p>;
  const yt = youtubeAt(video.webpage_url, time);

  return (
    <div className="space-y-6">
      <div className="text-sm text-muted">
        <Link href="/" className="hover:text-ink">Library</Link> / {video.title}
      </div>
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <div className="space-y-4">
          {/* Fit to the viewport: 16:9, full column width unless that would push the bottom off screen
              (10rem ≈ nav + page padding + breadcrumb). */}
          <video
            ref={player}
            src={video.video}
            controls
            autoPlay
            playsInline
            onLoadedMetadata={(e) => {
              // Browsers may refuse autoplay with sound; fall back to muted playback rather than a frozen frame.
              const el = e.currentTarget;
              el.play().catch(() => {
                el.muted = true;
                el.play().catch(() => {});
              });
            }}
            onTimeUpdate={(e) => setTime(e.currentTarget.currentTime)}
            className="mx-auto block aspect-video max-h-[calc(100svh-10rem)] w-full max-w-[calc((100svh-10rem)*16/9)] rounded-xl bg-black"
          />
          <div>
            <h1 className="text-xl font-semibold">{video.title}</h1>
            <div className="mt-1 flex flex-wrap gap-x-4 text-sm text-muted">
              <span>{fmtDuration(video.duration)}</span>
              <span>{video.num_segments} segments</span>
              {video.view_count != null && <span>{compact(video.view_count)} views</span>}
              <span>transcript: {video.transcript_source ?? "–"}</span>
              <span>source: {video.source_file}</span>
              {yt && (
                <a href={yt} target="_blank" rel="noreferrer" className="text-accent hover:underline">
                  Open on YouTube at {fmtTs(time)} ↗
                </a>
              )}
            </div>
          </div>

          <section>
            <h2 className="mb-2 text-sm font-medium">Segments</h2>
            {/* Timeline: one keyframe per indexed segment; width proportional to segment length. */}
            <div className="flex gap-0.5 overflow-x-auto pb-2">
              {video.segments.map((s) => (
                <button
                  key={s.idx}
                  onClick={() => seek(s.start)}
                  title={`${fmtTs(s.start)}–${fmtTs(s.end)}\n${s.text.slice(0, 200)}`}
                  className={`relative shrink-0 overflow-hidden rounded ${activeSeg?.idx === s.idx ? "ring-2 ring-accent" : "opacity-70 hover:opacity-100"}`}
                  style={{ width: Math.max(48, (s.end - s.start) * 2.6) }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={s.frame} alt="" className="h-12 w-full object-cover" loading="lazy" />
                  <span className="absolute bottom-0 left-0 bg-black/70 px-1 text-[10px] tabular">{fmtTs(s.start)}</span>
                </button>
              ))}
            </div>
            {activeSeg && (
              <div className="mt-2 rounded-lg border border-line bg-surface p-3 text-sm text-ink-2">
                <span className="text-xs text-muted tabular">
                  Segment {activeSeg.idx} · {fmtTs(activeSeg.start)}–{fmtTs(activeSeg.end)} ·{" "}
                </span>
                {activeSeg.text}
              </div>
            )}
          </section>

          <section className="space-y-3 rounded-xl border border-line bg-surface p-4">
            <h2 className="text-sm font-medium">Search inside this video</h2>
            <form onSubmit={searchHere} className="flex gap-2">
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="e.g. the benchmark table"
                className="flex-1 rounded-lg border border-line bg-page px-3 py-2 text-sm outline-none focus:border-accent"
              />
              <button className="rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white">Search</button>
            </form>
            <div className="flex flex-wrap gap-4">
              <ViewPicker value={view} onChange={setView} />
              <DimPicker value={dim} onChange={setDim} />
            </div>
            {hits && (
              <div className="grid gap-2">
                {hits.map((h) => (
                  <SegmentCard key={h.id} hit={h} onPlay={() => seek(h.start)} compact />
                ))}
              </div>
            )}
          </section>
        </div>

        <aside className="flex max-h-[calc(100vh-8rem)] flex-col rounded-xl border border-line bg-surface lg:sticky lg:top-20">
          <div className="flex items-center justify-between gap-2 border-b border-line px-4 py-2">
            <h2 className="text-sm font-medium">Transcript</h2>
            {engines.length > 1 && shownEngine && (
              <Segmented
                label=""
                ariaLabel="Transcript engine"
                value={shownEngine}
                options={engines}
                onChange={setEngine}
                render={(e) => (e === "gemma" ? "Gemma 4" : e === "whisper" ? "Whisper" : e)}
              />
            )}
          </div>
          <div ref={transcriptBox} className="relative flex-1 space-y-1 overflow-y-auto p-3">
            {cues.map((c, i) => (
              <button
                key={i}
                data-cue={i}
                onClick={() => seek(c.start)}
                className={`block w-full rounded px-2 py-1 text-left text-sm ${i === activeCue ? "bg-surface-2 text-ink" : "text-ink-2 hover:bg-surface-2"}`}
              >
                <span className="mr-2 text-xs text-muted tabular">{fmtTs(c.start)}</span>
                {c.text}
              </button>
            ))}
          </div>
        </aside>
      </div>
    </div>
  );
}
