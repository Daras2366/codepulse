import { createFileRoute, redirect } from "@tanstack/react-router";
import { useState } from "react";

import { hasAccessToken } from "@/api/client";

import { getDashboardErrorMessage } from "@/api/client";
import { Heatmap } from "@/components/dashboard/Heatmap";
import { RatingChart } from "@/components/dashboard/RatingChart";
import { TopicDonut } from "@/components/dashboard/TopicDonut";
import { DifficultySplit } from "@/components/dashboard/DifficultySplit";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, Skeleton } from "@/components/ui-kit/motion";
import { useAnalytics } from "@/hooks/useAnalytics";
import type { Platform } from "@/api/dashboard";

const title = "Analytics — CodePulse";
const description =
  "Rating progress, topic distribution and submission heatmaps filtered by platform and time range across your competitive programming history.";

export const Route = createFileRoute("/analytics")({
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
  component: Analytics,
});

function Analytics() {
  const [selectedPlatforms, setSelectedPlatforms] = useState<Platform[]>([]);
  const {
    authenticated,
    profiles,
    isLoadingProfiles,
    aggregateRating,
    aggregateTopic,
    aggregateDifficulty,
    aggregateActivity,
  } = useAnalytics(selectedPlatforms);

  // Initialize selected platforms on first load
  if (selectedPlatforms.length === 0 && profiles.length > 0) {
    setSelectedPlatforms(profiles.map((p) => p.platform));
  }

  if (!authenticated) {
    return (
      <AppShell
        title="Analytics"
        subtitle="Slice your history by platform, topic, difficulty, and activity."
      >
        <EmptyState
          title="Sign in to view your analytics"
          description="Authenticate with your CodePulse session to inspect rating, difficulty, and activity trends."
        />
      </AppShell>
    );
  }

  if (isLoadingProfiles) {
    return (
      <AppShell
        title="Analytics"
        subtitle="Slice your history by platform, topic, difficulty, and activity."
      >
        <div className="space-y-6" aria-busy>
          <Skeleton className="h-[360px] w-full rounded-2xl" />
          <div className="grid gap-6 xl:grid-cols-2">
            <Skeleton className="h-[280px] w-full rounded-2xl" />
            <Skeleton className="h-[280px] w-full rounded-2xl" />
          </div>
        </div>
      </AppShell>
    );
  }

  if (profiles.length === 0) {
    return (
      <AppShell
        title="Analytics"
        subtitle="Slice your history by platform, topic, difficulty, and activity."
      >
        <EmptyState
          title="No platform profiles connected"
          description="Connect and sync a platform profile to unlock detailed performance analytics."
        />
      </AppShell>
    );
  }

  if (selectedPlatforms.length === 0) {
    return (
      <AppShell
        title="Analytics"
        subtitle="Slice your history by platform, topic, difficulty, and activity."
      >
        <EmptyState
          title="No platforms selected"
          description="Select at least one platform to view your analytics."
          action={
            <button
              onClick={() => setSelectedPlatforms(profiles.map((p) => p.platform))}
              className="press inline-flex items-center justify-center rounded-full bg-primary px-5 py-2.5 text-caption font-semibold text-primary-foreground"
            >
              Show all
            </button>
          }
        />
      </AppShell>
    );
  }

  return (
    <AppShell
      title="Analytics"
      subtitle="Slice your history by platform, topic, difficulty, and activity."
    >
      <div className="space-y-6">
        <RatingChart
          aggregateRating={aggregateRating.data}
          availablePlatforms={profiles.map((p) => p.platform)}
          selectedPlatforms={selectedPlatforms}
          onPlatformChange={setSelectedPlatforms}
          isLoading={aggregateRating.isLoading}
          error={
            aggregateRating.error ? getDashboardErrorMessage(aggregateRating.error) : undefined
          }
          onRetry={() => aggregateRating.refetch()}
        />

        <div className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
          <TopicDonut
            topicData={aggregateTopic.data}
            isLoading={aggregateTopic.isLoading}
            error={
              aggregateTopic.error ? getDashboardErrorMessage(aggregateTopic.error) : undefined
            }
            onRetry={() => aggregateTopic.refetch()}
          />
          <DifficultySplit
            difficultyData={aggregateDifficulty.data}
            isLoading={aggregateDifficulty.isLoading}
            error={
              aggregateDifficulty.error
                ? getDashboardErrorMessage(aggregateDifficulty.error)
                : undefined
            }
            onRetry={() => aggregateDifficulty.refetch()}
          />
        </div>

        <Heatmap
          activity={aggregateActivity.data?.activity}
          totalSubmissions={aggregateActivity.data?.total_submissions}
          isLoading={aggregateActivity.isLoading}
          error={
            aggregateActivity.error ? getDashboardErrorMessage(aggregateActivity.error) : undefined
          }
          onRetry={() => aggregateActivity.refetch()}
        />
      </div>
    </AppShell>
  );
}
