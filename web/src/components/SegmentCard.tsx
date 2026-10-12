"use client";

import type { Hit } from "@/lib/api";
import { fmtTs } from "@/lib/format";

export function SegmentCard({
  hit,
  onPlay,
  highlight,
  compact = false,
  badge,
}: {
  hit: Hit;
  onPlay: (h: Hit) => void;
  highlight?: boolean;
  compact?: boolean;
  badge?: React.ReactNode;
}) {
  return (
    <button
      onClick={() => onPlay(hit)}
      className={`group flex w-full gap-3 rounded-lg border bg-surface p-2 text-left transition-colors hover:bg-surface-2 ${
        highlight ? "border-accent" : "border-line"
      }`}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={hit.frame}
        alt=""
        className={`${compact ? "h-14 w-24" : "h-20 w-36"} shrink-0 rounded-md bg-black object-cover`}
        loading="lazy"
      />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-xs text-muted tabular">
          <span className="font-medium text-ink-2">#{hit.rank}</span>
          <span>
            {fmtTs(hit.start)}–{fmtTs(hit.end)}
          </span>
          <span className="ml-auto">{hit.score < 1 ? hit.score.toFixed(3) : hit.score.toFixed(4)}</span>
          {badge}
        </div>
        <div className="truncate text-sm font-medium">{hit.title}</div>
        {!compact && <p className="line-clamp-2 text-xs text-ink-2">{hit.text}</p>}
      </div>
    </button>
  );
}
