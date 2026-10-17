"use client";

import { useEffect, useState } from "react";
import {getJSON, type Stats} from "@/lib/api";
import { DIMS, type View } from "@/lib/api";
import { VIEW_INFO, VIEW_ORDER } from "@/lib/views";

export function Segmented<T extends string | number>({
  value,
  options,
  onChange,
  render,
  label,
  ariaLabel,
}: {
  value: T;
  options: readonly T[];
  onChange: (v: T) => void;
  render?: (v: T) => React.ReactNode;
  label: string;
  ariaLabel?: string;
}) {
  return (
    <div className="flex items-center gap-2">
      {label && <span className="text-xs text-muted">{label}</span>}
      <div role="radiogroup" aria-label={ariaLabel ?? label} className="flex flex-wrap rounded-lg border border-line bg-surface p-0.5">
        {options.map((o) => (
          <button
            key={String(o)}
            role="radio"
            aria-checked={o === value}
            onClick={() => onChange(o)}
            className={`rounded-md px-2.5 py-1 text-sm transition-colors ${
              o === value ? "bg-surface-2 text-ink" : "text-ink-2 hover:text-ink"
            }`}
          >
            {render ? render(o) : String(o)}
          </button>
        ))}
      </div>
    </div>
  );
}

export function ViewSwatch({ view }: { view: View }) {
  return <span className="inline-block h-2 w-2 rounded-full" style={{ background: VIEW_INFO[view].color }} />;
}

export function ViewPicker({ value, onChange, views = VIEW_ORDER }: { value: View; onChange: (v: View) => void; views?: View[] }) {
  const [available,setAvailable]=useState<View[]>(views);
  useEffect(()=>{void getJSON<Stats>("/api/stats").then(s=>{setAvailable(s.views);if(s.views.length&&!s.views.includes(value))onChange(s.views[0]);}).catch(()=>{});
  // Initial capabilities are a server snapshot; manual selection remains local.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);
  return (
    <Segmented
      label="View"
      value={value}
      options={available.filter(v=>views.includes(v))}
      onChange={onChange}
      render={(v) => (
        <span className="flex items-center gap-1.5" title={VIEW_INFO[v].blurb}>
          <ViewSwatch view={v} />
          {VIEW_INFO[v].label}
        </span>
      )}
    />
  );
}

export function DimPicker({ value, onChange }: { value: number; onChange: (d: number) => void }) {
  const [dims,setDims]=useState<readonly number[]>(DIMS);
  useEffect(()=>{void getJSON<Stats>("/api/stats").then(s=>{setDims(s.dims);if(s.dims.length&&!s.dims.includes(value))onChange(s.dims[0]);}).catch(()=>{});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[]);
  return <Segmented label="Dims" value={value} options={dims} onChange={onChange} render={(d) => `${d}d`} />;
}
