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
