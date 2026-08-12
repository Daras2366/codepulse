import { Trash2 } from "lucide-react";

import type { GoalProgress } from "@/api/goals";
import { ActionButton, AnimatedBar, AnimatedCounter } from "@/components/ui-kit/motion";
import { cn } from "@/lib/utils";

export function ProgressBar({ value, color }: { value: number; color: string }) {
  return <AnimatedBar value={value} color={color} />;
}

export function GoalCard({
  progress,
  onDelete,
  isDeleting,
}: {
  progress: GoalProgress;
  onDelete?: (id: number) => void;
  isDeleting?: boolean;
}) {
  const pct = Math.min(100, Math.max(0, Math.round(progress.percentage)));
  const isAchieved = progress.is_achieved || pct >= 100;
  const tint = isAchieved ? "bg-green-soft" : "bg-card";
  const bar = isAchieved ? "var(--success)" : "var(--pastel-blue)";

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
            {progress.calculated_progress.toLocaleString()} of{" "}
            {progress.target_value.toLocaleString()}
          </p>

          {onDelete && (
            <ActionButton
              variant="quiet"
              className="h-7 w-7 p-0 opacity-0 transition-opacity group-hover:opacity-100"
              aria-label="Delete goal"
              disabled={isDeleting}
              onClick={() => onDelete(progress.id)}
            >
              <Trash2
                className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive"
                strokeWidth={1.8}
              />
            </ActionButton>
          )}
        </div>
      </div>
    </article>
  );
}
