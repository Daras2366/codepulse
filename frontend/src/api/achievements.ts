/**
 * Achievements API
 *
 * Catalog endpoints are public.
 * /me and /evaluate require authentication.
 */
import { apiRequest } from "@/api/client";

export type AchievementCategory =
  | "problem"
  | "contest"
  | "rating"
  | "streak"
  | "topic"
  | "special";

export interface Achievement {
  id: number;
  name: string;
  description: string;
  icon: string | null;
  category: AchievementCategory;
}

export interface UserAchievement {
  id: number;
  user_id: number;
  achievement_id: number;
  earned_at: string;
  achievement: Achievement;
}

export interface AchievementEvalResult {
  newly_granted: number;
  achievement_names: string[];
}

export function getAchievements() {
  return apiRequest<Achievement[]>("/achievements/");
}

export function getMyAchievements() {
  return apiRequest<UserAchievement[]>("/achievements/me");
}

export function evaluateAchievements() {
  return apiRequest<AchievementEvalResult>("/achievements/evaluate", {
    method: "POST",
  });
}
