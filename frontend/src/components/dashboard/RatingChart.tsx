import { useRef } from "react";
import { Download } from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipProps,
  XAxis,
  YAxis,
} from "recharts";

import type { DashboardRating } from "@/api/dashboard";
import { ActionButton, ChartSkeleton, EmptyState, ErrorState } from "@/components/ui-kit/motion";
import { Panel } from "@/components/ui-kit/Panel";
import { exportChartAsPng } from "@/lib/export-chart";
import { ratingSeries } from "@/lib/mock-data";

function ChartTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="surface-card px-4 py-3">
      <p className="text-label uppercase text-subtle">{label}</p>
      <p className="text-caption mt-2 font-semibold text-foreground">{payload[0]?.value} rating</p>
    </div>
  );
}

export function RatingChart({
  compact = false,
  rating,
  isLoading = false,
  error,
  onRetry,
}: {
  compact?: boolean;
  rating?: DashboardRating | undefined;
  isLoading?: boolean;
  error?: string | undefined;
  onRetry?: (() => void) | undefined;
}) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const height = compact ? 260 : 360;
  const data = rating
    ? rating.history.map((item) => ({
        date: new Intl.DateTimeFormat("en", { month: "short", year: "numeric" }).format(
          new Date(item.recorded_at),
        ),
        rating: item.rating,
      }))
    : ratingSeries.map((item) => ({ date: item.month, rating: item.codeforces }));
  const title = rating ? "Codeforces rating progress" : "Rating progress";
  const caption = rating
    ? "Rating changes from your synced Codeforces contests"
    : "Contest rating across all tracked platforms";

  return (
    <Panel
      title={title}
      caption={caption}
      action={
        <ActionButton
          variant="ghost"
          className="px-4 py-1.5"
          aria-label="Export chart as image"
          onClick={() => exportChartAsPng(chartRef.current, "codepulse-rating-progress")}
          disabled={isLoading || data.length === 0}
        >
          <Download className="h-3.5 w-3.5" strokeWidth={1.8} />
          Export
        </ActionButton>
      }
    >
      {isLoading ? (
        <ChartSkeleton height={height} />
      ) : error ? (
        <ErrorState description={error} onRetry={onRetry} />
      ) : data.length === 0 ? (
        <div style={{ minHeight: height }} className="flex items-center">
          <EmptyState
            title="No rating history yet"
            description="Join a rated Codeforces contest and sync your profile to see rating progress."
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
                dataKey="date"
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
              <Line
                type="monotone"
                dataKey="rating"
                name="Codeforces"
                stroke="var(--pastel-blue)"
                strokeWidth={2.5}
                dot={false}
                activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--card)" }}
                animationDuration={900}
                animationEasing="ease-out"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
