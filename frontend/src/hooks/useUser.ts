import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import { getCurrentUser } from "@/api/user";

export const userQueryKeys = {
  me: ["user", "me"] as const,
};

export function useUser() {
  const [authenticated, setAuthenticated] = useState(hasAccessToken);

  useEffect(() => {
    // Re-check authentication on mount and when storage changes
    setAuthenticated(hasAccessToken());

    const handleStorageChange = () => {
      setAuthenticated(hasAccessToken());
    };

    // Listen for storage events from other tabs/windows
    window.addEventListener("storage", handleStorageChange);

    // Custom event for same-window localStorage changes
    window.addEventListener("codepulse-auth-change", handleStorageChange);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("codepulse-auth-change", handleStorageChange);
    };
  }, []);

  const query = useQuery({
    queryKey: userQueryKeys.me,
    queryFn: getCurrentUser,
    enabled: authenticated,
  });

  return {
    authenticated,
    user: query.data ?? null,
    isLoading: query.isLoading,
    error: query.error,
  };
}
