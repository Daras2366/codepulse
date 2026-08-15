import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { ClipboardList, RefreshCw, Target, Trophy } from "lucide-react";

import { getDashboardErrorMessage } from "@/api/client";
import type { DashboardOverview, Platform } from "@/api/dashboard";
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
  "Track competitive programming progress with synced submissions, contests, ratings and problem statistics.";

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

function OverviewStats({
  overview,
  platformName,
  aggregateStats,
}: {
  overview: DashboardOverview | null;
  platformName: string;
  aggregateStats: any;
}) {
  // If aggregate mode, show aggregate statistics
  if (aggregateStats) {
    return (
      <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Problems solved"
          value={String(aggregateStats.totalProblemsSolved)}
          note={`${aggregateStats.platformCount} platform${aggregateStats.platformCount !== 1 ? "s" : ""}`}
          icon={Target}
          tint="bg-blue-soft"
        />
        <StatCard
          label="Contests attended"
          value={String(aggregateStats.totalContestsAttended)}
          note={`${aggregateStats.platformCount} platform${aggregateStats.platformCount !== 1 ? "s" : ""}`}
          icon={RefreshCw}
          tint="bg-pink-soft"
        />
        <StatCard
          label="Connected platforms"
          value={String(aggregateStats.platformCount)}
          note="Total platforms linked"
          icon={Trophy}
          tint="bg-yellow-soft"
        />
        <StatCard
          label="Platform breakdown"
          value=""
          note="See details below"
          icon={ClipboardList}
          tint="bg-violet-soft"
        />
      </div>
    );
  }

  return (
    <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        label="Problems solved"
        value={String(overview.total_problems_solved)}
        note={`Accepted ${platformName} problems`}
        icon={Target}
        tint="bg-blue-soft"
      />
      <StatCard
        label="Total submissions"
        value={String(overview.total_submissions)}
        note={`Synced ${platformName} submissions`}
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
  const [selectedPlatform, setSelectedPlatform] = useState<Platform | "all" | null>(null);
  const dashboard = useDashboard(selectedPlatform || undefined);

  // Get platform name for display
  const platformName =
    dashboard.profile?.platform === "leetcode"
      ? "LeetCode"
      : dashboard.profile?.platform === "codeforces"
        ? "Codeforces"
        : dashboard.profile?.platform || "Platform";

  const subtitle = dashboard.isAggregateMode
    ? "Your complete competitive programming progress."
    : "Your synced competitive programming progress at a glance.";

  if (!dashboard.authenticated) {
    return (
      <AppShell title="Dashboard" subtitle="Your synced competitive programming record.">
        <EmptyState
          title="Sign in to view your dashboard"
          description="Use your CodePulse session to load your connected platform profiles."
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

  if (!dashboard.profile && !dashboard.isAggregateMode) {
    return (
      <AppShell title="Dashboard" subtitle="Your synced competitive programming record.">
        <EmptyState
          title="No platform profiles connected"
          description="Connect a platform profile to see your statistics here."
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

  // Get available platforms for selector
  const availablePlatforms = dashboard.profiles.data?.map((p) => p.platform) || [];
  const hasMultiplePlatforms = availablePlatforms.length > 1;

  return (
    <AppShell
      title="Dashboard"
      subtitle={
        dashboard.isAggregateMode
          ? "Your complete competitive programming progress."
          : "Your synced competitive programming progress at a glance."
      }
    >
      <div className="space-y-6">
        {/* Platform Selector */}
        {hasMultiplePlatforms && (
          <div className="flex gap-2">
            <button
              onClick={() => setSelectedPlatform("all")}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                selectedPlatform === "all"
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted text-muted-foreground hover:bg-muted/80"
              }`}
            >
              All Platforms
            </button>
            {availablePlatforms.map((platform) => (
              <button
                key={platform}
                onClick={() => setSelectedPlatform(selectedPlatform === platform ? null : platform)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  (selectedPlatform === null && platform === dashboard.profile?.platform) ||
                  selectedPlatform === platform
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                {platform === "leetcode"
                  ? "LeetCode"
                  : platform === "codeforces"
                    ? "Codeforces"
                    : platform.charAt(0).toUpperCase() + platform.slice(1)}
              </button>
            ))}
          </div>
        )}

        {/* Aggregate Mode: Platform Breakdown */}
        {dashboard.isAggregateMode && dashboard.aggregateStats && (
          <div className="surface-card p-6">
            <h2 className="text-h3 mb-4">Platform Breakdown</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
              {dashboard.aggregateStats.platforms.map((platform) => (
                <div key={platform.platform} className="border border-border rounded-xl p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <span
                      className={`text-caption font-bold px-2 py-1 rounded ${
                        platform.platform === "leetcode"
                          ? "bg-yellow-soft"
                          : platform.platform === "codeforces"
                            ? "bg-blue-soft"
                            : "bg-muted"
                      }`}
                    >
                      {platform.platform === "leetcode"
                        ? "LC"
                        : platform.platform === "codeforces"
                          ? "CF"
                          : platform.platform.slice(0, 2).toUpperCase()}
                    </span>
                    <span className="text-label capitalize">{platform.platform}</span>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between">
                      <span className="text-label text-subtle">Problems</span>
                      <span className="text-caption font-semibold">{platform.problemsSolved}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-label text-subtle">Contests</span>
                      <span className="text-caption font-semibold">
                        {platform.contestsAttended}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-label text-subtle">Rating</span>
                      <span className="text-caption font-semibold">
                        {platform.currentRating ?? "Unrated"}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Single Platform Mode: Regular Dashboard */}
        {!dashboard.isAggregateMode && (
          <>
            {dashboard.overview.isLoading ? (
              <DashboardStatSkeletons />
            ) : overviewError ? (
              <ErrorState
                description={overviewError}
                onRetry={() => dashboard.overview.refetch()}
              />
            ) : dashboard.overview.data ? (
              <>
                <WelcomeCard
                  overview={dashboard.overview.data}
                  platform={dashboard.profile?.platform}
                />
                <OverviewStats
                  overview={dashboard.overview.data}
                  platformName={platformName}
                  aggregateStats={null}
                />
              </>
            ) : null}

            <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
              <RatingChart
                compact
                rating={dashboard.isAggregateMode ? undefined : dashboard.rating.data}
                aggregateRating={
                  dashboard.isAggregateMode ? dashboard.aggregateRating.data : undefined
                }
                platform={dashboard.profile?.platform}
                isLoading={
                  dashboard.isAggregateMode
                    ? dashboard.aggregateRating.isLoading
                    : dashboard.rating.isLoading
                }
                error={
                  dashboard.isAggregateMode
                    ? dashboard.aggregateRating.error
                      ? getDashboardErrorMessage(dashboard.aggregateRating.error)
                      : undefined
                    : ratingError
                }
                onRetry={() => {
                  if (dashboard.isAggregateMode) {
                    dashboard.aggregateRating.refetch();
                  } else {
                    dashboard.rating.refetch();
                  }
                }}
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
          </>
        )}

        {/* Aggregate Mode: Aggregate Statistics */}
        {dashboard.isAggregateMode && dashboard.aggregateStats && (
          <OverviewStats
            overview={null}
            platformName="All"
            aggregateStats={dashboard.aggregateStats}
          />
        )}
      </div>
    </AppShell>
  );
}
