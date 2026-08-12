import { useQuery } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import { getCurrentUser } from "@/api/user";

export const userQueryKeys = {
  me: ["user", "me"] as const,
};

export function useUser() {
  const authenticated = hasAccessToken();

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
