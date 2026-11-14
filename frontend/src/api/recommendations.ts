import { API_BASE_URL, ApiError, clearAccessToken, getAccessToken, apiRequest } from "./client";

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
// Streaming AI Coach chat (Server-Sent Events over POST + ReadableStream)
// ---------------------------------------------------------------------------

export interface ChatStreamDone {
  tool_calls_made: string[];
  model: string | null;
}

export interface ChatStreamHandlers {
  /** Tool name only — never arguments or results. */
  onToolCall?: (toolName: string) => void;
  /** A chunk of the final answer text. */
  onToken?: (text: string) => void;
  /** Exactly one per successful stream. */
  onDone?: (meta: ChatStreamDone) => void;
  /** Exactly one per failed stream (instead of onDone). */
  onError?: (errorKind: string) => void;
}

interface SseMessage {
  event: string;
  data: unknown;
}

function parseSseBlock(block: string): SseMessage | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (dataLines.length === 0) return null;
  try {
    return { event, data: JSON.parse(dataLines.join("\n")) };
  } catch {
    return null;
  }
}

/**
 * POST /ai-coach/chat/stream and consume the SSE stream.
 *
 * EventSource cannot POST, so this uses fetch + ReadableStream. Resolves when
 * the stream ends; rejects with ApiError for HTTP failures (401/429/5xx) that
 * occur before the stream starts. Pass an AbortSignal to cancel.
 */
export async function streamChatWithCoach(
  request: ChatRequest,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getAccessToken();
  if (!token) {
    throw new ApiError("Sign in to view your dashboard.", 401);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/ai-coach/chat/stream`, {
      method: "POST",
      headers: {
        Accept: "text/event-stream",
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify(request),
      signal: signal ?? null,
    });
  } catch (err) {
    if (err instanceof DOMException && err.name === "AbortError") throw err;
    throw new ApiError("Unable to reach CodePulse. Check your connection and try again.");
  }

  if (!response.ok) {
    const payload: unknown = await response.json().catch(() => null);
    const detail =
      typeof payload === "object" &&
      payload !== null &&
      "detail" in payload &&
      typeof payload.detail === "string"
        ? payload.detail
        : "The AI Coach is unavailable right now.";
    if (response.status === 401) {
      clearAccessToken();
    }
    throw new ApiError(detail, response.status);
  }

  if (!response.body) {
    throw new ApiError("Streaming is not supported by this browser.");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let sep: number;
      while ((sep = buffer.indexOf("\n\n")) !== -1) {
        const block = buffer.slice(0, sep);
        buffer = buffer.slice(sep + 2);
        const message = parseSseBlock(block);
        if (!message) continue;
        const data = message.data as Record<string, unknown>;
        if (message.event === "tool_call") {
          handlers.onToolCall?.(String(data["tool"] ?? ""));
        } else if (message.event === "token") {
          handlers.onToken?.(String(data["text"] ?? ""));
        } else if (message.event === "done") {
          handlers.onDone?.({
            tool_calls_made: Array.isArray(data["tool_calls_made"])
              ? (data["tool_calls_made"] as string[])
              : [],
            model: typeof data["model"] === "string" ? data["model"] : null,
          });
        } else if (message.event === "error") {
          handlers.onError?.(String(data["error_kind"] ?? "unknown"));
        }
      }
    }
    // Flush any trailing event that arrived without a final blank line.
    const tail = buffer.trim();
    if (tail) {
      const message = parseSseBlock(tail);
      if (message) {
        const data = message.data as Record<string, unknown>;
        if (message.event === "done") {
          handlers.onDone?.({
            tool_calls_made: Array.isArray(data["tool_calls_made"])
              ? (data["tool_calls_made"] as string[])
              : [],
            model: typeof data["model"] === "string" ? data["model"] : null,
          });
        } else if (message.event === "error") {
          handlers.onError?.(String(data["error_kind"] ?? "unknown"));
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
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

export async function submitCoachFeedback(recommendationId: number, action: CoachFeedbackAction) {
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
