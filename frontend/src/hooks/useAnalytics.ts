import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import {
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
  aggregateRating: ["analytics", "aggregate", "rating"] as const,
};

type SelectedPlatform = Platform | "all";

export function useAnalytics(selectedPlatform?: SelectedPlatform) {
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

  // Auto-select platform based on availability and preference
  const getSelectedProfile = () => {
    if (!profilesQuery.data || profilesQuery.data.length === 0) return null;
    
    // If "all" is selected, return null to indicate aggregate mode
    if (selectedPlatform === "all") return null;
    
    // If a platform is explicitly selected, use it
    if (selectedPlatform) {
      return profilesQuery.data.find((item) => item.platform === selectedPlatform) || null;
    }
    
    // Default to Codeforces if available, otherwise first available
    return profilesQuery.data.find((item) => item.platform === "codeforces") || profilesQuery.data[0];
  };
  
  const profile = getSelectedProfile();
  const profileId = profile?.id;
  const enabled = authenticated && profileId !== undefined;

  const summary = useQuery({
    queryKey: analyticsQueryKeys.summary(profileId!),
    queryFn: () => getAnalyticsSummary(profileId!),
    enabled: enabled && profileId !== undefined,
  });

  const activity = useQuery({
    queryKey: analyticsQueryKeys.activity(profileId!),
    queryFn: () => getAnalyticsSubmissionActivity(profileId!),
    enabled: enabled && profileId !== undefined,
  });

  const difficulty = useQuery({
    queryKey: analyticsQueryKeys.difficulty(profileId!),
    queryFn: () => getAnalyticsDifficultyDistribution(profileId!),
    enabled: enabled && profileId !== undefined,
  });

  const rating = useQuery({
    queryKey: analyticsQueryKeys.rating(profileId!),
    queryFn: () => getAnalyticsRatingProgression(profileId!),
    enabled: enabled && profileId !== undefined,
  });

  const contests = useQuery({
    queryKey: analyticsQueryKeys.contests(profileId!),
    queryFn: () => getAnalyticsContestPerformance(profileId!),
    enabled: enabled && profileId !== undefined,
  });

  const aggregateRating = useQuery({
    queryKey: analyticsQueryKeys.aggregateRating,
    queryFn: getAggregateRatingProgression,
    enabled: authenticated,
  });

  return {
    authenticated,
    profile,
    profiles: profilesQuery.data ?? [],
    isLoadingProfiles: profilesQuery.isLoading,
    summary,
    activity,
    difficulty,
    rating,
    contests,
    aggregateRating,
    isAggregateMode: selectedPlatform === "all",
  };
}
