import { createFileRoute, redirect } from "@tanstack/react-router";
import { useState } from "react";

import { getDashboardErrorMessage, hasAccessToken } from "@/api/client";
import { getDashboardContests } from "@/api/dashboard";
import { ContestsTable, Leaderboard } from "@/components/dashboard/Tables";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, Skeleton } from "@/components/ui-kit/motion";
import { getMyPlatformProfiles } from "@/api/platform-profiles";
import { useQuery } from "@tanstack/react-query";
import type { Platform } from "@/api/dashboard";

const title = "Contests — CodePulse";
const description = "Every rated contest you entered, with rank, rating delta and status.";

export const Route = createFileRoute("/contests")({
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
  component: Contests,
});

function Contests() {
  const [selectedPlatform, setSelectedPlatform] = useState<Platform | "all" | null>(null);

  const profilesQuery = useQuery({
    queryKey: ["platform-profiles", "me"],
    queryFn: getMyPlatformProfiles,
  });

  const authenticated = !!profilesQuery.data;
  const isLoadingProfiles = profilesQuery.isLoading;
  const profiles = profilesQuery.data || [];

  // Get selected profile based on platform selection
  const selectedProfile =
    selectedPlatform === "all"
      ? null
      : profiles.find((p) => p.platform === selectedPlatform) || profiles[0];

  const contestsQuery = useQuery({
    queryKey: ["dashboard", "contests", selectedProfile?.id],
    queryFn: () => getDashboardContests(selectedProfile!.id),
    enabled: !!selectedProfile,
  });

  if (!authenticated) {
    return (
      <AppShell title="Contests" subtitle="Rated rounds, ranks and rating movement.">
        <EmptyState
          title="Sign in to view contests"
          description="Sign in with your CodePulse account to view your rated contest history."
        />
      </AppShell>
    );
  }

  if (isLoadingProfiles) {
    return (
      <AppShell title="Contests" subtitle="Rated rounds, ranks and rating movement.">
        <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]" aria-busy>
          <Skeleton className="h-[360px] w-full rounded-2xl" />
          <Skeleton className="h-[360px] w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  if (profiles.length === 0) {
    return (
      <AppShell title="Contests" subtitle="Rated rounds, ranks and rating movement.">
        <EmptyState
          title="No platform profiles connected"
          description="Connect and sync a platform profile to view contest performance."
        />
      </AppShell>
    );
  }

  const availablePlatforms = profiles.map((p) => p.platform);
  const hasMultiplePlatforms = availablePlatforms.length > 1;

  return (
    <AppShell title="Contests" subtitle="Rated rounds, ranks and rating movement.">
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
              All
            </button>
            {availablePlatforms.map((platform) => (
              <button
                key={platform}
                onClick={() => setSelectedPlatform(selectedPlatform === platform ? null : platform)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  (selectedPlatform === null && platform === selectedProfile?.platform) ||
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

        <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
          {selectedPlatform === "all" ? (
            <EmptyState
              title="Select a platform"
              description="Choose a specific platform to view contest history, or view all contests combined."
            />
          ) : (
            <ContestsTable
              contests={contestsQuery.data}
              isLoading={contestsQuery.isLoading}
              error={
                contestsQuery.error ? getDashboardErrorMessage(contestsQuery.error) : undefined
              }
              onRetry={() => contestsQuery.refetch()}
            />
          )}
          <Leaderboard />
        </div>
      </div>
    </AppShell>
  );
}
