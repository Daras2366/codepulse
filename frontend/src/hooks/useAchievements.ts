import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import { evaluateAchievements, getAchievements, getMyAchievements } from "@/api/achievements";

export const achievementsQueryKeys = {
  catalog: ["achievements", "catalog"] as const,
  mine: ["achievements", "mine"] as const,
};

export function useAchievements() {
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

  const catalogQuery = useQuery({
    queryKey: achievementsQueryKeys.catalog,
    queryFn: getAchievements,
  });

  const mineQuery = useQuery({
    queryKey: achievementsQueryKeys.mine,
    queryFn: getMyAchievements,
    enabled: authenticated,
  });

  const evalMutation = useMutation({
    mutationFn: evaluateAchievements,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: achievementsQueryKeys.mine });
    },
  });

  return {
    authenticated,
    catalog: catalogQuery.data ?? [],
    earned: mineQuery.data ?? [],
    isLoading: catalogQuery.isLoading || (authenticated && mineQuery.isLoading),
    error: catalogQuery.error || mineQuery.error,
    refetch: () => {
      void catalogQuery.refetch();
      void mineQuery.refetch();
    },
    evaluate: evalMutation.mutateAsync,
    isEvaluating: evalMutation.isPending,
    evalResult: evalMutation.data,
    evalError: evalMutation.error,
  };
}
