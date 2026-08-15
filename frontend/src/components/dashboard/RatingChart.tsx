import { useRef } from "react";
import { Download } from "lucide-react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  type TooltipProps,
  XAxis,
  YAxis,
} from "recharts";

import type { AnalyticsRatingProgression } from "@/api/analytics";
import type { DashboardRating } from "@/api/dashboard";
import { ActionButton, ChartSkeleton, EmptyState, ErrorState } from "@/components/ui-kit/motion";
import { Panel } from "@/components/ui-kit/Panel";
import { exportChartAsPng } from "@/lib/export-chart";

const PLATFORM_COLORS: Record<string, string> = {
  codeforces: "var(--pastel-blue)",
  leetcode: "var(--pastel-yellow)",
  codechef: "var(--pastel-green)",
  atcoder: "var(--pastel-pink)",
};

/**
 * Normalize a date from various formats to a Date object.
 * Handles:
 * - ISO datetime strings
 * - Unix timestamps in seconds
 * - Unix timestamps in milliseconds
 * - Python datetime JSON strings
 */
function normalizeDate(dateInput: string | number): Date {
  if (typeof dateInput === "number") {
    // Check if it's seconds (LeetCode uses seconds, not milliseconds)
    // If timestamp is less than year 2000 in milliseconds, it's likely seconds
    if (dateInput < 946684800000) {
      return new Date(dateInput * 1000);
    }
    return new Date(dateInput);
  }

  // String input
  const date = new Date(dateInput);
  if (!isNaN(date.getTime())) {
    return date;
  }

  // Fallback to current time if parsing fails
  return new Date();
}

/**
 * Format a date for display in charts
 */
function formatDate(dateInput: string | number): string {
  const date = normalizeDate(dateInput);
  return new Intl.DateTimeFormat("en", { month: "short", year: "numeric" }).format(date);
}

function ChartTooltip({ active, payload, label }: TooltipProps<number, string>) {
  if (!active || !payload?.length) return null;
  return (
    <div className="surface-card px-4 py-3">
      <p className="text-label uppercase text-subtle">{label}</p>
      {payload.map((entry, index) => (
        <p key={index} className="text-caption mt-1 font-semibold" style={{ color: entry.color }}>
          {entry.name}: {entry.value}
        </p>
      ))}
    </div>
  );
}

export function RatingChart({
  compact = false,
  rating,
  aggregateRating,
  platform,
  isLoading = false,
  error,
  onRetry,
}: {
  compact?: boolean;
  rating?: DashboardRating | AnalyticsRatingProgression | undefined;
  aggregateRating?: any;
  platform?: string;
  isLoading?: boolean;
  error?: string | undefined;
  onRetry?: (() => void) | undefined;
}) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const height = compact ? 260 : 360;

  let data: any[] = [];
  let lines: any[] = [];
  let legend: any = null;

  if (aggregateRating) {
    // Aggregate mode: multiple lines for each platform
    // New structure: { series: [{ platform, username, history: [{ date, rating, platform }] }] }
    const allDates = new Set<string>();
    const platformDataMap: Record<string, any> = {};

    aggregateRating.series.forEach((series: any) => {
      platformDataMap[series.platform] = series;
      series.history.forEach((item: any) => {
        allDates.add(formatDate(item.date));
      });
    });

    const sortedDates = Array.from(allDates).sort();

    data = sortedDates.map((date) => {
      const point: any = { date };
      Object.keys(platformDataMap).forEach((platform) => {
        const series = platformDataMap[platform];
        const historyItem = series.history.find((h: any) => formatDate(h.date) === date);
        point[platform] = historyItem ? historyItem.rating : null;
      });
      return point;
    });

    lines = Object.keys(platformDataMap).map((platform) => (
      <Line
        key={platform}
        type="monotone"
        dataKey={platform}
        name={platform.charAt(0).toUpperCase() + platform.slice(1)}
        stroke={PLATFORM_COLORS[platform] || "var(--pastel-blue)"}
        strokeWidth={2.5}
        dot={false}
        activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--card)" }}
        connectNulls={false}
        animationDuration={900}
        animationEasing="ease-out"
      />
    ));

    legend = (
      <Legend
        verticalAlign="top"
        height={36}
        iconType="circle"
        formatter={(value: string) => {
          const platformName = value.charAt(0).toUpperCase() + value.slice(1);
          return <span className="text-caption text-subtle">{platformName}</span>;
        }}
      />
    );
  } else if (rating?.history) {
    // Single platform mode
    data = rating.history.map((item) => {
      const rawDate = "recorded_at" in item ? item.recorded_at : item.date;
      const formattedDate = formatDate(rawDate);
      return {
        date: formattedDate,
        rating: item.rating,
      };
    });

    lines = [
      <Line
        key="single"
        type="monotone"
        dataKey="rating"
        name="Rating"
        stroke={PLATFORM_COLORS[platform || "codeforces"] || "var(--pastel-blue)"}
        strokeWidth={2.5}
        dot={false}
        activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--card)" }}
        animationDuration={900}
        animationEasing="ease-out"
      />,
    ];
  }

  const title = aggregateRating
    ? "Rating progress across platforms"
    : rating
      ? `${
          platform === "leetcode"
            ? "LeetCode"
            : platform === "codeforces"
              ? "Codeforces"
              : platform === "codechef"
                ? "CodeChef"
                : platform === "atcoder"
                  ? "AtCoder"
                  : platform || "Platform"
        } rating progress`
      : "Rating progress";
  const caption = aggregateRating
    ? "Rating changes from all your synced platforms"
    : rating
      ? `Rating changes from your synced ${
          platform === "leetcode"
            ? "LeetCode"
            : platform === "codeforces"
              ? "Codeforces"
              : platform === "codechef"
                ? "CodeChef"
                : platform === "atcoder"
                  ? "AtCoder"
                  : platform || "Platform"
        } contests`
      : "Contest rating progress";

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
            description={`Join a rated ${
              platform === "leetcode"
                ? "LeetCode"
                : platform === "codeforces"
                  ? "Codeforces"
                  : platform === "codechef"
                    ? "CodeChef"
                    : platform === "atcoder"
                      ? "AtCoder"
                      : platform || "Platform"
            } contest and sync your profile to see rating progress.`}
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
              {legend}
              {lines}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
