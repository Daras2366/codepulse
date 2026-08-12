import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import {
  createGoal,
  deleteGoal,
  getGoalProgress,
  getGoals,
  updateGoal,
  type GoalCreate,
  type GoalProgress,
  type GoalUpdate,
} from "@/api/goals";

export const goalsQueryKeys = {
  all: ["goals"] as const,
  progress: (goalId: number) => ["goals", goalId, "progress"] as const,
};

export function useGoals() {
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

  const goalsQuery = useQuery({
    queryKey: goalsQueryKeys.all,
    queryFn: getGoals,
    enabled: authenticated,
  });

  const goalsList = goalsQuery.data ?? [];

  // Query progress for each goal
  const progressQueries = useQuery({
    queryKey: ["goals", "all-progress", goalsList.map((g) => g.id)],
    queryFn: async () => {
      if (goalsList.length === 0) return [];
      const results = await Promise.all(
        goalsList.map((g) => getGoalProgress(g.id).catch(() => null)),
      );
      return results.filter((r): r is GoalProgress => r !== null);
    },
    enabled: authenticated && goalsList.length > 0,
  });

  const createMutation = useMutation({
    mutationFn: (data: GoalCreate) => createGoal(data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: goalsQueryKeys.all });
    },
  });

  const updateMutation = useMutation({
    mutationFn: ({ goalId, data }: { goalId: number; data: GoalUpdate }) =>
      updateGoal(goalId, data),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: goalsQueryKeys.all });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (goalId: number) => deleteGoal(goalId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: goalsQueryKeys.all });
    },
  });

  return {
    authenticated,
    goals: goalsList,
    progressList: progressQueries.data ?? [],
    isLoading: goalsQuery.isLoading || (goalsList.length > 0 && progressQueries.isLoading),
    error: goalsQuery.error || progressQueries.error,
    refetch: () => {
      void goalsQuery.refetch();
      void progressQueries.refetch();
    },
    createGoal: createMutation.mutateAsync,
    isCreating: createMutation.isPending,
    createError: createMutation.error,
    updateGoal: updateMutation.mutateAsync,
    isUpdating: updateMutation.isPending,
    updateError: updateMutation.error,
    deleteGoal: deleteMutation.mutateAsync,
    isDeleting: deleteMutation.isPending,
  };
}
