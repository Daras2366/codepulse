import { createFileRoute } from "@tanstack/react-router";
import { ClipboardList, RefreshCw, Target, Trophy } from "lucide-react";

import { getDashboardErrorMessage } from "@/api/client";
import type { DashboardOverview } from "@/api/dashboard";
import { ActivityTimeline } from "@/components/dashboard/ActivityTimeline";
import { Heatmap } from "@/components/dashboard/Heatmap";
import { PlatformCards } from "@/components/dashboard/PlatformCards";
import { RatingChart } from "@/components/dashboard/RatingChart";
import { StatCard } from "@/components/dashboard/StatCard";
import { ContestsTable } from "@/components/dashboard/Tables";
import { TopicDonut } from "@/components/dashboard/TopicDonut";
import { WelcomeCard } from "@/components/dashboard/WelcomeCard";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui-kit/motion";
import { useDashboard } from "@/hooks/useDashboard";

const title = "CodePulse — Competitive Programming Tracker";
const description =
  "Track Codeforces progress with synced submissions, contests, ratings and problem statistics.";

export const Route = createFileRoute("/")({
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

function OverviewStats({ overview }: { overview: DashboardOverview }) {
  return (
    <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        label="Problems solved"
        value={String(overview.total_problems_solved)}
        note="Accepted Codeforces problems"
        icon={Target}
        tint="bg-blue-soft"
      />
      <StatCard
        label="Total submissions"
        value={String(overview.total_submissions)}
        note="Synced Codeforces submissions"
        icon={ClipboardList}
        tint="bg-violet-soft"
      />
      <StatCard
        label="Contest rating"
        value={overview.current_rating?.toLocaleString() ?? "Unrated"}
        note={overview.rank ?? "No current rank"}
        icon={Trophy}
        tint="bg-yellow-soft"
      />
      <StatCard
        label="Contests attended"
        value={String(overview.contests_attended)}
        note={
          overview.max_rating === null
            ? "No peak rating yet"
            : `Peak ${overview.max_rating.toLocaleString()}`
        }
        icon={RefreshCw}
        tint="bg-pink-soft"
      />
    </div>
  );
}

function Dashboard() {
  const dashboard = useDashboard();

  if (!dashboard.authenticated) {
    return (
      <AppShell title="Dashboard" subtitle="Your synced competitive programming record.">
        <EmptyState
          title="Sign in to view your dashboard"
          description="Use your CodePulse session to load the Codeforces profile connected to your account."
        />
      </AppShell>
    );
  }

  if (dashboard.profiles.isLoading) {
    return (
      <AppShell title="Dashboard" subtitle="Your synced competitive programming record.">
        <DashboardStatSkeletons />
      </AppShell>
    );
  }

  if (dashboard.profiles.error) {
    return (
      <AppShell title="Dashboard" subtitle="Your synced competitive programming record.">
        <ErrorState
          description={getDashboardErrorMessage(dashboard.profiles.error)}
          onRetry={() => dashboard.profiles.refetch()}
        />
      </AppShell>
    );
  }

  if (!dashboard.profile) {
    return (
      <AppShell title="Dashboard" subtitle="Your synced competitive programming record.">
        <EmptyState
          title="No Codeforces profile yet"
          description="Connect and sync a Codeforces profile to see your statistics here."
        />
      </AppShell>
    );
  }

  const overviewError = dashboard.overview.error
    ? getDashboardErrorMessage(dashboard.overview.error)
    : undefined;
  const ratingError = dashboard.rating.error
    ? getDashboardErrorMessage(dashboard.rating.error)
    : undefined;
  const problemsError = dashboard.problems.error
    ? getDashboardErrorMessage(dashboard.problems.error)
    : undefined;
  const submissionsError = dashboard.submissions.error
    ? getDashboardErrorMessage(dashboard.submissions.error)
    : undefined;
  const contestsError = dashboard.contests.error
    ? getDashboardErrorMessage(dashboard.contests.error)
    : undefined;

  return (
    <AppShell title="Dashboard" subtitle="Your synced Codeforces progress at a glance.">
      <div className="space-y-6">
        {dashboard.overview.isLoading ? (
          <DashboardStatSkeletons />
        ) : overviewError ? (
          <ErrorState description={overviewError} onRetry={() => dashboard.overview.refetch()} />
        ) : dashboard.overview.data ? (
          <>
            <WelcomeCard overview={dashboard.overview.data} />
            <OverviewStats overview={dashboard.overview.data} />
          </>
        ) : null}

        <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
          <RatingChart
            compact
            rating={dashboard.rating.data}
            isLoading={dashboard.rating.isLoading}
            error={ratingError}
            onRetry={() => dashboard.rating.refetch()}
          />
          <TopicDonut
            problems={dashboard.problems.data}
            isLoading={dashboard.problems.isLoading}
            error={problemsError}
            onRetry={() => dashboard.problems.refetch()}
          />
        </div>

        <Heatmap
          activity={dashboard.submissions.data?.activity}
          isLoading={dashboard.submissions.isLoading}
          error={submissionsError}
          onRetry={() => dashboard.submissions.refetch()}
        />

        <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
          <ActivityTimeline
            limit={5}
            submissions={dashboard.submissions.data}
            isLoading={dashboard.submissions.isLoading}
            error={submissionsError}
            onRetry={() => dashboard.submissions.refetch()}
          />
          <ContestsTable
            limit={5}
            contests={dashboard.contests.data}
            isLoading={dashboard.contests.isLoading}
            error={contestsError}
            onRetry={() => dashboard.contests.refetch()}
          />
        </div>

        {dashboard.overview.data && (
          <div>
            <h2 className="text-h3 mb-5">Platform</h2>
            <PlatformCards overview={dashboard.overview.data} rating={dashboard.rating.data} />
          </div>
        )}
      </div>
    </AppShell>
  );
}
