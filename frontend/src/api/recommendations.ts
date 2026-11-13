import { apiRequest } from "./client";

export interface Recommendation {
  category: "topic" | "difficulty" | "consistency" | "contest";
  title: string;
  reason: string;
  priority: "high" | "medium" | "low";
  suggested_activity: string;
  target_metric: string;
  difficulty_suggestion: "easy" | "medium" | "hard" | "mixed";
}

export interface DataQuality {
  has_topic_data: boolean;
  has_submission_data: boolean;
  has_contest_data: boolean;
  profile_reported_solved: number;
  locally_tagged_solved: number;
  historical_coverage_days: number;
  platform_coverage: string[];
}

export interface RecommendationsResponse {
  recommendations: Recommendation[];
  data_quality: DataQuality;
  has_sufficient_data: boolean;
}

export async function getRecommendations() {
  return apiRequest<RecommendationsResponse>("/recommendations");
}

export interface ChatRequest {
  message: string;
  conversation_history?: Array<{ role: string; content: string }>;
}

export interface ChatResponse {
  response: string;
  is_configured: boolean;
}

export async function chatWithCoach(request: ChatRequest) {
  return apiRequest<ChatResponse>("/ai-coach/chat", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

// ---------------------------------------------------------------------------
// AI Agent recommendation types
// ---------------------------------------------------------------------------

export interface AgentProblemRecommendation {
  problem_id: number | null;
  title: string;
  platform: string;
  difficulty: string | null;
  url: string;
  topics: string[];
  reason: string;
  priority: number;
  likely_unsolved: boolean;
  recommendation_id?: number | null;
}

export interface AgentRecommendationResponse {
  recommendations: AgentProblemRecommendation[];
  agent_reasoning: string;
  has_sufficient_data: boolean;
  catalog_limited: boolean;
  is_configured: boolean;
  tool_calls_made: string[];
  error: string | null;
  error_kind?: string | null;
  from_cache?: boolean;
  refreshed_at?: string | null;
}

export async function getAgentRecommendations(
  forceRefresh = false,
): Promise<AgentRecommendationResponse> {
  const suffix = forceRefresh ? "?force_refresh=true" : "";
  return apiRequest<AgentRecommendationResponse>(`/ai-coach/recommend${suffix}`, {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// AI Coach recommendation feedback
// ---------------------------------------------------------------------------

export type CoachFeedbackAction = "solved" | "skipped" | "thumbs_up" | "thumbs_down";

export interface CoachFeedbackResponse {
  recommendation_id: number;
  action: CoachFeedbackAction;
  recorded: boolean;
}

export async function submitCoachFeedback(
  recommendationId: number,
  action: CoachFeedbackAction,
) {
  return apiRequest<CoachFeedbackResponse>("/ai-coach/feedback", {
    method: "POST",
    body: JSON.stringify({ recommendation_id: recommendationId, action }),
  });
}

// ---------------------------------------------------------------------------
// Personalized study plan & upcoming contests
// ---------------------------------------------------------------------------

export interface StudyPlanProblem {
  id: number;
  title: string;
  platform: string;
  difficulty: string | null;
  url: string;
  topics: string[];
  estimated_minutes: number;
  acceptance_rate: number | null;
}

export interface StudyPlanDailyTarget {
  solved_today: number;
  daily_target: number | null;
  target_label: string | null;
  target_source: string | null;
  timezone: string;
}

export interface StudyPlanContest {
  id: number;
  title: string;
  platform: string;
  contest_url: string;
  start_time: string;
  duration_minutes: number;
}

export interface StudyPlanResponse {
  has_sufficient_data: boolean;
  focus_topic: string | null;
  focus_reason: string | null;
  problems: StudyPlanProblem[];
  problems_planned: number;
  total_estimated_minutes: number;
  estimate_note: string;
  daily: StudyPlanDailyTarget;
  upcoming_contest: StudyPlanContest | null;
  catalog_size: number;
  limitations: string[];
}

export function getStudyPlan(timezone?: string) {
  const tz =
    timezone ??
    (typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC");
  return apiRequest<StudyPlanResponse>(`/ai-coach/study-plan?timezone=${encodeURIComponent(tz)}`);
}

export function getUpcomingContests(limit = 5) {
  return apiRequest<StudyPlanContest[]>(`/ai-coach/upcoming-contests?limit=${limit}`);
}
