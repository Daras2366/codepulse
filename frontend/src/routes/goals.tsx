import { useState } from "react";
import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";

import { GoalCard } from "@/components/dashboard/GoalCard";
import { GoalModal } from "@/components/goals/GoalModal";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui-kit/motion";
import { useGoals } from "@/hooks/useGoals";

const title = "Goals — CodePulse";
const description =
  "Milestone cards for problem counts and targets, each with a rounded progress bar and status.";

export const Route = createFileRoute("/goals")({
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
  const {
    authenticated,
    progressList,
    isLoading,
    error,
    refetch,
    createGoal,
    isCreating,
    createError,
    deleteGoal,
    isDeleting,
  } = useGoals();

  const [isModalOpen, setIsModalOpen] = useState(false);

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

  const activeGoals = progressList.filter((g) => !g.is_achieved);
  const completedGoals = progressList.filter((g) => g.is_achieved);

  return (
    <AppShell title="Goals" subtitle="Small targets, kept visible.">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="text-body text-muted-foreground">
            {activeGoals.length} active goal{activeGoals.length === 1 ? "" : "s"} ·{" "}
            {completedGoals.length} achieved
          </p>
          <button
            onClick={() => setIsModalOpen(true)}
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
                onDelete={(id) => void deleteGoal(id)}
                isDeleting={isDeleting}
              />
            ))}
          </div>
        )}

        <GoalModal
          isOpen={isModalOpen}
          onClose={() => setIsModalOpen(false)}
          onSubmit={async (data) => {
            await createGoal(data);
          }}
          isSubmitting={isCreating}
          error={createError}
        />
      </div>
    </AppShell>
  );
}
