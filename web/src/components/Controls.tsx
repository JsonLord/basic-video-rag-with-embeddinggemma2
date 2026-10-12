"use client";

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
      <div role="radiogroup" aria-label={ariaLabel ?? label} className="flex rounded-lg border border-line bg-surface p-0.5">
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
  return (
    <Segmented
      label="View"
      value={value}
      options={views}
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
  return <Segmented label="Dims" value={value} options={DIMS as readonly number[]} onChange={onChange} render={(d) => `${d}d`} />;
}
