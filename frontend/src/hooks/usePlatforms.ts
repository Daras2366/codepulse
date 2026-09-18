import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import { syncPlatformProfile, type Platform, type SyncResult } from "@/api/dashboard";
import { getMyPlatformProfiles, type PlatformProfile } from "@/api/platform-profiles";

export const platformQueryKeys = {
  profiles: ["platform-profiles", "me"] as const,
};

export function usePlatforms() {
  const queryClient = useQueryClient();
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
    queryKey: platformQueryKeys.profiles,
    queryFn: getMyPlatformProfiles,
    enabled: authenticated,
  });

  const syncMutation = useMutation({
    mutationFn: ({ platform, profileId }: { platform: Platform; profileId: number }) =>
      syncPlatformProfile(platform, profileId),
    onSuccess: () => {
      // Invalidate all relevant React Query data after a successful sync
      void queryClient.invalidateQueries({ queryKey: ["platform-profiles"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      void queryClient.invalidateQueries({ queryKey: ["analytics"] });
      void queryClient.invalidateQueries({ queryKey: ["submissions"] });
      void queryClient.invalidateQueries({ queryKey: ["contests"] });
      void queryClient.invalidateQueries({ queryKey: ["achievements"] });
      void queryClient.invalidateQueries({ queryKey: ["goals"] });
    },
  });

  return {
    authenticated,
    profiles: profilesQuery.data ?? [],
    isLoading: profilesQuery.isLoading,
    error: profilesQuery.error,
    refetch: profilesQuery.refetch,
    syncProfile: (profile: PlatformProfile) =>
      syncMutation.mutateAsync({ platform: profile.platform, profileId: profile.id }),
    isSyncing: syncMutation.isPending,
    syncError: syncMutation.error,
    syncResult: syncMutation.data as SyncResult | undefined,
  };
}
