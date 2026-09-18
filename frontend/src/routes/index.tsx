import { createFileRoute, redirect } from "@tanstack/react-router";
import { ClipboardList, RefreshCw, Target, Trophy } from "lucide-react";

import { hasAccessToken } from "@/api/client";

import { getDashboardErrorMessage } from "@/api/client";
import type { DashboardAggregateOverview } from "@/api/dashboard";
import { ActivityTimeline } from "@/components/dashboard/ActivityTimeline";
import { Heatmap } from "@/components/dashboard/Heatmap";
import { PlatformCards } from "@/components/dashboard/PlatformCards";
import { RatingChart } from "@/components/dashboard/RatingChart";
import { StatCard } from "@/components/dashboard/StatCard";
import { ContestsTable } from "@/components/dashboard/Tables";
import { TopicDonut } from "@/components/dashboard/TopicDonut";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui-kit/motion";
import { useAnalytics } from "@/hooks/useAnalytics";
import { useDashboard } from "@/hooks/useDashboard";

const title = "CodePulse — Competitive Programming Tracker";
const description =
  "Track your combined competitive-programming progress with synced submissions, contests, ratings and problem statistics.";

export const Route = createFileRoute("/")({
  beforeLoad: () => {
    if (!hasAccessToken()) {
      throw redirect({ to: "/auth" });
    }
  },
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: Dashboard,
});

function DashboardStatSkeletons() {
  return (
    <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4" aria-busy>
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="surface-card space-y-5 p-6">
          <Skeleton className="h-11 w-11 rounded-2xl" />
          <Skeleton className="h-3 w-24" />
          <Skeleton className="h-8 w-28" />
          <Skeleton className="h-3 w-32" />
        </div>
      ))}
    </div>
  );
}

function OverviewStats({ overview }: { overview: DashboardAggregateOverview }) {
  return (
    <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        label="Problems solved"
        value={overview.total_problems_solved.toLocaleString()}
        note="Across connected platforms"
        icon={Target}
        tint="bg-blue-soft"
      />
      <StatCard
        label="Synced submissions"
        value={overview.total_submissions.toLocaleString()}
        note="Recorded submission history"
        icon={ClipboardList}
        tint="bg-violet-soft"
      />
      <StatCard
        label="Contests attended"
        value={overview.contests_attended.toLocaleString()}
        note="Across connected platforms"
        icon={RefreshCw}
        tint="bg-pink-soft"
      />
      <StatCard
        label="Connected platforms"
        value={overview.connected_platforms.toLocaleString()}
        note="Accounts linked to CodePulse"
        icon={Trophy}
        tint="bg-yellow-soft"
      />
    </div>
  );
}

function Dashboard() {
  const dashboard = useDashboard();
  const analytics = useAnalytics();

  if (dashboard.aggregate.isLoading || analytics.isLoadingProfiles) {
    return (
      <AppShell title="Dashboard" subtitle="Your complete competitive programming progress.">
        <DashboardStatSkeletons />
      </AppShell>
    );
  }

  if (dashboard.aggregate.error) {
    return (
      <AppShell title="Dashboard" subtitle="Your complete competitive programming progress.">
        <ErrorState
          description={getDashboardErrorMessage(dashboard.aggregate.error)}
          onRetry={() => dashboard.aggregate.refetch()}
        />
      </AppShell>
    );
  }

  const aggregate = dashboard.aggregate.data;
  if (!aggregate || aggregate.overview.connected_platforms === 0) {
    return (
      <AppShell title="Dashboard" subtitle="Your complete competitive programming progress.">
        <EmptyState
          title="No platforms connected yet"
          description="Connect Codeforces or LeetCode to see your progress."
        />
      </AppShell>
    );
  }

  const ratingError = analytics.aggregateRating.error
    ? getDashboardErrorMessage(analytics.aggregateRating.error)
    : undefined;
  const topicError = analytics.aggregateTopic.error
    ? getDashboardErrorMessage(analytics.aggregateTopic.error)
    : undefined;
  const activityError = analytics.aggregateActivity.error
    ? getDashboardErrorMessage(analytics.aggregateActivity.error)
    : undefined;

  return (
    <AppShell title="Dashboard" subtitle="Your complete competitive programming progress.">
      <div className="space-y-6">
        <OverviewStats overview={aggregate.overview} />

        <RatingChart
          compact
          aggregateRating={analytics.aggregateRating.data}
          isLoading={analytics.aggregateRating.isLoading}
          error={ratingError}
          onRetry={() => analytics.aggregateRating.refetch()}
        />

        <TopicDonut
          topicData={analytics.aggregateTopic.data}
          isLoading={analytics.aggregateTopic.isLoading}
          error={topicError}
          onRetry={() => analytics.aggregateTopic.refetch()}
        />

        <Heatmap
          activity={analytics.aggregateActivity.data?.activity}
          totalSubmissions={analytics.aggregateActivity.data?.total_submissions}
          isLoading={analytics.aggregateActivity.isLoading}
          error={activityError}
          onRetry={() => analytics.aggregateActivity.refetch()}
        />

        <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
          <ActivityTimeline limit={5} submissions={aggregate.submissions} />
          <ContestsTable limit={5} contests={aggregate.contests} />
        </div>

        <section>
          <h2 className="text-h3 mb-5">Platforms</h2>
          <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
            {aggregate.overview.platforms.map((platform) => (
              <PlatformCards key={platform.profile_id} overview={platform} />
            ))}
          </div>
        </section>
      </div>
    </AppShell>
  );
}
