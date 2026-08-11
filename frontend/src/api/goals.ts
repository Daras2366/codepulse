/**
 * Goals API
 *
 * All endpoints require authentication. user_id is always derived from the
 * current token — it is never accepted from the frontend.
 */
import { apiRequest } from "@/api/client";

export type GoalType = "daily" | "weekly" | "monthly";
export type GoalStatus = "active" | "completed" | "failed";

export interface Goal {
  id: number;
  user_id: number;
  title: string;
  description: string | null;
  goal_type: GoalType;
  target_value: number;
  current_value: number;
  status: GoalStatus;
  created_at: string;
  updated_at: string;
}

export interface GoalProgress extends Goal {
  window_start: string;
  window_end: string;
  calculated_progress: number;
  percentage: number;
  remaining: number;
  is_achieved: boolean;
}

export interface GoalCreate {
  title: string;
  goal_type: GoalType;
  target_value: number;
  description?: string;
  current_value?: number;
  status?: GoalStatus;
}

export interface GoalUpdate {
  title?: string;
  goal_type?: GoalType;
  target_value?: number;
  description?: string;
  current_value?: number;
  status?: GoalStatus;
}

export function getGoals() {
  return apiRequest<Goal[]>("/goals/");
}

export function getGoal(goalId: number) {
  return apiRequest<Goal>(`/goals/${goalId}`);
}

export function getGoalProgress(goalId: number) {
  return apiRequest<GoalProgress>(`/goals/${goalId}/progress`);
}

export function createGoal(data: GoalCreate) {
  return apiRequest<Goal>("/goals/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function updateGoal(goalId: number, data: GoalUpdate) {
  return apiRequest<Goal>(`/goals/${goalId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export function deleteGoal(goalId: number) {
  return apiRequest<void>(`/goals/${goalId}`, { method: "DELETE" });
}
