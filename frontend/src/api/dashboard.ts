import { apiRequest } from "@/api/client";

export type Platform = "leetcode" | "codeforces" | "codechef" | "atcoder";
export type Difficulty = "Easy" | "Medium" | "Hard";
export type SubmissionStatus =
  | "accepted"
  | "wrong_answer"
  | "time_limit_exceeded"
  | "memory_limit_exceeded"
  | "runtime_error"
  | "compile_error";

export interface DashboardOverview {
  profile_id: number;
  platform: Platform;
  username: string;
  total_problems_solved: number;
  total_submissions: number;
  contests_attended: number;
  current_rating: number | null;
  max_rating: number | null;
  rank: string | null;
  last_synced_at: string | null;
}

export interface DashboardRatingHistoryItem {
  contest_id: number | null;
  contest_name: string | null;
  contest_start_time: string | null;
  rating: number;
  rating_change: number;
  recorded_at: string;
}

export interface DashboardRating {
  profile_id: number;
  current_rating: number | null;
  max_rating: number | null;
  rank: string | null;
  history: DashboardRatingHistoryItem[];
}

export interface DashboardDifficultyCount {
  difficulty: Difficulty;
  solved_count: number;
}

export interface DashboardProblems {
  profile_id: number;
  solved_count: number;
  solved_by_difficulty: DashboardDifficultyCount[];
}

export interface DashboardSubmissionSummary {
  total_submissions: number;
  accepted_submissions: number;
  rejected_submissions: number;
}

export interface DashboardRecentSubmission {
  id: number;
  platform_submission_id: string;
  submitted_at: string;
  language: string;
  status: SubmissionStatus;
  problem_id: number;
  problem_title: string;
  problem_url: string;
  difficulty: Difficulty;
  contest_id: number | null;
  contest_name: string | null;
}

export interface DashboardSubmissionActivity {
  activity_date: string;
  total_submissions: number;
  accepted_submissions: number;
  rejected_submissions: number;
}

export interface DashboardSubmissions {
  profile_id: number;
  summary: DashboardSubmissionSummary;
  recent_submissions: DashboardRecentSubmission[];
  activity: DashboardSubmissionActivity[];
}

export interface DashboardContest {
  contest_id: number;
  contest_name: string;
  contest_url: string;
  start_time: string;
  duration_minutes: number;
  rank: number | null;
  old_rating: number | null;
  new_rating: number | null;
  rating_change: number | null;
  solved: number;
  penalty: number | null;
}

export interface DashboardContests {
  profile_id: number;
  contests_attended: number;
  contests: DashboardContest[];
}

export function getDashboardOverview(profileId: number) {
  return apiRequest<DashboardOverview>(`/dashboard/${profileId}/overview`);
}

export function getDashboardRating(profileId: number) {
  return apiRequest<DashboardRating>(`/dashboard/${profileId}/rating`);
}

export function getDashboardProblems(profileId: number) {
  return apiRequest<DashboardProblems>(`/dashboard/${profileId}/problems`);
}

export function getDashboardSubmissions(profileId: number, recentLimit = 20) {
  return apiRequest<DashboardSubmissions>(
    `/dashboard/${profileId}/submissions?recent_limit=${recentLimit}`,
  );
}

export function getDashboardContests(profileId: number) {
  return apiRequest<DashboardContests>(`/dashboard/${profileId}/contests`);
}

export interface SyncResult {
  profile_id: number;
  platform: string;
  problems_created: number;
  contests_created: number;
  submissions_created: number;
  submissions_skipped: number;
  rating_history_created: number;
  contest_participations_created: number;
  problems_solved: number;
  contests_attended: number;
  synced_at: string;
}

export function syncCodeforcesProfile(profileId: number) {
  return apiRequest<SyncResult>(`/sync/codeforces/${profileId}`, { method: "POST" });
}
