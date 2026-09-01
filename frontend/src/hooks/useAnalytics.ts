import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import {
  getAggregateDifficultyDistribution,
  getAggregateSubmissionActivity,
  getAggregateTopicBreakdown,
  getAnalyticsContestPerformance,
  getAnalyticsDifficultyDistribution,
  getAnalyticsRatingProgression,
  getAnalyticsSubmissionActivity,
  getAnalyticsSummary,
  getAggregateRatingProgression,
} from "@/api/analytics";
import { getMyPlatformProfiles } from "@/api/platform-profiles";
import type { Platform } from "@/api/dashboard";

export const analyticsQueryKeys = {
  summary: (profileId: number) => ["analytics", profileId, "summary"] as const,
  activity: (profileId: number) => ["analytics", profileId, "activity"] as const,
  difficulty: (profileId: number) => ["analytics", profileId, "difficulty"] as const,
  rating: (profileId: number) => ["analytics", profileId, "rating"] as const,
  contests: (profileId: number) => ["analytics", profileId, "contests"] as const,
  aggregateRating: (platforms: Platform[]) =>
    ["analytics", "aggregate", "rating", [...platforms].sort().join(",")] as const,
  aggregateTopic: (platforms: Platform[]) =>
    ["analytics", "aggregate", "topic", [...platforms].sort().join(",")] as const,
  aggregateDifficulty: (platforms: Platform[]) =>
    ["analytics", "aggregate", "difficulty", [...platforms].sort().join(",")] as const,
  aggregateActivity: (platforms: Platform[], rangeDays?: number) =>
    ["analytics", "aggregate", "activity", [...platforms].sort().join(","), rangeDays] as const,
};

type TimeRange = "7D" | "30D" | "90D" | "1Y" | "All";

const RANGE_DAYS: Record<TimeRange, number | null> = {
  "7D": 7,
  "30D": 30,
  "90D": 90,
  "1Y": 365,
  All: null,
};

export function useAnalytics(selectedPlatforms: Platform[] = [], timeRange: TimeRange = "All") {
  const [authenticated, setAuthenticated] = useState(hasAccessToken);

  useEffect(() => {
    setAuthenticated(hasAccessToken());
    const handleStorageChange = () => setAuthenticated(hasAccessToken());
    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("codepulse-auth-change", handleStorageChange);
    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("codepulse-auth-change", handleStorageChange);
    };
  }, []);

  const profilesQuery = useQuery({
    queryKey: ["platform-profiles", "me"],
    queryFn: getMyPlatformProfiles,
    enabled: authenticated,
  });

  const profiles = profilesQuery.data ?? [];
  const isLoadingProfiles = profilesQuery.isLoading;

  // Use selected platforms if provided, otherwise use all available platforms
  const activePlatforms =
    selectedPlatforms.length > 0 ? selectedPlatforms : profiles.map((p) => p.platform);
  const rangeDays = RANGE_DAYS[timeRange];

  // Aggregate queries (multi-platform)
  const aggregateRating = useQuery({
    queryKey: analyticsQueryKeys.aggregateRating(activePlatforms),
    queryFn: () => getAggregateRatingProgression(activePlatforms),
    enabled: authenticated && activePlatforms.length > 0,
  });

  const aggregateTopic = useQuery({
    queryKey: analyticsQueryKeys.aggregateTopic(activePlatforms),
    queryFn: () => getAggregateTopicBreakdown(activePlatforms),
    enabled: authenticated && activePlatforms.length > 0,
  });

  const aggregateDifficulty = useQuery({
    queryKey: analyticsQueryKeys.aggregateDifficulty(activePlatforms),
    queryFn: () => getAggregateDifficultyDistribution(activePlatforms),
    enabled: authenticated && activePlatforms.length > 0,
  });

  const aggregateActivity = useQuery({
    queryKey: analyticsQueryKeys.aggregateActivity(activePlatforms, rangeDays),
    queryFn: () => getAggregateSubmissionActivity(activePlatforms, rangeDays),
    enabled: authenticated && activePlatforms.length > 0,
  });

  return {
    authenticated,
    profiles,
    isLoadingProfiles,
    aggregateRating,
    aggregateTopic,
    aggregateDifficulty,
    aggregateActivity,
  };
}
