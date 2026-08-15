import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import type { Platform } from "@/api/dashboard";
import {
  getDashboardContests,
  getDashboardOverview,
  getDashboardProblems,
  getDashboardRating,
  getDashboardSubmissions,
} from "@/api/dashboard";
import { getMyPlatformProfiles } from "@/api/platform-profiles";
import { getAggregateRatingProgression } from "@/api/analytics";

export const dashboardQueryKeys = {
  profile: ["platform-profiles", "me"] as const,
  overview: (profileId: number) => ["dashboard", profileId, "overview"] as const,
  rating: (profileId: number) => ["dashboard", profileId, "rating"] as const,
  problems: (profileId: number) => ["dashboard", profileId, "problems"] as const,
  submissions: (profileId: number) => ["dashboard", profileId, "submissions"] as const,
  contests: (profileId: number) => ["dashboard", profileId, "contests"] as const,
  aggregateRating: ["dashboard", "aggregate", "rating"] as const,
};

type SelectedPlatform = Platform | "all";

export function useDashboard(selectedPlatform?: SelectedPlatform) {
  const queryClient = useQueryClient();
  const [authenticated, setAuthenticated] = useState(hasAccessToken);

  useEffect(() => {
    // Re-check authentication on mount and when storage changes
    setAuthenticated(hasAccessToken());

    const handleStorageChange = () => {
      setAuthenticated(hasAccessToken());
    };

    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("codepulse-auth-change", handleStorageChange);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("codepulse-auth-change", handleStorageChange);
    };
  }, []);

  const profiles = useQuery({
    queryKey: dashboardQueryKeys.profile,
    queryFn: getMyPlatformProfiles,
    enabled: authenticated,
  });
  
  // Auto-select platform based on availability and preference
  const getSelectedProfile = () => {
    if (!profiles.data || profiles.data.length === 0) return null;
    
    // If "all" is selected, return null to indicate aggregate mode
    if (selectedPlatform === "all") return null;
    
    // If a platform is explicitly selected, use it
    if (selectedPlatform) {
      return profiles.data.find((item) => item.platform === selectedPlatform) || null;
    }
    
    // Default to Codeforces if available, otherwise first available
    return profiles.data.find((item) => item.platform === "codeforces") || profiles.data[0];
  };
  
  const profile = getSelectedProfile();
  const profileId = profile?.id;
  const enabled = profileId !== undefined;

  const overview = useQuery({
    queryKey: dashboardQueryKeys.overview(profileId!),
    queryFn: () => getDashboardOverview(profileId!),
    enabled: enabled && profileId !== undefined,
  });
  const rating = useQuery({
    queryKey: dashboardQueryKeys.rating(profileId!),
    queryFn: () => getDashboardRating(profileId!),
    enabled: enabled && profileId !== undefined,
  });
  const problems = useQuery({
    queryKey: dashboardQueryKeys.problems(profileId!),
    queryFn: () => getDashboardProblems(profileId!),
    enabled: enabled && profileId !== undefined,
  });
  const submissions = useQuery({
    queryKey: dashboardQueryKeys.submissions(profileId!),
    queryFn: () => getDashboardSubmissions(profileId!),
    enabled: enabled && profileId !== undefined,
  });
  const contests = useQuery({
    queryKey: dashboardQueryKeys.contests(profileId!),
    queryFn: () => getDashboardContests(profileId!),
    enabled: enabled && profileId !== undefined,
  });

  const aggregateRating = useQuery({
    queryKey: dashboardQueryKeys.aggregateRating,
    queryFn: getAggregateRatingProgression,
    enabled: authenticated && selectedPlatform === "all",
  });

  // Calculate aggregate statistics for "All Platforms"
  const aggregateStats = profiles.data ? {
    totalProblemsSolved: profiles.data.reduce((sum, p) => sum + p.problems_solved, 0),
    totalContestsAttended: profiles.data.reduce((sum, p) => sum + p.contests_attended, 0),
    totalSubmissions: profiles.data.reduce((sum, p) => {
      // This would need to be calculated from actual submissions, but for now use 0
      return sum; 
    }, 0),
    platformCount: profiles.data.length,
    platforms: profiles.data.map(p => ({
      platform: p.platform,
      username: p.username,
      problemsSolved: p.problems_solved,
      contestsAttended: p.contests_attended,
      currentRating: p.current_rating,
      maxRating: p.max_rating,
    })),
  } : null;

  return {
    authenticated,
    profile,
    profiles,
    overview,
    rating,
    problems,
    submissions,
    contests,
    aggregateRating,
    aggregateStats,
    isAggregateMode: selectedPlatform === "all",
    refresh: () => queryClient.invalidateQueries({ queryKey: ["dashboard", profileId] }),
  };
}
