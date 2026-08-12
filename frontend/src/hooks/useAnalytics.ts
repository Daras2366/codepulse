import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import {
  getAnalyticsContestPerformance,
  getAnalyticsDifficultyDistribution,
  getAnalyticsRatingProgression,
  getAnalyticsSubmissionActivity,
  getAnalyticsSummary,
} from "@/api/analytics";
import { getMyPlatformProfiles } from "@/api/platform-profiles";

export const analyticsQueryKeys = {
  summary: (profileId: number) => ["analytics", profileId, "summary"] as const,
  activity: (profileId: number) => ["analytics", profileId, "activity"] as const,
  difficulty: (profileId: number) => ["analytics", profileId, "difficulty"] as const,
  rating: (profileId: number) => ["analytics", profileId, "rating"] as const,
  contests: (profileId: number) => ["analytics", profileId, "contests"] as const,
};

export function useAnalytics() {
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

  const profile = profilesQuery.data?.find((p) => p.platform === "codeforces");
  const profileId = profile?.id;
  const enabled = authenticated && profileId !== undefined;

  const summary = useQuery({
    queryKey: profileId ? analyticsQueryKeys.summary(profileId) : ["analytics", "summary"],
    queryFn: () => getAnalyticsSummary(profileId!),
    enabled,
  });

  const activity = useQuery({
    queryKey: profileId ? analyticsQueryKeys.activity(profileId) : ["analytics", "activity"],
    queryFn: () => getAnalyticsSubmissionActivity(profileId!),
    enabled,
  });

  const difficulty = useQuery({
    queryKey: profileId ? analyticsQueryKeys.difficulty(profileId) : ["analytics", "difficulty"],
    queryFn: () => getAnalyticsDifficultyDistribution(profileId!),
    enabled,
  });

  const rating = useQuery({
    queryKey: profileId ? analyticsQueryKeys.rating(profileId) : ["analytics", "rating"],
    queryFn: () => getAnalyticsRatingProgression(profileId!),
    enabled,
  });

  const contests = useQuery({
    queryKey: profileId ? analyticsQueryKeys.contests(profileId) : ["analytics", "contests"],
    queryFn: () => getAnalyticsContestPerformance(profileId!),
    enabled,
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
  };
}
