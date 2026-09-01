/**
 * Goals API
 *
 * All endpoints require authentication. user_id is always derived from the
 * current token — it is never accepted from the frontend.
 *
 * All read endpoints now return GoalProgressResponse so the frontend always
 * gets live-computed progress in a single call.
 */
import { apiRequest } from "@/api/client";

export type GoalType = "rating" | "problems" | "topic" | "consistency" | "contest" | "placement";

export type GoalStatus = "active" | "completed" | "overdue" | "paused";

export type Platform = "leetcode" | "codeforces";

export type DifficultyFilter = "Easy" | "Medium" | "Hard";

export type Pace = "ahead" | "on_track" | "behind" | "completed" | "overdue" | "no_deadline";

/** Full goal with live-computed progress — returned by every endpoint. */
export interface GoalProgress {
  // Identity
  id: number;
  user_id: number;
  title: string;
  description: string | null;
  goal_type: GoalType;
  status: GoalStatus;

  // Scoping
  platform: Platform | null;
  topic_slug: string | null;
  topic_name: string | null;
  difficulty_filter: DifficultyFilter | null;

  // Target / baseline
  target_value: number;
  start_value: number;

  // Progress (computed by backend)
  current_value: number;
  progress_percentage: number;
  remaining: number;

  // Time
  start_date: string | null;
  deadline: string | null;
  days_remaining: number | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;

  // Insights
  is_overdue: boolean;
  is_completed: boolean;
  pace: Pace;
}

export interface GoalCreate {
  title: string;
  goal_type: GoalType;
  target_value: number;
  description?: string;
  platform?: Platform;
  topic_slug?: string;
  topic_name?: string;
  difficulty_filter?: DifficultyFilter;
  start_date?: string;
  deadline?: string;
}

export interface GoalUpdate {
  title?: string;
  description?: string;
  target_value?: number;
  platform?: Platform;
  topic_slug?: string;
  topic_name?: string;
  difficulty_filter?: DifficultyFilter;
  start_date?: string;
  deadline?: string;
  status?: GoalStatus;
}

export function getGoals(statusFilter?: GoalStatus) {
  const params = statusFilter ? `?status=${statusFilter}` : "";
  return apiRequest<GoalProgress[]>(`/goals/${params}`);
}

export function getGoal(goalId: number) {
  return apiRequest<GoalProgress>(`/goals/${goalId}`);
}

export function getGoalProgress(goalId: number) {
  return apiRequest<GoalProgress>(`/goals/${goalId}/progress`);
}

export function createGoal(data: GoalCreate) {
  return apiRequest<GoalProgress>("/goals/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function updateGoal(goalId: number, data: GoalUpdate) {
  return apiRequest<GoalProgress>(`/goals/${goalId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function deleteGoal(goalId: number) {
  return apiRequest<void>(`/goals/${goalId}`, { method: "DELETE" });
}
