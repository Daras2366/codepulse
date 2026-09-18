import { CheckCircle2, CircleDot, Flag, Sparkles, Trophy } from "lucide-react";

import type { DashboardAggregateSubmissions, DashboardSubmissions } from "@/api/dashboard";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui-kit/motion";
import { Panel, Pill } from "@/components/ui-kit/Panel";

type TimelineItem = {
  kind: "solved" | "attempt" | "contest" | "milestone" | "topic";
  title: string;
  meta: string;
  time: string;
};

const config: Record<
  TimelineItem["kind"],
  {
    icon: typeof Trophy;
    tint: string;
    tone: "green" | "blue" | "yellow" | "violet" | "neutral";
    label: string;
  }
> = {
  solved: { icon: CheckCircle2, tint: "bg-green-soft", tone: "green", label: "Solved" },
  attempt: { icon: CircleDot, tint: "bg-yellow-soft", tone: "yellow", label: "Attempt" },
  contest: { icon: Trophy, tint: "bg-blue-soft", tone: "blue", label: "Contest" },
  milestone: { icon: Sparkles, tint: "bg-yellow-soft", tone: "yellow", label: "Milestone" },
  topic: { icon: Flag, tint: "bg-violet-soft", tone: "violet", label: "Topic" },
};

function formatTimestamp(value: string) {
  const d = new Date(value);
  if (isNaN(d.getTime())) return value;
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(d);
}

export function ActivityTimeline({
  limit,
  submissions,
  isLoading = false,
  error,
  onRetry,
}: {
  limit?: number;
  submissions?: DashboardSubmissions | DashboardAggregateSubmissions | undefined;
  isLoading?: boolean;
  error?: string | undefined;
  onRetry?: (() => void) | undefined;
}) {
  const items: TimelineItem[] = submissions
    ? submissions.recent_submissions.map((submission) => ({
        kind: submission.status === "accepted" ? "solved" : "attempt",
        title: submission.problem_title,
        meta: `${submission.platform} · ${submission.difficulty} · ${submission.language}`,
        time: formatTimestamp(submission.submitted_at),
      }))
    : [];
  const displayedItems = limit ? items.slice(0, limit) : items;

  return (
    <Panel title="Recent activity" caption="Your most recent synced submissions">
      {isLoading ? (
        <ListSkeleton rows={limit ?? 4} />
      ) : error ? (
        <ErrorState description={error} onRetry={onRetry} />
      ) : displayedItems.length === 0 ? (
        <EmptyState
          title="No submissions yet"
          description="Sync your Codeforces profile to see your recent submission activity."
        />
      ) : (
        <ol className="relative space-y-5 before:absolute before:top-2 before:bottom-2 before:left-[19px] before:w-px before:bg-border">
          {displayedItems.map((item, index) => {
            const appearance = config[item.kind];
            return (
              <li key={`${item.title}-${index}`} className="relative flex gap-4">
                <span
                  className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${appearance.tint}`}
                >
                  <appearance.icon className="h-[17px] w-[17px]" strokeWidth={1.6} />
                </span>
                <div className="min-w-0 flex-1 pt-1">
                  <div className="flex flex-wrap items-center gap-2.5">
                    <p className="text-caption font-semibold">{item.title}</p>
                    <Pill tone={appearance.tone}>{appearance.label}</Pill>
                  </div>
                  <p className="text-caption mt-1 text-muted-foreground">
                    {item.meta} · {item.time}
                  </p>
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Panel>
  );
}
