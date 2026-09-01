import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";

import type { GoalProgress } from "@/api/goals";
import { ActionButton, AnimatedBar, AnimatedCounter } from "@/components/ui-kit/motion";
import { DeleteConfirmDialog } from "@/components/goals/DeleteConfirmDialog";
import { cn } from "@/lib/utils";

export function ProgressBar({ value, color }: { value: number; color: string }) {
  return <AnimatedBar value={value} color={color} />;
}

export function GoalCard({
  progress,
  onEdit,
  onDelete,
  isDeleting,
}: {
  progress: GoalProgress;
  onEdit?: (goal: GoalProgress) => void;
  onDelete?: (id: number) => void;
  isDeleting?: boolean;
}) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const pct = Math.min(100, Math.max(0, Math.round(progress.progress_percentage)));
  const isAchieved = progress.is_completed || pct >= 100;
  const tint = isAchieved ? "bg-green-soft" : "bg-card";
  const bar = isAchieved ? "var(--success)" : "var(--pastel-blue)";

  const handleDelete = () => {
    if (!onDelete) return;
    setShowDeleteConfirm(true);
  };

  const confirmDelete = () => {
    if (onDelete) {
      onDelete(progress.id);
    }
    setShowDeleteConfirm(false);
  };

  return (
    <article
      className={cn(
        "lift group relative flex flex-col justify-between rounded-[20px] border border-border p-6",
        tint,
      )}
    >
      <div>
        <div className="flex items-start justify-between gap-4">
          <div>
            <span className="text-label uppercase tracking-wider text-subtle">
              {progress.goal_type} goal
            </span>
            <h3 className="text-card-title mt-0.5">{progress.title}</h3>
          </div>
          <span className="text-caption font-semibold">
            <AnimatedCounter value={pct} suffix="%" />
          </span>
        </div>
        {progress.description && (
          <p className="text-caption mt-1.5 text-muted-foreground">{progress.description}</p>
        )}
      </div>

      <div className="mt-5">
        <AnimatedBar value={pct} color={bar} />
        <div className="mt-3 flex items-center justify-between">
          <p className="text-label text-subtle">
            {progress.current_value.toLocaleString()} of {progress.target_value.toLocaleString()}
            {progress.goal_type === "consistency" && " active days"}
            {progress.remaining > 0 && (
              <span className="ml-1 text-subtle/70">· {progress.remaining} remaining</span>
            )}
          </p>
          <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            {onEdit && (
              <ActionButton
                variant="quiet"
                className="h-7 w-7 p-0"
                aria-label="Edit goal"
                onClick={() => onEdit(progress)}
              >
                <Pencil
                  className="h-3.5 w-3.5 text-muted-foreground hover:text-foreground"
                  strokeWidth={1.8}
                />
              </ActionButton>
            )}
            {onDelete && (
              <ActionButton
                variant="quiet"
                className="h-7 w-7 p-0"
                aria-label="Delete goal"
                disabled={isDeleting}
                onClick={handleDelete}
              >
                <Trash2
                  className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive"
                  strokeWidth={1.8}
                />
              </ActionButton>
            )}
          </div>
        </div>
      </div>

      {/* Delete confirmation dialog */}
      <DeleteConfirmDialog
        isOpen={showDeleteConfirm}
        goalTitle={progress.title}
        onConfirm={confirmDelete}
        onCancel={() => setShowDeleteConfirm(false)}
        isDeleting={isDeleting}
      />
    </article>
  );
}
