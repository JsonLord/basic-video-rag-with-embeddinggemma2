"use client";

import { useEffect, useRef } from "react";
import { fmtTs } from "@/lib/format";

export interface ClipRef {
  video_id: string;
  title: string;
  start: number;
  end: number;
  text?: string;
}

/** Modal that plays the 480p proxy from the segment start and pauses at its end. */
export function ClipPlayer({ clip, onClose }: { clip: ClipRef | null; onClose: () => void }) {
  const ref = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!clip) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6" onClick={onClose}>
      <div className="w-full max-w-4xl overflow-hidden rounded-xl border border-line bg-surface" onClick={(e) => e.stopPropagation()}>
        <video
          ref={ref}
          key={`${clip.video_id}-${clip.start}`}
          src={`/media/${clip.video_id}/video.mp4#t=${clip.start},${clip.end}`}
          controls
          autoPlay
          className="aspect-video max-h-[calc(100svh-12rem)] w-full bg-black"
        />
        <div className="flex items-start justify-between gap-4 p-4">
          <div className="min-w-0">
            <div className="text-sm font-medium">{clip.title}</div>
            <div className="text-xs text-muted tabular">
              {fmtTs(clip.start)} – {fmtTs(clip.end)}
            </div>
            {clip.text && <p className="mt-2 line-clamp-4 text-sm text-ink-2">{clip.text}</p>}
          </div>
          <button onClick={onClose} className="rounded-md border border-line px-3 py-1 text-sm text-ink-2 hover:text-ink">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
