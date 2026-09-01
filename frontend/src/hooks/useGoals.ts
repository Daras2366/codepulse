import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { hasAccessToken } from "@/api/client";
import {
  createGoal,
  deleteGoal,
  getGoals,
  updateGoal,
  type GoalCreate,
  type GoalProgress,
  type GoalStatus,
  type GoalUpdate,
} from "@/api/goals";

export const goalsQueryKeys = {
  all: ["goals"] as const,
  filtered: (status?: GoalStatus) => ["goals", "filtered", status] as const,
};

export function useGoals(statusFilter?: GoalStatus) {
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
    queryKey: goalsQueryKeys.filtered(statusFilter),
    queryFn: () => getGoals(statusFilter),
    enabled: authenticated,
  });

  const progressList = goalsQuery.data ?? [];

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
    progressList,
    isLoading: goalsQuery.isLoading,
    error: goalsQuery.error,
    refetch: () => {
      void goalsQuery.refetch();
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
