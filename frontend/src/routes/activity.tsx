import { createFileRoute } from "@tanstack/react-router";

import { getDashboardErrorMessage } from "@/api/client";
import { ActivityTimeline } from "@/components/dashboard/ActivityTimeline";
import { Heatmap } from "@/components/dashboard/Heatmap";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, Skeleton } from "@/components/ui-kit/motion";
import { Panel } from "@/components/ui-kit/Panel";
import { useAnalytics } from "@/hooks/useAnalytics";
import { useDashboard } from "@/hooks/useDashboard";

const title = "Submission Activity — CodePulse";
const description =
  "A year of submissions in a rounded contribution heatmap, paired with a timeline of solved problems and contest entries.";

export const Route = createFileRoute("/activity")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: ActivityPage,
});

function ActivityPage() {
  const { authenticated, profile, isLoadingProfiles, activity } = useAnalytics();
  const dashboard = useDashboard();

  if (!authenticated) {
    return (
      <AppShell title="Submission Activity" subtitle="One square per day, one year of practice.">
        <EmptyState
          title="Sign in to view submission activity"
          description="Sign in with your CodePulse account to view your activity heatmap and submission timeline."
        />
      </AppShell>
    );
  }

  if (isLoadingProfiles || dashboard.profiles.isLoading) {
    return (
      <AppShell title="Submission Activity" subtitle="One square per day, one year of practice.">
        <div className="space-y-6" aria-busy>
          <Skeleton className="h-[200px] w-full rounded-2xl" />
          <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
            <Skeleton className="h-[300px] w-full rounded-2xl" />
            <Skeleton className="h-[300px] w-full rounded-2xl" />
          </div>
        </div>
      </AppShell>
    );
  }

  if (!profile) {
    return (
      <AppShell title="Submission Activity" subtitle="One square per day, one year of practice.">
        <EmptyState
          title="No Codeforces profile connected"
          description="Connect and sync a Codeforces profile to see submission history and activity."
        />
      </AppShell>
    );
  }

  // Calculate 7-day rolling statistics from activity data
  const activityDays = activity.data?.activity ?? [];
  const now = new Date();
  const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);

  const last7Days = activityDays.filter((day) => new Date(day.date) >= sevenDaysAgo);
  const totalSubmissions7d = last7Days.reduce((acc, d) => acc + d.total_submissions, 0);
  const accepted7d = last7Days.reduce((acc, d) => acc + d.accepted_submissions, 0);
  const rejected7d = last7Days.reduce((acc, d) => acc + d.rejected_submissions, 0);

  const weeklyStats = [
    { label: "Submissions (7d)", value: String(totalSubmissions7d) },
    { label: "Accepted (7d)", value: String(accepted7d) },
    { label: "Rejected (7d)", value: String(rejected7d) },
    { label: "Total solved", value: String(profile.problems_solved) },
    { label: "Contests attended", value: String(profile.contests_attended) },
  ];

  return (
    <AppShell title="Submission Activity" subtitle="One square per day, one year of practice.">
      <div className="space-y-6">
        <Heatmap
          activity={activity.data?.activity}
          isLoading={activity.isLoading}
          error={activity.error ? getDashboardErrorMessage(activity.error) : undefined}
          onRetry={() => activity.refetch()}
        />
        <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
          <ActivityTimeline
            submissions={dashboard.submissions.data}
            isLoading={dashboard.submissions.isLoading}
            error={
              dashboard.submissions.error
                ? getDashboardErrorMessage(dashboard.submissions.error)
                : undefined
            }
            onRetry={() => dashboard.submissions.refetch()}
          />
          <Panel title="This week" caption="Rolling seven-day summary">
            <ul className="space-y-4">
              {weeklyStats.map((s) => (
                <li
                  key={s.label}
                  className="flex items-center justify-between rounded-2xl bg-muted px-4 py-3"
                >
                  <span className="text-caption text-muted-foreground">{s.label}</span>
                  <span className="text-caption font-semibold">{s.value}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
