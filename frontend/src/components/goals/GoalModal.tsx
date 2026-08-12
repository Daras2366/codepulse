import { useEffect, useState } from "react";
import { X } from "lucide-react";

import { getDashboardErrorMessage } from "@/api/client";
import type { GoalCreate, GoalProgress, GoalType, GoalUpdate } from "@/api/goals";
import { ActionButton } from "@/components/ui-kit/motion";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface CreateProps {
  mode: "create";
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: GoalCreate) => Promise<void>;
  isSubmitting: boolean;
  error: unknown;
}

interface EditProps {
  mode: "edit";
  goal: GoalProgress;
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: GoalUpdate) => Promise<void>;
  isSubmitting: boolean;
  error: unknown;
}

type GoalModalProps = CreateProps | EditProps;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function GoalModal(props: GoalModalProps) {
  const { isOpen, onClose, isSubmitting, error } = props;
  const isEditing = props.mode === "edit";

  const initial = isEditing
    ? {
        title: props.goal.title,
        description: props.goal.description ?? "",
        goalType: props.goal.goal_type as GoalType,
        targetValue: String(props.goal.target_value),
      }
    : { title: "", description: "", goalType: "weekly" as GoalType, targetValue: "10" };

  const [title, setTitle] = useState(initial.title);
  const [description, setDescription] = useState(initial.description);
  const [goalType, setGoalType] = useState<GoalType>(initial.goalType);
  const [targetValue, setTargetValue] = useState(initial.targetValue);

  // Re-sync form when the goal being edited changes
  useEffect(() => {
    if (isEditing) {
      setTitle(props.goal.title);
      setDescription(props.goal.description ?? "");
      setGoalType(props.goal.goal_type as GoalType);
      setTargetValue(String(props.goal.target_value));
    } else {
      setTitle("");
      setDescription("");
      setGoalType("weekly");
      setTargetValue("10");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const target = parseInt(targetValue, 10);
    if (!title.trim() || isNaN(target) || target <= 0) return;

    try {
      if (isEditing) {
        await (props as EditProps).onSubmit({
          title: title.trim(),
          description: description.trim() || undefined,
          goal_type: goalType,
          target_value: target,
        });
      } else {
        await (props as CreateProps).onSubmit({
          title: title.trim(),
          description: description.trim() || undefined,
          goal_type: goalType,
          target_value: target,
        });
      }
      onClose();
    } catch {
      // Error handled in hook
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="surface-card w-full max-w-md p-6">
        <div className="flex items-center justify-between border-b border-border pb-4">
          <h2 className="text-h3 font-semibold">{isEditing ? "Edit goal" : "Create new goal"}</h2>
          <button
            onClick={onClose}
            className="rounded-full p-1 text-muted-foreground hover:bg-muted"
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {error ? (
          <div className="mt-4 rounded-xl bg-destructive/10 p-3 text-caption text-destructive">
            {getDashboardErrorMessage(error)}
          </div>
        ) : null}

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div>
            <label className="text-label block uppercase text-subtle">Title</label>
            <input
              type="text"
              required
              placeholder="e.g. Solve 15 Medium problems"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="mt-1 h-11 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
            />
          </div>

          <div>
            <label className="text-label block uppercase text-subtle">Goal cadence</label>
            <select
              value={goalType}
              onChange={(e) => setGoalType(e.target.value as GoalType)}
              className="mt-1 h-11 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
            >
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>

          <div>
            <label className="text-label block uppercase text-subtle">Target count</label>
            <input
              type="number"
              min={1}
              required
              value={targetValue}
              onChange={(e) => setTargetValue(e.target.value)}
              className="mt-1 h-11 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
            />
          </div>

          <div>
            <label className="text-label block uppercase text-subtle">Description (optional)</label>
            <input
              type="text"
              placeholder="Optional notes or details"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="mt-1 h-11 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
            />
          </div>

          <div className="mt-6 flex justify-end gap-3 pt-2">
            <ActionButton variant="quiet" type="button" onClick={onClose}>
              Cancel
            </ActionButton>
            <ActionButton type="submit" disabled={isSubmitting}>
              {isSubmitting
                ? isEditing
                  ? "Saving…"
                  : "Creating…"
                : isEditing
                  ? "Save changes"
                  : "Create goal"}
            </ActionButton>
          </div>
        </form>
      </div>
    </div>
  );
}
