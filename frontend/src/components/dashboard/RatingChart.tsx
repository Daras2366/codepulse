import { useRef, useState } from "react";
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
  type TooltipPayload,
} from "recharts";

import type {
  AggregateRatingPoint,
  AggregateRatingProgression,
  AggregateRatingSeries,
} from "@/api/analytics";
import type { DashboardRating } from "@/api/dashboard";
import type { Platform } from "@/api/dashboard";
import { ActionButton, ChartSkeleton, EmptyState, ErrorState } from "@/components/ui-kit/motion";
import { Panel } from "@/components/ui-kit/Panel";
import { exportChartAsPng } from "@/lib/export-chart";

const PLATFORM_COLORS: Record<string, string> = {
  codeforces: "var(--pastel-blue)",
  leetcode: "var(--pastel-yellow)",
  codechef: "var(--pastel-green)",
  atcoder: "var(--pastel-pink)",
};

const TIME_RANGES = [
  { key: "7D", label: "7D", days: 7 },
  { key: "30D", label: "30D", days: 30 },
  { key: "90D", label: "90D", days: 90 },
  { key: "1Y", label: "1Y", days: 365 },
  { key: "All", label: "All", days: null },
];

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
  const sorted = [...payload].sort((a, b) => (b.value ?? 0) - (a.value ?? 0));

  // Format timestamp for display
  let displayLabel = label;
  if (typeof label === "number") {
    displayLabel = formatDate(new Date(label));
  }

  return (
    <div className="surface-card px-4 py-3">
      <p className="text-label uppercase text-subtle">{displayLabel}</p>
      <div className="mt-2 space-y-1.5">
        {sorted.map((p: TooltipPayload<number, string>) => (
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

interface ChartDataPoint {
  timestamp: number;
  [platform: string]: number | null | undefined;
}

interface PlatformDataMap {
  [platform: string]: AggregateRatingSeries;
}

interface RatingChartProps {
  compact?: boolean;
  rating?: DashboardRating | undefined;
  aggregateRating?: AggregateRatingProgression | undefined;
  platform?: string;
  availablePlatforms?: Platform[];
  selectedPlatforms?: Platform[];
  onPlatformChange?: (platforms: Platform[]) => void;
  isLoading?: boolean;
  error?: string | undefined;
  onRetry?: (() => void) | undefined;
}

export function RatingChart({
  compact = false,
  rating,
  aggregateRating,
  platform,
  availablePlatforms = [],
  selectedPlatforms = [],
  onPlatformChange,
  isLoading = false,
  error,
  onRetry,
}: RatingChartProps) {
  const [timeRange, setTimeRange] = useState("1Y");
  const [loading, setLoading] = useState(false);
  const [hovered, setHovered] = useState<string | null>(null);
  const chartRef = useRef<HTMLDivElement | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const rangeConfig = TIME_RANGES.find((r) => r.key === timeRange);
  const height = compact ? 260 : 360;

  function changeRange(key: string) {
    setTimeRange(key);
    setLoading(true);
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setLoading(false), 420);
  }

  function togglePlatform(platform: Platform) {
    if (!onPlatformChange) return;

    if (selectedPlatforms.includes(platform)) {
      // Don't allow deselecting the last platform
      if (selectedPlatforms.length > 1) {
        onPlatformChange(selectedPlatforms.filter((p) => p !== platform));
      }
    } else {
      onPlatformChange([...selectedPlatforms, platform]);
    }
  }

  function showAll() {
    if (onPlatformChange && availablePlatforms.length > 0) {
      onPlatformChange(availablePlatforms);
    }
  }

  let data: ChartDataPoint[] = [];
  let lines: React.ReactNode[] = [];
  let legend: React.ReactNode = null;

  if (aggregateRating) {
    // Aggregate mode: multiple lines for each platform with forward-fill
    // New structure: { series: [{ platform, username, history: [{ date, rating, platform }] }] }

    // Apply time range filtering
    const now = new Date();
    const cutoffDate = rangeConfig?.days
      ? new Date(now.getTime() - rangeConfig.days * 24 * 60 * 60 * 1000)
      : null;

    // Collect all rating events with actual timestamps
    const allEvents: Array<{ timestamp: Date; platform: string; rating: number }> = [];
    const platformDataMap: PlatformDataMap = {};

    aggregateRating.series.forEach((series: AggregateRatingSeries) => {
      platformDataMap[series.platform] = series;
      series.history.forEach((item: AggregateRatingPoint) => {
        const dateObj = normalizeDate(item.date);
        // Filter by time range if specified
        if (!cutoffDate || dateObj >= cutoffDate) {
          allEvents.push({
            timestamp: dateObj,
            platform: series.platform,
            rating: item.rating,
          });
        }
      });
    });

    // Sort all events chronologically
    allEvents.sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

    // Create timeline from union of all timestamps
    const uniqueTimestamps = Array.from(new Set(allEvents.map((e) => e.timestamp.getTime()))).sort(
      (a, b) => a - b,
    );

    // Build forward-filled data for each platform
    const platformRatings: Record<string, number[]> = {};
    const platformFirstEvent: Record<string, number> = {};

    Object.keys(platformDataMap).forEach((platform) => {
      platformRatings[platform] = [];
      platformFirstEvent[platform] = -1;

      // Sort this platform's events chronologically
      const platformEvents = allEvents
        .filter((e) => e.platform === platform)
        .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

      if (platformEvents.length > 0) {
        platformFirstEvent[platform] = uniqueTimestamps.indexOf(
          platformEvents[0].timestamp.getTime(),
        );
      }
    });

    // For each timestamp, forward-fill ratings
    uniqueTimestamps.forEach((timestamp, index) => {
      Object.keys(platformDataMap).forEach((platform) => {
        const platformEvents = allEvents
          .filter((e) => e.platform === platform)
          .sort((a, b) => a.timestamp.getTime() - b.timestamp.getTime());

        // Find the most recent rating event at or before this timestamp
        let rating = null;
        for (let i = platformEvents.length - 1; i >= 0; i--) {
          if (platformEvents[i].timestamp.getTime() <= timestamp) {
            rating = platformEvents[i].rating;
            break;
          }
        }

        platformRatings[platform].push(rating);
      });
    });

    // Build chart data with actual timestamps
    data = uniqueTimestamps.map((timestamp, index) => {
      const point: ChartDataPoint = { timestamp };
      Object.keys(platformDataMap).forEach((platform) => {
        point[platform] = platformRatings[platform][index];
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
        strokeWidth={hovered === platform ? 3.5 : 2.5}
        strokeOpacity={hovered && hovered !== platform ? 0.35 : 1}
        dot={false}
        activeDot={{ r: 5, strokeWidth: 2, stroke: "var(--card)" }}
        connectNulls={true}
        animationDuration={900}
        animationEasing="ease-out"
        onMouseEnter={() => setHovered(platform)}
        onMouseLeave={() => setHovered(null)}
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
    // Single platform mode - use actual timestamps with forward-fill
    data = rating.history
      .map((item) => {
        const rawDate = "recorded_at" in item ? item.recorded_at : item.date;
        const dateObj = normalizeDate(rawDate);
        return {
          timestamp: dateObj.getTime(),
          rating: item.rating,
        };
      })
      .sort((a, b) => a.timestamp - b.timestamp);

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
        connectNulls={true}
        animationDuration={900}
        animationEasing="ease-out"
      />,
    ];
  }

  const platformDisplayName =
    platform === "leetcode"
      ? "LeetCode"
      : platform === "codeforces"
        ? "Codeforces"
        : platform === "codechef"
          ? "CodeChef"
          : platform === "atcoder"
            ? "AtCoder"
            : platform || "Platform";

  const title = aggregateRating
    ? "Rating progress across platforms"
    : rating
      ? `${platformDisplayName} rating progress`
      : "Rating progress";
  const caption = aggregateRating
    ? "Rating changes from all your synced platforms"
    : rating
      ? `Rating changes from your synced ${platformDisplayName} contests`
      : "Contest rating progress";

  const shownPlatforms = availablePlatforms.filter((p) => selectedPlatforms.includes(p));

  return (
    <Panel
      title={title}
      caption={caption}
      action={
        <div className="flex flex-wrap items-center gap-2">
          {TIME_RANGES.map((range) => (
            <button
              key={range.key}
              onClick={() => changeRange(range.key)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                timeRange === range.key
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              {range.label}
            </button>
          ))}
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
        </div>
      }
    >
      {/* Platform Selector */}
      {availablePlatforms.length > 1 && (
        <div className="mb-6 flex flex-wrap gap-2">
          {availablePlatforms.map((p) => {
            const isSelected = selectedPlatforms.includes(p);
            const displayName =
              p === "leetcode"
                ? "LeetCode"
                : p === "codeforces"
                  ? "Codeforces"
                  : p === "codechef"
                    ? "CodeChef"
                    : p === "atcoder"
                      ? "AtCoder"
                      : p.charAt(0).toUpperCase() + p.slice(1);
            return (
              <button
                key={p}
                onClick={() => togglePlatform(p)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  isSelected
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                {displayName}
              </button>
            );
          })}
        </div>
      )}

      {isLoading || loading ? (
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
            action={
              shownPlatforms.length === 0 && availablePlatforms.length > 0 ? (
                <ActionButton onClick={showAll}>Show all</ActionButton>
              ) : undefined
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
                dataKey="timestamp"
                tickLine={false}
                axisLine={false}
                tick={{ fill: "var(--subtle)", fontSize: 12 }}
                dy={10}
                minTickGap={80}
                tickFormatter={(value) => {
                  const label = formatDate(new Date(value));
                  return label;
                }}
              />
              <YAxis
                tickLine={false}
                axisLine={false}
                width={52}
                tick={{ fill: "var(--subtle)", fontSize: 12 }}
                domain={["dataMin - 120", "dataMax + 80"]}
              />
              <Tooltip content={<ChartTooltip />} cursor={{ stroke: "var(--border)" }} />
              {lines}
              {legend}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </Panel>
  );
}
