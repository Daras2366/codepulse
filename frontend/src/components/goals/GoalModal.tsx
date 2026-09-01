import { useEffect, useState, useRef } from "react";
import { X } from "lucide-react";

import { getDashboardErrorMessage } from "@/api/client";
import type { GoalCreate, GoalProgress, GoalType, GoalUpdate, Platform } from "@/api/goals";
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
  const formRef = useRef<HTMLFormElement>(null);

  const initial = isEditing
    ? {
        title: props.goal.title,
        description: props.goal.description ?? "",
        goalType: props.goal.goal_type as GoalType,
        targetValue: String(props.goal.target_value),
        platform: props.goal.platform ?? undefined,
        topicSlug: props.goal.topic_slug ?? "",
        topicName: props.goal.topic_name ?? "",
        difficultyFilter: props.goal.difficulty_filter ?? undefined,
        deadline: props.goal.deadline ?? "",
        startDate: props.goal.start_date ?? "",
      }
    : {
        title: "",
        description: "",
        goalType: "problems" as GoalType,
        targetValue: "10",
        platform: undefined,
        topicSlug: "",
        topicName: "",
        difficultyFilter: undefined,
        deadline: "",
        startDate: "",
      };

  const [title, setTitle] = useState(initial.title);
  const [description, setDescription] = useState(initial.description);
  const [goalType, setGoalType] = useState<GoalType>(initial.goalType);
  const [targetValue, setTargetValue] = useState(initial.targetValue);
  const [platform, setPlatform] = useState<Platform | undefined>(initial.platform);
  const [topicSlug, setTopicSlug] = useState(initial.topicSlug);
  const [topicName, setTopicName] = useState(initial.topicName);
  const [difficultyFilter, setDifficultyFilter] = useState<"Easy" | "Medium" | "Hard" | undefined>(
    initial.difficultyFilter,
  );
  const [deadline, setDeadline] = useState(initial.deadline);
  const [startDate, setStartDate] = useState(initial.startDate);

  // Re-sync form when the goal being edited changes
  useEffect(() => {
    if (isEditing) {
      setTitle(props.goal.title);
      setDescription(props.goal.description ?? "");
      setGoalType(props.goal.goal_type as GoalType);
      setTargetValue(String(props.goal.target_value));
      setPlatform(props.goal.platform ?? undefined);
      setTopicSlug(props.goal.topic_slug ?? "");
      setTopicName(props.goal.topic_name ?? "");
      setDifficultyFilter(props.goal.difficulty_filter ?? undefined);
      setDeadline(props.goal.deadline ?? "");
      setStartDate(props.goal.start_date ?? "");
    } else {
      setTitle("");
      setDescription("");
      setGoalType("problems");
      setTargetValue("10");
      setPlatform(undefined);
      setTopicSlug("");
      setTopicName("");
      setDifficultyFilter(undefined);
      setDeadline("");
      setStartDate("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const target = parseInt(targetValue, 10);
    if (!title.trim() || isNaN(target) || target <= 0) return;

    // Validate required fields based on goal type
    if (goalType === "rating" && !platform) {
      alert("Platform is required for rating goals");
      return;
    }
    if (goalType === "topic" && (!topicSlug.trim() || !topicName.trim())) {
      alert("Topic slug and name are required for topic goals");
      return;
    }

    try {
      const baseData = {
        title: title.trim(),
        description: description.trim() || undefined,
        goal_type: goalType,
        target_value: target,
        platform: platform,
        topic_slug: topicSlug.trim() || undefined,
        topic_name: topicName.trim() || undefined,
        difficulty_filter: difficultyFilter,
        start_date: startDate.trim() || undefined,
        deadline: deadline.trim() || undefined,
      };

      if (isEditing) {
        // For edit, don't send goal_type since it's not editable
        const { goal_type, ...editData } = baseData;
        await (props as EditProps).onSubmit(editData);
      } else {
        await (props as CreateProps).onSubmit(baseData);
      }
      onClose();
    } catch {
      // Error handled in hook
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm">
      <div className="surface-card w-full max-w-md flex flex-col max-h-[calc(100vh-2rem)] overflow-hidden rounded-2xl">
        {/* Fixed Header */}
        <div className="flex items-center justify-between border-b border-border p-6 pb-4 flex-shrink-0">
          <h2 className="text-h3 font-semibold">{isEditing ? "Edit goal" : "Create new goal"}</h2>
          <button
            onClick={onClose}
            className="rounded-full p-1 text-muted-foreground hover:bg-muted"
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Scrollable Form Content */}
        <div className="flex-1 overflow-y-auto min-h-0 px-6">
          {error ? (
            <div className="mt-4 rounded-xl bg-destructive/10 p-3 text-caption text-destructive">
              {getDashboardErrorMessage(error)}
            </div>
          ) : null}

          <form onSubmit={handleSubmit} className="mt-5 space-y-3 pb-6">
            <div>
              <label className="text-label block uppercase text-subtle">Title</label>
              <input
                type="text"
                required
                placeholder="e.g. Solve 15 Medium problems"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="mt-1 h-10 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
              />
            </div>

            <div>
              <label className="text-label block uppercase text-subtle">Goal type</label>
              <select
                value={goalType}
                onChange={(e) => setGoalType(e.target.value as GoalType)}
                className="mt-1 h-10 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
              >
                <option value="rating">Rating</option>
                <option value="problems">Problems</option>
                <option value="topic">Topic</option>
                <option value="consistency">Consistency</option>
                <option value="contest">Contest</option>
                <option value="placement">Placement</option>
              </select>
            </div>

            {/* Platform - required for rating, optional for others */}
            {(goalType === "rating" || goalType === "problems" || goalType === "topic") && (
              <div>
                <label className="text-label block uppercase text-subtle">
                  Platform {goalType === "rating" ? "(required)" : "(optional)"}
                </label>
                <select
                  value={platform || ""}
                  onChange={(e) => setPlatform(e.target.value as Platform | undefined)}
                  required={goalType === "rating"}
                  className="mt-1 h-10 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
                >
                  <option value="">Select platform</option>
                  <option value="leetcode">LeetCode</option>
                  <option value="codeforces">Codeforces</option>
                </select>
              </div>
            )}

            {/* Topic fields - required for topic goals */}
            {goalType === "topic" && (
              <>
                <div>
                  <label className="text-label block uppercase text-subtle">
                    Topic slug (required)
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. dynamic-programming"
                    value={topicSlug}
                    onChange={(e) => setTopicSlug(e.target.value)}
                    className="mt-1 h-10 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
                  />
                </div>
                <div>
                  <label className="text-label block uppercase text-subtle">
                    Topic name (required)
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Dynamic Programming"
                    value={topicName}
                    onChange={(e) => setTopicName(e.target.value)}
                    className="mt-1 h-10 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
                  />
                </div>
              </>
            )}

            {/* Difficulty filter - optional for problems and placement */}
            {(goalType === "problems" || goalType === "placement") && (
              <div>
                <label className="text-label block uppercase text-subtle">
                  Difficulty filter (optional)
                </label>
                <select
                  value={difficultyFilter || ""}
                  onChange={(e) =>
                    setDifficultyFilter(e.target.value as "Easy" | "Medium" | "Hard" | undefined)
                  }
                  className="mt-1 h-10 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
                >
                  <option value="">All difficulties</option>
                  <option value="Easy">Easy</option>
                  <option value="Medium">Medium</option>
                  <option value="Hard">Hard</option>
                </select>
              </div>
            )}

            <div>
              <label className="text-label block uppercase text-subtle">Target value</label>
              <input
                type="number"
                min={1}
                required
                value={targetValue}
                onChange={(e) => setTargetValue(e.target.value)}
                className="mt-1 h-10 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
              />
            </div>

            <div>
              <label className="text-label block uppercase text-subtle">
                Start date (optional)
              </label>
              <input
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="mt-1 h-10 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
              />
            </div>

            <div>
              <label className="text-label block uppercase text-subtle">Deadline (optional)</label>
              <input
                type="date"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
                className="mt-1 h-10 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
              />
            </div>

            <div>
              <label className="text-label block uppercase text-subtle">
                Description (optional)
              </label>
              <input
                type="text"
                placeholder="Optional notes or details"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="mt-1 h-10 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none focus:border-violet"
              />
            </div>
          </form>
        </div>

        {/* Fixed Footer */}
        <div className="flex justify-end gap-3 p-6 pt-4 border-t border-border flex-shrink-0">
          <ActionButton variant="quiet" type="button" onClick={onClose}>
            Cancel
          </ActionButton>
          <ActionButton
            type="submit"
            disabled={isSubmitting}
            onClick={(e) => {
              e.preventDefault();
              handleSubmit(e as React.FormEvent<HTMLFormElement>);
            }}
          >
            {isSubmitting
              ? isEditing
                ? "Saving…"
                : "Creating…"
              : isEditing
                ? "Save changes"
                : "Create goal"}
          </ActionButton>
        </div>
      </div>
    </div>
  );
}
