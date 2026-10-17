import { useMemo, useState } from "react";

import type { AggregateActivityDay } from "@/api/analytics";
import type { AnalyticsActivityDay } from "@/api/analytics";
import type { DashboardSubmissionActivity } from "@/api/dashboard";
import { ChartSkeleton, EmptyState, ErrorState } from "@/components/ui-kit/motion";
import { Panel } from "@/components/ui-kit/Panel";

const levels = [
  "bg-[color-mix(in_oklab,var(--border)_60%,var(--card))]",
  "bg-[color-mix(in_oklab,var(--pastel-green)_40%,var(--card))]",
  "bg-[color-mix(in_oklab,var(--pastel-green)_65%,var(--card))]",
  "bg-[color-mix(in_oklab,var(--pastel-green)_85%,var(--card))]",
  "bg-[var(--success)]",
];

function levelForCount(count: number, peak: number) {
  if (count === 0 || peak === 0) return 0;
  return Math.min(4, Math.max(1, Math.ceil((count / peak) * 4)));
}

type GenericActivityItem =
  | DashboardSubmissionActivity
  | AnalyticsActivityDay
  | AggregateActivityDay
  | { date?: string; activity_date?: string; total_submissions: number };

function buildActivityHeatmap(activity: GenericActivityItem[] = []) {
  const counts = new Map<string, number>();
  let peak = 0;

  for (const item of activity) {
    const key = "activity_date" in item && item.activity_date ? item.activity_date : item.date;
    if (key) {
      counts.set(key, item.total_submissions);
      if (item.total_submissions > peak) peak = item.total_submissions;
    }
  }

  const today = new Date();
  const start = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate()));
  start.setUTCDate(start.getUTCDate() - 52 * 7 - start.getUTCDay());

  return Array.from({ length: 53 }, (_, week) =>
    Array.from({ length: 7 }, (_, day) => {
      const date = new Date(start);
      date.setUTCDate(start.getUTCDate() + week * 7 + day);
      const key = date.toISOString().slice(0, 10);
      const count = date > today ? 0 : (counts.get(key) ?? 0);
      return {
        count,
        level: levelForCount(count, peak),
        label: date.toLocaleDateString("en-US", {
          month: "short",
          day: "numeric",
          year: "numeric",
          timeZone: "UTC",
        }),
      };
    }),
  );
}

export function Heatmap({
  activity,
  totalSubmissions,
  isLoading = false,
  error,
  onRetry,
}: {
  activity?: GenericActivityItem[] | undefined;
  totalSubmissions?: number | undefined;
  isLoading?: boolean;
  error?: string | undefined;
  onRetry?: (() => void) | undefined;
}) {
  const weeks = useMemo(() => buildActivityHeatmap(activity), [activity]);
  const [hover, setHover] = useState<{ label: string; count: number } | null>(null);
  const total =
    totalSubmissions ?? activity?.reduce((sum, item) => sum + item.total_submissions, 0) ?? 0;

  return (
    <Panel
      title="Submission activity"
      caption={`${total.toLocaleString()} submissions in the last year`}
      action={
        <div className="flex items-center gap-2">
          <span className="text-label text-subtle">Less</span>
          {levels.map((level, index) => (
            <span key={index} className={`h-3 w-3 rounded-[4px] ${level}`} />
          ))}
          <span className="text-label text-subtle">More</span>
        </div>
      }
    >
      {isLoading ? (
        <ChartSkeleton height={180} />
      ) : error ? (
        <ErrorState description={error} onRetry={onRetry} />
      ) : !activity || activity.length === 0 ? (
        <EmptyState
          title="No submission activity yet"
          description="Sync your platform profiles after submitting problems to see activity here."
        />
      ) : (
        <div className="relative">
          <div className="no-scrollbar overflow-x-auto pb-2">
            <div className="min-w-[720px]">
              <div className="flex gap-[3px]">
                {weeks.map((week, weekIndex) => (
                  <div key={weekIndex} className="flex flex-col gap-[3px]">
                    {week.map((day, dayIndex) => (
                      <span
                        key={dayIndex}
                        onMouseEnter={() => setHover(day)}
                        onMouseLeave={() => setHover(null)}
                        className={`h-3 w-3 rounded-[4px] transition-transform duration-150 hover:scale-125 ${levels[day.level]}`}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div className="mt-4 h-6">
            {hover && (
              <span className="text-caption rounded-full bg-muted px-3 py-1 text-muted-foreground">
                {hover.count} submissions · {hover.label}
              </span>
            )}
          </div>
        </div>
      )}
    </Panel>
  );
}
