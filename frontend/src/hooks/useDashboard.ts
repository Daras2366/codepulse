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

export const dashboardQueryKeys = {
  profile: ["platform-profiles", "me"] as const,
  overview: (profileId: number) => ["dashboard", profileId, "overview"] as const,
  rating: (profileId: number) => ["dashboard", profileId, "rating"] as const,
  problems: (profileId: number) => ["dashboard", profileId, "problems"] as const,
  submissions: (profileId: number) => ["dashboard", profileId, "submissions"] as const,
  contests: (profileId: number) => ["dashboard", profileId, "contests"] as const,
};

export function useDashboard(selectedPlatform?: Platform) {
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
    queryKey:
      profileId === undefined ? ["dashboard", "overview"] : dashboardQueryKeys.overview(profileId),
    queryFn: () => getDashboardOverview(profileId!),
    enabled,
  });
  const rating = useQuery({
    queryKey:
      profileId === undefined ? ["dashboard", "rating"] : dashboardQueryKeys.rating(profileId),
    queryFn: () => getDashboardRating(profileId!),
    enabled,
  });
  const problems = useQuery({
    queryKey:
      profileId === undefined ? ["dashboard", "problems"] : dashboardQueryKeys.problems(profileId),
    queryFn: () => getDashboardProblems(profileId!),
    enabled,
  });
  const submissions = useQuery({
    queryKey:
      profileId === undefined
        ? ["dashboard", "submissions"]
        : dashboardQueryKeys.submissions(profileId),
    queryFn: () => getDashboardSubmissions(profileId!),
    enabled,
  });
  const contests = useQuery({
    queryKey:
      profileId === undefined ? ["dashboard", "contests"] : dashboardQueryKeys.contests(profileId),
    queryFn: () => getDashboardContests(profileId!),
    enabled,
  });

  return {
    authenticated,
    profile,
    profiles,
    overview,
    rating,
    problems,
    submissions,
    contests,
    refresh: () => queryClient.invalidateQueries({ queryKey: ["dashboard", profileId] }),
  };
}
