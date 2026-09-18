import { useState } from "react";
import { createFileRoute, redirect } from "@tanstack/react-router";
import { Plus } from "lucide-react";

import { hasAccessToken } from "@/api/client";

import type { GoalProgress, GoalStatus } from "@/api/goals";
import { GoalCard } from "@/components/dashboard/GoalCard";
import { GoalModal } from "@/components/goals/GoalModal";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui-kit/motion";
import { useGoals } from "@/hooks/useGoals";

const title = "Goals — CodePulse";
const description =
  "Milestone cards for problem counts and targets, each with a rounded progress bar and status.";

export const Route = createFileRoute("/goals")({
  beforeLoad: () => {
    if (!hasAccessToken()) {
      throw redirect({ to: "/auth" });
    }
  },
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: Goals,
});

function Goals() {
  const [statusFilter, setStatusFilter] = useState<GoalStatus | undefined>(undefined);

  const {
    authenticated,
    progressList,
    isLoading,
    error,
    refetch,
    createGoal,
    isCreating,
    createError,
    updateGoal,
    isUpdating,
    updateError,
    deleteGoal,
    isDeleting,
  } = useGoals(statusFilter);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [editingGoal, setEditingGoal] = useState<GoalProgress | null>(null);

  const filterOptions = [
    { label: "All", value: undefined },
    { label: "Active", value: "active" as GoalStatus },
    { label: "Completed", value: "completed" as GoalStatus },
    { label: "Overdue", value: "overdue" as GoalStatus },
  ];

  if (!authenticated) {
    return (
      <AppShell title="Goals" subtitle="Small targets, kept visible.">
        <EmptyState
          title="Sign in to view your goals"
          description="Sign in with your CodePulse account to view and create targets."
        />
      </AppShell>
    );
  }

  if (isLoading) {
    return (
      <AppShell title="Goals" subtitle="Small targets, kept visible.">
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3" aria-busy>
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-48 w-full rounded-[20px]" />
          ))}
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell title="Goals" subtitle="Small targets, kept visible.">
        <ErrorState description="Could not load your goals right now." onRetry={refetch} />
      </AppShell>
    );
  }

  return (
    <AppShell title="Goals" subtitle="Small targets, kept visible.">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-2">
            {filterOptions.map((option) => (
              <button
                key={option.label}
                onClick={() => setStatusFilter(option.value)}
                className={`rounded-full px-4 py-2 text-caption font-semibold transition-colors ${
                  statusFilter === option.value
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:bg-muted/80"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
          <button
            onClick={() => setIsCreateOpen(true)}
            className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-caption font-semibold text-primary-foreground press"
          >
            <Plus className="h-4 w-4" strokeWidth={1.8} />
            New goal
          </button>
        </div>

        {progressList.length === 0 ? (
          <EmptyState
            title="No goals set yet"
            description="Create a daily, weekly, or monthly goal to track your competitive programming practice."
          />
        ) : (
          <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
            {progressList.map((progress) => (
              <GoalCard
                key={progress.id}
                progress={progress}
                onEdit={(goal) => setEditingGoal(goal)}
                onDelete={(id) => void deleteGoal(id)}
                isDeleting={isDeleting}
              />
            ))}
          </div>
        )}

        {/* Create modal */}
        <GoalModal
          mode="create"
          isOpen={isCreateOpen}
          onClose={() => setIsCreateOpen(false)}
          onSubmit={async (data) => {
            await createGoal(data);
          }}
          isSubmitting={isCreating}
          error={createError}
        />

        {/* Edit modal */}
        {editingGoal && (
          <GoalModal
            mode="edit"
            goal={editingGoal}
            isOpen={editingGoal !== null}
            onClose={() => setEditingGoal(null)}
            onSubmit={async (data) => {
              await updateGoal({ goalId: editingGoal.id, data });
            }}
            isSubmitting={isUpdating}
            error={updateError}
          />
        )}
      </div>
    </AppShell>
  );
}
