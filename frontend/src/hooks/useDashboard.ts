import { useEffect, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import { getAggregateDashboard } from "@/api/dashboard";

export const dashboardQueryKeys = {
  aggregate: ["dashboard", "aggregate"] as const,
};

/**
 * Dashboard data is always centralized: the API aggregates every platform
 * connected to the authenticated user. Per-platform filtering remains an
 * Analytics-only concern.
 */
export function useDashboard() {
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

  const aggregate = useQuery({
    queryKey: dashboardQueryKeys.aggregate,
    queryFn: () => getAggregateDashboard(),
    enabled: authenticated,
  });

  return {
    authenticated,
    aggregate,
    refresh: () => queryClient.invalidateQueries({ queryKey: dashboardQueryKeys.aggregate }),
  };
}
