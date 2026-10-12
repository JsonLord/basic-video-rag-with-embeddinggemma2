"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { View } from "@/lib/api";
import { VIEW_HEX, VIEW_INFO } from "@/lib/views";

export interface Point {
  dim: number;
  [view: string]: number;
}

function ChartTooltip({ active, payload, label, metric }: { active?: boolean; payload?: { dataKey: string; value: number; color: string }[]; label?: number; metric: string }) {
  if (!active || !payload?.length) return null;
  const rows = [...payload].sort((a, b) => b.value - a.value);
  return (
    <div className="rounded-lg border border-line bg-surface-2 px-3 py-2 text-xs shadow-lg">
      <div className="mb-1 text-muted">
        {label}d · {metric}
      </div>
      {rows.map((r) => (
        <div key={r.dataKey} className="flex items-center gap-2">
          <span className="inline-block h-0.5 w-3 rounded" style={{ background: r.color }} />
          <span className="w-10 font-semibold text-ink tabular">{r.value.toFixed(3)}</span>
          <span className="text-ink-2">{VIEW_INFO[r.dataKey as View].label}</span>
        </div>
      ))}
    </div>
  );
}

/** One line per embedding view; x = Matryoshka dimension. Legend is rendered by the caller. */
export function MetricByDimChart({ data, views, metric, highlight }: { data: Point[]; views: View[]; metric: string; highlight?: View | null }) {
  return (
    <div className="h-[340px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 12, right: 24, bottom: 8, left: 0 }}>
          <CartesianGrid stroke="#2c2c2a" strokeWidth={1} vertical={false} />
          <XAxis
            dataKey="dim"
            tickFormatter={(d) => `${d}d`}
            stroke="#383835"
            tick={{ fill: "#898781", fontSize: 12 }}
            tickLine={false}
            padding={{ left: 24, right: 24 }}
          />
          <YAxis
            domain={[0, 1]}
            ticks={[0, 0.25, 0.5, 0.75, 1]}
            tickFormatter={(v) => v.toFixed(2)}
            stroke="#383835"
            tick={{ fill: "#898781", fontSize: 12 }}
            tickLine={false}
            axisLine={false}
            width={44}
          />
          <Tooltip content={<ChartTooltip metric={metric} />} cursor={{ stroke: "#c3c2b7", strokeWidth: 1 }} />
          {views.map((v) => (
            <Line
              key={v}
              dataKey={v}
              stroke={VIEW_HEX[v]}
              strokeWidth={2}
              strokeOpacity={highlight && highlight !== v ? 0.2 : 1}
              strokeLinecap="round"
              strokeLinejoin="round"
              dot={{ r: 4, fill: VIEW_HEX[v], stroke: "#1a1a19", strokeWidth: 2, fillOpacity: highlight && highlight !== v ? 0.2 : 1 }}
              activeDot={{ r: 5, stroke: "#1a1a19", strokeWidth: 2 }}
              isAnimationActive={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
