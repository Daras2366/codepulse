import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";

import { getDashboardErrorMessage } from "@/api/client";
import { Heatmap } from "@/components/dashboard/Heatmap";
import { RatingChart } from "@/components/dashboard/RatingChart";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui-kit/motion";
import { Panel } from "@/components/ui-kit/Panel";
import { useAnalytics } from "@/hooks/useAnalytics";
import type { Platform } from "@/api/dashboard";

const title = "Analytics — CodePulse";
const description =
  "Rating progress, difficulty distribution and submission heatmaps across your competitive programming history.";

export const Route = createFileRoute("/analytics")({
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

const difficultyColors: Record<string, string> = {
  Easy: "var(--pastel-green)",
  Medium: "var(--pastel-yellow)",
  Hard: "var(--pastel-pink)",
};

function Analytics() {
  const [selectedPlatform, setSelectedPlatform] = useState<Platform | "all" | null>(null);
  const {
    authenticated,
    profile,
    profiles,
    isLoadingProfiles,
    rating,
    difficulty,
    activity,
    aggregateRating,
    isAggregateMode,
  } = useAnalytics(selectedPlatform || undefined);

  if (!authenticated) {
    return (
      <AppShell title="Analytics" subtitle="Slice your history by platform and time range.">
        <EmptyState
          title="Sign in to view your analytics"
          description="Authenticate with your CodePulse session to inspect rating, difficulty, and activity trends."
        />
      </AppShell>
    );
  }

  if (isLoadingProfiles) {
    return (
      <AppShell title="Analytics" subtitle="Slice your history by platform and time range.">
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

  if ((!profile && !profiles) || profiles.length === 0) {
    return (
      <AppShell title="Analytics" subtitle="Slice your history by platform and time range.">
        <EmptyState
          title="No platform profiles connected"
          description="Connect and sync a platform profile to unlock detailed performance analytics."
        />
      </AppShell>
    );
  }

  const difficultyItems = difficulty.data?.solved_by_difficulty ?? [];
  const totalSolved = difficultyItems.reduce((sum, d) => sum + d.solved_count, 0);

  // Get available platforms for selector
  const availablePlatforms = profiles.map((p) => p.platform);
  const hasMultiplePlatforms = availablePlatforms.length > 1;

  return (
    <AppShell
      title="Analytics"
      subtitle="Slice your history by rating progression, difficulty, and activity."
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
                  (selectedPlatform === null && platform === profile?.platform) ||
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

        <RatingChart
          rating={selectedPlatform === "all" ? undefined : rating.data}
          aggregateRating={selectedPlatform === "all" ? aggregateRating.data : undefined}
          platform={selectedPlatform === "all" ? undefined : selectedPlatform}
          isLoading={selectedPlatform === "all" ? aggregateRating.isLoading : rating.isLoading}
          error={
            selectedPlatform === "all"
              ? aggregateRating.error
                ? getDashboardErrorMessage(aggregateRating.error)
                : undefined
              : rating.error
                ? getDashboardErrorMessage(rating.error)
                : undefined
          }
          onRetry={() => {
            if (selectedPlatform === "all") {
              aggregateRating.refetch();
            } else {
              rating.refetch();
            }
          }}
        />

        {!selectedPlatform || selectedPlatform !== "all" ? (
          <>
            <div className="grid gap-6 xl:grid-cols-[1.2fr_1fr]">
              <Panel title="Difficulty split" caption="Solved problems by difficulty band">
                {difficulty.isLoading ? (
                  <div className="space-y-4 py-4">
                    <Skeleton className="h-4 w-full rounded" />
                    <Skeleton className="h-4 w-full rounded" />
                    <Skeleton className="h-4 w-full rounded" />
                  </div>
                ) : difficulty.error ? (
                  <ErrorState
                    description={getDashboardErrorMessage(difficulty.error)}
                    onRetry={() => difficulty.refetch()}
                  />
                ) : difficultyItems.length === 0 ? (
                  <EmptyState
                    title="No difficulty breakdown yet"
                    description="Sync your submissions to categorize solved problems by difficulty."
                  />
                ) : (
                  <ul className="space-y-5">
                    {difficultyItems.map((d) => {
                      const pct =
                        totalSolved > 0 ? Math.round((d.solved_count / totalSolved) * 100) : 0;
                      const color = difficultyColors[d.difficulty] ?? "var(--pastel-blue)";
                      return (
                        <li key={d.difficulty}>
                          <div className="mb-2 flex items-center justify-between">
                            <span className="text-caption text-muted-foreground">
                              {d.difficulty}
                            </span>
                            <span className="text-caption font-semibold">
                              {d.solved_count.toLocaleString()} · {pct}%
                            </span>
                          </div>
                          <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                            <div
                              className="h-full rounded-full transition-all duration-500"
                              style={{ width: `${pct}%`, background: color }}
                            />
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </Panel>

              <Panel title="Connected Platforms" caption="Real solved count per platform profile">
                <div className="space-y-3">
                  {profiles.map((p) => (
                    <div
                      key={p.id}
                      className="flex items-center justify-between rounded-2xl bg-muted px-4 py-3"
                    >
                      <span className="text-caption font-semibold capitalize">{p.platform}</span>
                      <span className="text-caption text-muted-foreground">
                        {p.problems_solved.toLocaleString()} solved
                      </span>
                    </div>
                  ))}
                </div>
              </Panel>

              <Panel title="Activity heatmap" caption="Submission activity over time">
                <Heatmap
                  activity={activity.data?.activity}
                  isLoading={activity.isLoading}
                  error={activity.error ? getDashboardErrorMessage(activity.error) : undefined}
                  onRetry={() => activity.refetch()}
                />
              </Panel>
            </div>
          </>
        ) : null}
      </div>
    </AppShell>
  );
}
