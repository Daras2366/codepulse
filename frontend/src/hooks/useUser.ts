import { useQuery } from "@tanstack/react-query";

import { getCurrentUser } from "@/api/user";
import { useAuth } from "@/contexts/AuthContext";

export const userQueryKeys = {
  me: ["user", "me"] as const,
};

export function useUser() {
  const { isAuthenticated, isLoading: authLoading, user: authUser } = useAuth();

  const query = useQuery({
    queryKey: userQueryKeys.me,
    queryFn: getCurrentUser,
    enabled: isAuthenticated,
  });

  return {
    authenticated: isAuthenticated,
    user: query.data ?? authUser,
    isLoading: authLoading || query.isLoading,
    error: query.error,
  };
}
