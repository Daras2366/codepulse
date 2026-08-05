import { useRef, useState } from "react";
import { Download } from "lucide-react";
import {
  Brush,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipProps,
  XAxis,
  YAxis,
} from "recharts";

import { ChipToggle, Panel } from "@/components/ui-kit/Panel";
import { ActionButton, ChartSkeleton, EmptyState } from "@/components/ui-kit/motion";
import { exportChartAsPng } from "@/lib/export-chart";
import { platforms, ratingSeries } from "@/lib/mock-data";

const ranges = [
  { key: "7D", label: "7D", slice: 2 },
  { key: "30D", label: "30D", slice: 3 },
  { key: "90D", label: "90D", slice: 4 },
  { key: "1Y", label: "1Y", slice: 10 },
  { key: "All", label: "All", slice: 10 },
];

function ChartTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  const sorted = [...payload].sort((a, b) => (b.value ?? 0) - (a.value ?? 0));
  return (
    <div className="surface-card px-4 py-3">
      <p className="text-label uppercase text-subtle">{label}</p>
      <div className="mt-2 space-y-1.5">
        {sorted.map((p) => (
          <div key={p.dataKey} className="flex items-center gap-2.5">
            <span className="h-2 w-2 rounded-full" style={{ background: p.stroke }} />
            <span className="text-caption text-muted-foreground">{p.name}</span>
            <span className="text-caption ml-auto font-semibold text-foreground">{p.value}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function RatingChart({ compact = false }: { compact?: boolean }) {
  const [range, setRange] = useState("1Y");
  const [active, setActive] = useState<string[]>(platforms.map((p) => p.key));
  const [loading, setLoading] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);
  const chartRef = useRef<HTMLDivElement | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const slice = ranges.find((r) => r.key === range)?.slice ?? 10;
  const data = ratingSeries.slice(ratingSeries.length - slice);
  const height = compact ? 260 : 360;
  const shown = platforms.filter((p) => active.includes(p.key));

  function changeRange(key: string) {
    setRange(key);
    setLoading(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setLoading(false), 420);
  }

  return (
    <Panel
      title="Rating progress"
      caption="Contest rating across all tracked platforms"
      action={
        <div className="flex flex-wrap items-center gap-2">
          <ChipToggle
            options={ranges.map((r) => ({ key: r.key, label: r.label }))}
            value={[range]}
            onChange={changeRange}
          />
          <ActionButton
            variant="ghost"
            className="px-4 py-1.5"
            aria-label="Export chart as image"
            onClick={() => exportChartAsPng(chartRef.current, "codepulse-rating-progress")}
          >
            <Download className="h-3.5 w-3.5" strokeWidth={1.8} />
            Export
          </ActionButton>
        </div>
      }
    >
      <ChipToggle
        className="mb-6"
        options={platforms.map((p) => ({ key: p.key, label: p.name }))}
        value={active}
        onChange={(key) =>
          setActive((prev) => (prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]))
        }
      />

      {loading ? (
        <ChartSkeleton height={height} />
      ) : shown.length === 0 ? (
        <div style={{ minHeight: height }} className="flex items-center">
          <EmptyState
            title="No platforms selected"
            description="Turn a platform back on above to plot its rating curve."
            action={
              <ActionButton onClick={() => setActive(platforms.map((p) => p.key))}>
                Show all
              </ActionButton>
            }
          />
        </div>
      ) : (
        <div ref={chartRef} style={{ height, width: "100%" }} className="min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={data}
              margin={{ top: 8, right: 8, left: -18, bottom: compact ? 0 : 4 }}
            >
              <CartesianGrid stroke="var(--border)" strokeDasharray="4 6" vertical={false} />
              <XAxis
                dataKey="month"
                tickLine={false}
                axisLine={false}
                tick={{ fill: "var(--subtle)", fontSize: 12 }}
                dy={10}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                width={52}
                tick={{ fill: "var(--subtle)", fontSize: 12 }}
                domain={["dataMin - 120", "dataMax + 80"]}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--border)" }} />
              {shown.map((p) => (
                <Line
                  key={p.key}
                  type="monotone"
                  dataKey={p.key}
                  name={p.name}
                  stroke={p.stroke}
                  strokeWidth={hovered === p.key ? 3.5 : 2.5}
                  strokeOpacity={hovered && hovered !== p.key ? 0.35 : 1}
                  dot={false}
                  activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--card)" }}
                  animationDuration={900}
                  animationEasing="ease-out"
                  onMouseEnter={() => setHovered(p.key)}
                  onMouseLeave={() => setHovered(null)}
                />
              ))}
              {!compact && (
                <Brush
                  dataKey="month"
                  height={26}
                  travellerWidth={10}
                  stroke="var(--border)"
                  fill="var(--muted)"
                />
              )}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
