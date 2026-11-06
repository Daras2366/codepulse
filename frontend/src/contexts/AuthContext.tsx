import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import { getCurrentUser } from "@/api/user";
import { userQueryKeys } from "@/hooks/useUser";

interface AuthContextValue {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: Awaited<ReturnType<typeof getCurrentUser>> | null;
  refetch: () => void;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [isClient, setIsClient] = useState(false);
  const [hasToken, setHasToken] = useState(false);

  // Initialize on client side only
  useEffect(() => {
    setIsClient(true);
    setHasToken(hasAccessToken());

    const handleStorageChange = () => {
      setHasToken(hasAccessToken());
    };

    window.addEventListener("storage", handleStorageChange);
    window.addEventListener("codepulse-auth-change", handleStorageChange);

    return () => {
      window.removeEventListener("storage", handleStorageChange);
      window.removeEventListener("codepulse-auth-change", handleStorageChange);
    };
  }, []);

  // Only fetch user if we have a token and are on the client
  const query = useQuery({
    queryKey: userQueryKeys.me,
    queryFn: getCurrentUser,
    enabled: isClient && hasToken,
    retry: false,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });

  const isAuthenticated = isClient && hasToken && query.data !== null && !query.error;

  return (
    <AuthContext.Provider
      value={{
        isAuthenticated,
        isLoading: query.isLoading,
        user: query.data ?? null,
        refetch: query.refetch,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
