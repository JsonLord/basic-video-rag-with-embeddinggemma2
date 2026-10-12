"use client";

import type { View } from "@/lib/api";
import { VIEW_INFO } from "@/lib/views";
import { ViewSwatch } from "@/components/Controls";

// Sequential blue ramp (dataviz reference), dark-surface direction: low values recede toward the surface.
const RAMP = ["#0d366b", "#104281", "#184f95", "#1c5cab", "#256abf", "#2a78d6", "#3987e5", "#5598e7", "#6da7ec", "#86b6ef", "#9ec5f4"];

function cellColor(t: number) {
  const i = Math.max(0, Math.min(RAMP.length - 1, Math.round(t * (RAMP.length - 1))));
  return { bg: RAMP[i], fg: i >= 7 ? "#0b0b0b" : "#ffffff" };
}

/** views x dims table; cell = value, shaded on a single-hue ramp between the table's min and max. */
export function Heatmap({
  views,
  dims,
  value,
  format,
}: {
  views: View[];
  dims: number[];
  value: (view: View, dim: number) => number | undefined;
  format: (v: number) => string;
}) {
  const all = views.flatMap((v) => dims.map((d) => value(v, d))).filter((x): x is number => x != null);
  const lo = Math.min(...all);
  const hi = Math.max(...all);
  return (
    <table className="w-full border-separate" style={{ borderSpacing: 2 }}>
      <thead>
        <tr>
          <th className="text-left text-xs font-normal text-muted">View</th>
          {dims.map((d) => (
            <th key={d} className="text-right text-xs font-normal text-muted tabular">
              {d}d
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {views.map((v) => (
          <tr key={v}>
            <td className="pr-3 text-sm">
              <span className="flex items-center gap-2">
                <ViewSwatch view={v} />
                {VIEW_INFO[v].label}
              </span>
            </td>
            {dims.map((d) => {
              const x = value(v, d);
              if (x == null) return <td key={d} />;
              const { bg, fg } = cellColor(hi > lo ? (x - lo) / (hi - lo) : 1);
              return (
                <td key={d} className="rounded px-3 py-2 text-right text-sm font-medium tabular" style={{ background: bg, color: fg }} title={`${VIEW_INFO[v].label} @ ${d}d: ${format(x)}`}>
                  {format(x)}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
