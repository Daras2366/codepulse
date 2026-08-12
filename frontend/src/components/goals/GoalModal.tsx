import { useState } from "react";
import { X } from "lucide-react";

import { getDashboardErrorMessage } from "@/api/client";
import type { GoalCreate, GoalType } from "@/api/goals";
import { ActionButton } from "@/components/ui-kit/motion";

export function GoalModal({
  isOpen,
  onClose,
  onSubmit,
  isSubmitting,
  error,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: (data: GoalCreate) => Promise<void>;
  isSubmitting: boolean;
  error: unknown;
}) {
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [goalType, setGoalType] = useState<GoalType>("weekly");
  const [targetValue, setTargetValue] = useState("10");

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const target = parseInt(targetValue, 10);
    if (!title.trim() || isNaN(target) || target <= 0) return;

    try {
      await onSubmit({
        title: title.trim(),
        description: description.trim() || undefined,
        goal_type: goalType,
        target_value: target,
      });
      setTitle("");
      setDescription("");
      setTargetValue("10");
      onClose();
    } catch {
      // Error handles in hook
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="surface-card w-full max-w-md p-6">
        <div className="flex items-center justify-between border-b border-border pb-4">
          <h2 className="text-h3 font-semibold">Create new goal</h2>
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
              {isSubmitting ? "Creating…" : "Create goal"}
            </ActionButton>
          </div>
        </form>
      </div>
    </div>
  );
}
