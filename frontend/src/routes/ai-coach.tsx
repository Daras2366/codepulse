import { createFileRoute, Link, redirect } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Bot,
  BrainCircuit,
  CalendarClock,
  ExternalLink,
  Loader2,
  RefreshCw,
  RotateCcw,
  Send,
  Sparkles,
  ThumbsDown,
  ThumbsUp,
  Trophy,
} from "lucide-react";
import * as React from "react";

import { hasAccessToken } from "@/api/client";
import { getPerformanceProfile, type PerformanceProfile } from "@/api/analytics";
import {
  streamChatWithCoach,
  getAgentRecommendations,
  getRecommendations,
  getUpcomingContests,
  submitCoachFeedback,
  type AgentProblemRecommendation,
  type AgentRecommendationResponse,
  type CoachFeedbackAction,
  type Recommendation,
} from "@/api/recommendations";

import { AppShell } from "@/components/layout/AppShell";
import { StudyPlanSection } from "@/components/coach/StudyPlanSection";
import { Markdown } from "@/components/coach/Markdown";
import { Panel } from "@/components/ui-kit/Panel";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui-kit/motion";
import { cn } from "@/lib/utils";

const title = "AI Coach — CodePulse";
const description =
  "Personalized recommendations and AI coaching based on your actual DSA performance data.";

export const Route = createFileRoute("/ai-coach")({
  beforeLoad: () => {
    // During SSR, we can't check localStorage, so don't redirect
    // The component will handle redirecting unauthenticated users
    if (typeof window !== "undefined" && !hasAccessToken()) {
      throw redirect({ to: "/auth" });
    }
  },
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: AICoach,
});

// ---------------------------------------------------------------------------
// Shared bits
// ---------------------------------------------------------------------------

function SectionLoader({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-busy>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-16 w-full rounded-2xl" />
      ))}
    </div>
  );
}

function RefreshButton({ onClick, title }: { onClick: () => void; title: string }) {
  return (
    <button
      onClick={onClick}
      className="flex h-9 w-9 items-center justify-center rounded-full bg-violet-soft text-violet transition-colors hover:bg-violet-soft/80"
      title={title}
    >
      <RefreshCw className="h-4 w-4" strokeWidth={1.6} />
    </button>
  );
}

function priorityBadgeClass(priority: string) {
  if (priority === "high") return "bg-pink-soft text-pink";
  if (priority === "medium") return "bg-yellow-soft text-yellow";
  return "bg-green-soft text-green";
}

function formatEnumLabel(value: string) {
  // "well_covered" → "Well covered", "Dynamic Programming" stays as-is.
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// ---------------------------------------------------------------------------
// Recommendations section (deterministic — independent of Gemini)
// ---------------------------------------------------------------------------

function RecommendationsSection() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["recommendations"],
    queryFn: getRecommendations,
  });

  const recommendations = data?.recommendations ?? [];
  const hasSufficientData = data?.has_sufficient_data ?? false;
  const dataQuality = data?.data_quality;

  return (
    <Panel
      title="Personalized Recommendations"
      caption="Deterministic analysis of your actual performance data"
      action={<RefreshButton onClick={() => refetch()} title="Refresh recommendations" />}
    >
      {isLoading ? (
        <SectionLoader />
      ) : error ? (
        <ErrorState
          title="Recommendations unavailable"
          description="We couldn't load your recommendations. The rest of this page still works."
          onRetry={() => refetch()}
        />
      ) : !hasSufficientData ? (
        <EmptyState
          title="Not enough data yet"
          description="Sync your platforms to get personalized recommendations based on your real practice history."
          action={
            <Link to="/platforms">
              <button className="rounded-full bg-primary px-5 py-2.5 text-caption font-semibold text-primary-foreground">
                Connect a platform
              </button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-4">
          {dataQuality &&
            (!dataQuality.has_topic_data ||
              !dataQuality.has_contest_data ||
              dataQuality.locally_tagged_solved < dataQuality.profile_reported_solved) && (
              <div className="rounded-2xl border border-yellow-soft bg-yellow-soft/20 px-4 py-3 text-caption text-yellow-700">
                <strong>Data coverage note:</strong>
                {!dataQuality.has_topic_data && " No topic data is available."}
                {!dataQuality.has_contest_data && " No contest data is available."}
                {dataQuality.locally_tagged_solved < dataQuality.profile_reported_solved &&
                  ` Only ${dataQuality.locally_tagged_solved} of ${dataQuality.profile_reported_solved} solved problems have topic tags.`}
              </div>
            )}

          {recommendations.length === 0 ? (
            <p className="text-body text-muted-foreground">
              No recommendations right now — keep practicing and check back after your next sync.
            </p>
          ) : (
            <ul className="grid gap-4 lg:grid-cols-2">
              {recommendations.slice(0, 6).map((rec, index) => (
                <RecommendationCard key={index} rec={rec} />
              ))}
            </ul>
          )}
        </div>
      )}
    </Panel>
  );
}

function RecommendationCard({ rec }: { rec: Recommendation }) {
  return (
    <li
      className={cn(
        "lift rounded-2xl border border-border bg-muted/50 p-5",
        rec.priority === "high" && "border-l-4 border-l-pink",
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={cn(
            "text-label rounded-full px-2 py-0.5 text-xs font-medium",
            priorityBadgeClass(rec.priority),
          )}
        >
          {rec.priority.toUpperCase()}
        </span>
        <span className="text-label text-subtle uppercase">{rec.category}</span>
      </div>
      <p className="text-card-title mt-2">{rec.title}</p>
      <p className="text-body mt-2 text-muted-foreground">{rec.reason}</p>
      <dl className="mt-3 space-y-1">
        <div className="flex gap-2 text-caption">
          <dt className="shrink-0 font-semibold text-subtle">Action:</dt>
          <dd className="text-muted-foreground">{rec.suggested_activity}</dd>
        </div>
        <div className="flex gap-2 text-caption">
          <dt className="shrink-0 font-semibold text-subtle">Target:</dt>
          <dd className="text-muted-foreground">{rec.target_metric}</dd>
        </div>
        {rec.difficulty_suggestion !== "mixed" && (
          <div className="flex gap-2 text-caption">
            <dt className="shrink-0 font-semibold text-subtle">Difficulty:</dt>
            <dd className="text-muted-foreground">{formatEnumLabel(rec.difficulty_suggestion)}</dd>
          </div>
        )}
      </dl>
    </li>
  );
}

// ---------------------------------------------------------------------------
// AI problem recommendations (Gemini agent — isolated failure domain)
// ---------------------------------------------------------------------------

function agentErrorMessage(data: AgentRecommendationResponse | undefined, queryError: unknown) {
  const kind = data?.error_kind;
  if (kind === "provider_unavailable" || kind === "rate_limited" || kind === "timeout") {
    return "The AI provider is temporarily unavailable (high demand or rate limit). Your deterministic recommendations above are unaffected — try again shortly.";
  }
  if (kind === "auth") {
    return "The configured Gemini API key was rejected. Check GEMINI_API_KEY in the backend environment.";
  }
  if (data?.error) return `AI recommendations failed: ${data.error}`;
  if (queryError) return "Failed to reach the AI recommendation service. Please try again.";
  return "AI recommendations failed. Please try again.";
}

function formatRefreshTime(iso: string | null | undefined): string | null {
  if (!iso) return null;
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return null;
  const diffMs = Date.now() - then;
  const mins = Math.floor(diffMs / 60_000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

function RecommendationFeedback({ recommendationId }: { recommendationId: number }) {
  const [submittedAction, setSubmittedAction] = React.useState<CoachFeedbackAction | null>(null);
  const [failed, setFailed] = React.useState(false);

  const mutation = useMutation({
    mutationFn: (action: CoachFeedbackAction) => submitCoachFeedback(recommendationId, action),
  });

  const submit = (action: CoachFeedbackAction) => {
    if (mutation.isPending || submittedAction) return;
    setFailed(false);
    mutation.mutate(action, {
      onSuccess: () => setSubmittedAction(action),
      onError: () => setFailed(true),
    });
  };

  if (submittedAction) {
    return <p className="text-caption mt-3 text-subtle">Thanks — feedback recorded.</p>;
  }

  return (
    <div className="mt-3 flex items-center gap-2">
      <button
        onClick={() => submit("thumbs_up")}
        disabled={mutation.isPending}
        className="flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-caption text-subtle transition-colors hover:bg-muted disabled:opacity-50"
        title="This recommendation was helpful"
      >
        {mutation.isPending ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <ThumbsUp className="h-3.5 w-3.5" />
        )}
        Helpful
      </button>
      <button
        onClick={() => submit("thumbs_down")}
        disabled={mutation.isPending}
        className="flex items-center gap-1 rounded-full border border-border px-2.5 py-1 text-caption text-subtle transition-colors hover:bg-muted disabled:opacity-50"
        title="This recommendation was not helpful"
      >
        <ThumbsDown className="h-3.5 w-3.5" />
        Not helpful
      </button>
      {failed && <span className="text-caption text-pink">Feedback failed — try again.</span>}
    </div>
  );
}

function AgentRecommendationCard({ rec }: { rec: AgentProblemRecommendation }) {
  return (
    <li className="lift rounded-2xl border border-border bg-muted/50 p-5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-label rounded-full bg-violet-soft px-2 py-0.5 text-xs font-medium text-violet">
          Priority {rec.priority}
        </span>
        <span className="text-label rounded-full bg-muted px-2 py-0.5 text-xs text-subtle">
          {rec.platform}
        </span>
        {rec.difficulty && (
          <span
            className={cn(
              "text-label rounded-full px-2 py-0.5 text-xs font-medium",
              rec.difficulty === "Easy"
                ? "bg-green-soft text-green"
                : rec.difficulty === "Medium"
                  ? "bg-yellow-soft text-yellow"
                  : "bg-pink-soft text-pink",
            )}
          >
            {rec.difficulty}
          </span>
        )}
        <span className="text-label text-xs text-subtle">
          {rec.likely_unsolved ? "Verified unsolved" : "Solve status uncertain"}
        </span>
      </div>

      <a
        href={rec.url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-card-title mt-2 flex items-center gap-1 hover:text-violet"
      >
        {rec.title}
        <ExternalLink className="h-3.5 w-3.5 shrink-0 opacity-60" />
      </a>

      {rec.topics.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {rec.topics.slice(0, 5).map((topic) => (
            <span key={topic} className="rounded-full bg-muted px-2 py-0.5 text-xs text-subtle">
              {topic}
            </span>
          ))}
        </div>
      )}

      <p className="text-body mt-3 text-muted-foreground">{rec.reason}</p>

      {rec.recommendation_id != null && (
        <RecommendationFeedback recommendationId={rec.recommendation_id} />
      )}
    </li>
  );
}

function AgentRecommendationsSection() {
  const queryClient = useQueryClient();
  const [enabled, setEnabled] = React.useState(false);

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["agent-recommendations"],
    queryFn: () => getAgentRecommendations(false),
    enabled,
    retry: false,
  });

  // Force refresh bypasses the server-side cache but still respects the
  // per-user rate limit. Existing recommendations stay visible while the
  // fresh result is being generated.
  const refreshMutation = useMutation({
    mutationFn: () => getAgentRecommendations(true),
    onSuccess: (fresh) => {
      queryClient.setQueryData(["agent-recommendations"], fresh);
    },
  });

  const forceRefresh = () => refreshMutation.mutate();

  const start = () => {
    setEnabled(true);
    queryClient.invalidateQueries({ queryKey: ["agent-recommendations"] });
  };

  const refreshedLabel = formatRefreshTime(data?.refreshed_at);

  return (
    <Panel
      title="AI Problem Recommendations"
      caption="Gemini searches your real problem catalog for unsolved problems matched to your weak areas"
      action={
        data ? (
          <button
            onClick={forceRefresh}
            disabled={refreshMutation.isPending}
            className="flex h-9 w-9 items-center justify-center rounded-full bg-violet-soft text-violet transition-colors hover:bg-violet-soft/80 disabled:opacity-60"
            title="Get fresh AI recommendations"
          >
            {refreshMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" strokeWidth={1.6} />
            )}
          </button>
        ) : undefined
      }
    >
      {!enabled && !data ? (
        <div className="flex flex-col items-center gap-4 py-6">
          <p className="text-body max-w-md text-center text-muted-foreground">
            Let Gemini analyse your profile and find specific unsolved problems from your synced
            catalog.
          </p>
          <button
            onClick={start}
            className="flex items-center gap-2 rounded-2xl bg-violet px-5 py-2.5 text-caption font-medium text-white transition-colors hover:bg-violet/90"
          >
            <Sparkles className="h-4 w-4" />
            Get AI Recommendations
          </button>
        </div>
      ) : isLoading ? (
        <div className="flex flex-col items-center gap-3 py-8">
          <Loader2 className="h-7 w-7 animate-spin text-violet" />
          <p className="text-body text-center text-muted-foreground">
            AI agent is analysing your profile and searching for problems…
          </p>
        </div>
      ) : error ? (
        <div className="flex flex-col items-center gap-4 py-6">
          <AlertCircle className="h-7 w-7 text-pink" />
          <p className="text-body max-w-md text-center text-muted-foreground">
            {agentErrorMessage(undefined, error)}
          </p>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 rounded-2xl bg-violet px-4 py-2 text-caption font-medium text-white transition-colors hover:bg-violet/90"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      ) : data && !data.is_configured ? (
        <div className="rounded-2xl bg-muted/50 p-4">
          <p className="text-body text-muted-foreground">
            AI recommendations are not configured. Set{" "}
            <code className="font-mono">GEMINI_API_KEY</code> in the backend environment to enable
            this feature.
          </p>
        </div>
      ) : data && data.error && data.recommendations.length === 0 ? (
        <div className="flex flex-col items-center gap-4 py-6">
          <AlertCircle className="h-7 w-7 text-pink" />
          <p className="text-body max-w-md text-center text-muted-foreground">
            {agentErrorMessage(data, null)}
          </p>
          <button
            onClick={() => refetch()}
            className="flex items-center gap-2 rounded-2xl bg-violet px-4 py-2 text-caption font-medium text-white transition-colors hover:bg-violet/90"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      ) : data ? (
        <div className="space-y-4">
          {data.catalog_limited && (
            <div className="rounded-2xl border border-yellow-soft bg-yellow-soft/20 px-4 py-3 text-caption text-yellow-700">
              <strong>Catalog note:</strong> The problem catalog only contains problems synced from
              your submission history. Sync more submissions to expand it.
            </div>
          )}

          {data.agent_reasoning && (
            <div className="rounded-2xl bg-violet-soft/30 px-4 py-3">
              <p className="text-caption text-subtle">{data.agent_reasoning}</p>
            </div>
          )}

          {data.recommendations.length === 0 ? (
            <p className="text-body text-muted-foreground">
              No candidate problems found in the catalog. Try syncing more submissions.
            </p>
          ) : (
            <ul className="grid gap-4 lg:grid-cols-2">
              {data.recommendations.slice(0, 6).map((rec, index) => (
                <AgentRecommendationCard
                  key={rec.recommendation_id ?? rec.problem_id ?? index}
                  rec={rec}
                />
              ))}
            </ul>
          )}

          {data.error && data.recommendations.length > 0 && (
            <p className="text-caption text-subtle">Note: {data.error}</p>
          )}

          {refreshMutation.isError && (
            <p className="text-caption text-pink">
              Fresh recommendations failed to load — showing the previous result.
            </p>
          )}

          <div className="flex items-center justify-between gap-3">
            <p className="text-caption text-subtle">
              {data.from_cache ? "Cached" : "Fresh"}
              {refreshedLabel ? ` · refreshed ${refreshedLabel}` : ""} ·{" "}
              {data.tool_calls_made.length} tool call
              {data.tool_calls_made.length !== 1 ? "s" : ""} made
            </p>
            <button
              onClick={forceRefresh}
              disabled={refreshMutation.isPending}
              className="flex items-center gap-2 rounded-2xl border border-border px-4 py-2 text-caption font-medium text-subtle transition-colors hover:bg-muted disabled:opacity-60"
            >
              {refreshMutation.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              Reconsider
            </button>
          </div>
        </div>
      ) : null}
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Strengths & weaknesses (performance profile — independent failure domain)
// ---------------------------------------------------------------------------

function StrengthsWeaknessesSection() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["performance-profile"],
    queryFn: getPerformanceProfile,
  });

  const profile = data?.profile;

  return (
    <div className="grid gap-6 xl:grid-cols-2">
      <Panel
        title="Strengths"
        caption="Patterns derived from your actual submission data"
        action={
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-green-soft">
            <BrainCircuit className="h-4 w-4" strokeWidth={1.6} />
          </span>
        }
      >
        {isLoading ? (
          <SectionLoader rows={2} />
        ) : error ? (
          <ErrorState
            title="Strengths unavailable"
            description="Performance profile could not be loaded."
            onRetry={() => refetch()}
          />
        ) : !profile || profile.strengths.length === 0 ? (
          <p className="text-body text-muted-foreground">
            No strengths identified yet. Keep practicing to build your profile!
          </p>
        ) : (
          <ul className="space-y-3">
            {profile.strengths.slice(0, 4).map((s, index) => (
              <li key={index} className="flex items-start gap-3 rounded-2xl bg-green-soft/30 p-3">
                <BrainCircuit className="mt-0.5 h-5 w-5 shrink-0 text-green" strokeWidth={1.6} />
                <div>
                  <p className="text-card-title">{s.description}</p>
                  <p className="text-caption mt-1 text-subtle">
                    {s.supporting_metric}:{" "}
                    <strong>
                      {typeof s.metric_value === "number"
                        ? s.metric_value.toLocaleString()
                        : s.metric_value}
                    </strong>
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel
        title="Weaknesses"
        caption="Areas for improvement — based on your actual data"
        action={
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-pink-soft">
            <Bot className="h-4 w-4" strokeWidth={1.6} />
          </span>
        }
      >
        {isLoading ? (
          <SectionLoader rows={2} />
        ) : error ? (
          <ErrorState
            title="Weaknesses unavailable"
            description="Performance profile could not be loaded."
            onRetry={() => refetch()}
          />
        ) : !profile || profile.weaknesses.length === 0 ? (
          <p className="text-body text-muted-foreground">
            No weaknesses identified. Great job maintaining balance across topics!
          </p>
        ) : (
          <ul className="space-y-3">
            {profile.weaknesses.slice(0, 4).map((w, index) => (
              <li key={index} className="flex items-start gap-3 rounded-2xl bg-pink-soft/30 p-3">
                <Bot className="mt-0.5 h-5 w-5 shrink-0 text-pink" strokeWidth={1.6} />
                <div>
                  <p className="text-card-title">{w.description}</p>
                  <p className="text-caption mt-1 text-subtle">
                    {w.supporting_metric}:{" "}
                    <strong>
                      {typeof w.metric_value === "number"
                        ? w.metric_value.toLocaleString()
                        : w.metric_value}
                    </strong>{" "}
                    · Confidence: {formatEnumLabel(w.confidence)}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Contest preparation
// ---------------------------------------------------------------------------

function useContestCountdown(targetIso: string) {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(id);
  }, []);
  const diff = new Date(targetIso).getTime() - now;
  if (diff <= 0) return "Live now";
  const days = Math.floor(diff / 86_400_000);
  const hours = Math.floor((diff % 86_400_000) / 3_600_000);
  if (days > 0) return `in ${days}d ${hours}h`;
  if (hours > 0) return `in ${hours}h ${Math.floor((diff % 3_600_000) / 60_000)}m`;
  return `in ${Math.max(1, Math.floor(diff / 60_000))}m`;
}

function ContestPrepSection() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["upcoming-contests"],
    queryFn: () => getUpcomingContests(5),
  });

  return (
    <Panel
      title="Contest Preparation"
      caption="Upcoming contests from your synced platforms"
      action={
        <span className="flex h-9 w-9 items-center justify-center rounded-full bg-yellow-soft">
          <Trophy className="h-4 w-4" strokeWidth={1.6} />
        </span>
      }
    >
      {isLoading ? (
        <SectionLoader rows={2} />
      ) : error ? (
        <ErrorState
          title="Contests unavailable"
          description="Contest data could not be loaded. It syncs from your connected platforms."
          onRetry={() => refetch()}
        />
      ) : !data || data.length === 0 ? (
        <EmptyState
          icon={CalendarClock}
          title="No upcoming contests"
          description="No future contests are stored yet. Contest data is synced from your connected platforms — check back after your next sync."
        />
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2">
          {data.map((contest) => (
            <ContestRow key={contest.id} contest={contest} />
          ))}
        </ul>
      )}
    </Panel>
  );
}

function ContestRow({
  contest,
}: {
  contest: {
    id: number;
    title: string;
    platform: string;
    contest_url: string;
    start_time: string;
    duration_minutes: number;
  };
}) {
  const countdown = useContestCountdown(contest.start_time);
  return (
    <li className="lift rounded-2xl border border-border bg-muted/40 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <a
            href={contest.contest_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-card-title flex items-center gap-1 truncate hover:text-violet"
          >
            {contest.title}
            <ExternalLink className="h-3.5 w-3.5 shrink-0 opacity-60" />
          </a>
          <p className="text-label mt-1 text-subtle">
            {contest.platform} ·{" "}
            {new Date(contest.start_time).toLocaleString(undefined, {
              dateStyle: "medium",
              timeStyle: "short",
            })}{" "}
            · {contest.duration_minutes} min
          </p>
        </div>
        <span className="text-label shrink-0 rounded-full bg-yellow-soft px-2.5 py-1 font-medium text-yellow">
          {countdown}
        </span>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// AI Chat
// ---------------------------------------------------------------------------

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

function suggestedQuestions(profile: PerformanceProfile | undefined): string[] {
  const questions: string[] = [];
  const weak = profile?.topic_performance?.find((t) => t.strength_level === "weak");
  const moderate = profile?.topic_performance?.find(
    (t) => t.strength_level === "moderate" && t.recent_activity === 0,
  );

  if (weak) questions.push(`How can I improve my ${weak.topic} skills?`);
  if (moderate) questions.push(`Should I revise ${moderate.topic}?`);
  questions.push("What should I practice today?");
  if ((profile?.contest_performance.contests_participated ?? 0) > 0) {
    questions.push("How has my contest performance changed recently?");
  } else if ((profile?.overview.solved_problems ?? 0) > 20) {
    questions.push("Should I try a contest yet?");
  }
  questions.push("Create a seven-day revision plan.");
  return questions.slice(0, 4);
}

const TOOL_STATUS_LABELS: Record<string, string> = {
  get_user_performance_profile: "checking your overall stats…",
  get_topic_performance: "checking your topic stats…",
  get_recent_submissions: "reviewing your recent submissions…",
  get_user_goals: "checking your practice goals…",
  search_candidate_problems: "searching the problem catalog…",
  get_problem_details: "verifying problem details…",
  get_failure_patterns: "analysing your failure patterns…",
  get_attempts_before_accept: "checking attempts per topic…",
  get_stale_topics: "checking for stale topics…",
  get_contest_postmortem: "reviewing your contest history…",
};

function toolStatusLabel(toolName: string): string {
  return TOOL_STATUS_LABELS[toolName] ?? "checking your data…";
}

function ChatSection({ profile }: { profile: PerformanceProfile | undefined }) {
  const [message, setMessage] = React.useState("");
  const [conversationHistory, setConversationHistory] = React.useState<ChatMsg[]>([]);
  const [pendingUserMessage, setPendingUserMessage] = React.useState<string | null>(null);
  const [isChatPending, setIsChatPending] = React.useState(false);
  const [toolStatuses, setToolStatuses] = React.useState<string[]>([]);
  const [streamText, setStreamText] = React.useState("");
  const abortRef = React.useRef<AbortController | null>(null);
  const chatScrollRef = React.useRef<HTMLDivElement>(null);

  // Abort any in-flight stream when the component unmounts.
  React.useEffect(() => () => abortRef.current?.abort(), []);

  React.useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [conversationHistory, isChatPending, streamText, toolStatuses.length]);

  const handleSendMessage = (overrideMessage?: string) => {
    const text = (overrideMessage ?? message).trim();
    if (!text || isChatPending) return;

    if (!overrideMessage) setMessage("");
    setPendingUserMessage(null);

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    const priorHistory = conversationHistory;
    setConversationHistory([...priorHistory, { role: "user", content: text }]);
    setToolStatuses([]);
    setStreamText("");
    setIsChatPending(true);

    let accumulated = "";
    let settled = false;

    const fail = (notConfigured = false) => {
      if (settled) return;
      settled = true;
      setIsChatPending(false);
      setToolStatuses([]);
      setStreamText("");
      if (notConfigured) {
        // Provider not configured — keep the user message but show a
        // system-style notice instead of a fabricated answer.
        setConversationHistory((prev) => [
          ...prev,
          {
            role: "assistant",
            content:
              "AI Coach is not configured. Set GEMINI_API_KEY in the backend " +
              "environment to enable chat.",
          },
        ]);
      } else {
        setConversationHistory(priorHistory);
        setPendingUserMessage(text);
      }
    };

    streamChatWithCoach(
      { message: text, conversation_history: priorHistory },
      {
        onToolCall: (toolName) => {
          setToolStatuses((prev) => [...prev, toolStatusLabel(toolName)]);
        },
        onToken: (chunk) => {
          accumulated += chunk;
          setStreamText(accumulated);
        },
        onDone: () => {
          if (settled) return;
          settled = true;
          setConversationHistory((prev) => [
            ...prev,
            { role: "assistant", content: accumulated || "(no response)" },
          ]);
          setIsChatPending(false);
          setToolStatuses([]);
          setStreamText("");
        },
        onError: (errorKind) => {
          fail(errorKind === "not_configured");
        },
      },
      controller.signal,
    )
      .catch((err) => {
        if (err instanceof DOMException && err.name === "AbortError") return;
        fail();
      })
      .finally(() => {
        // Stream ended without done/error (e.g. server closed early).
        if (!settled && !controller.signal.aborted) fail();
      });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const questions = suggestedQuestions(profile);

  return (
    <Panel
      title="Ask Your AI Coach"
      caption="Powered by Gemini — answers are grounded in your actual backend performance data"
    >
      <div className="space-y-4">
        {(conversationHistory.length > 0 || isChatPending) && (
          <div
            ref={chatScrollRef}
            className="max-h-96 space-y-3 overflow-y-auto rounded-2xl bg-muted/50 p-4"
          >
            {conversationHistory.map((msg, index) => (
              <div
                key={index}
                className={cn(
                  "rounded-2xl p-3",
                  msg.role === "user"
                    ? "ml-auto max-w-[80%] bg-violet-soft"
                    : "mr-auto max-w-[85%] bg-card",
                )}
              >
                {msg.role === "assistant" ? (
                  <Markdown content={msg.content} />
                ) : (
                  <p className="text-body whitespace-pre-wrap">{msg.content}</p>
                )}
              </div>
            ))}

            {isChatPending && (
              <div className="mr-auto max-w-[85%] space-y-2">
                {toolStatuses.map((status, index) => (
                  <p key={index} className="flex items-center gap-1.5 text-caption text-subtle">
                    <Loader2 className="h-3 w-3 animate-spin" />
                    {status}
                  </p>
                ))}
                {streamText ? (
                  <div className="rounded-2xl bg-card p-3">
                    <Markdown content={streamText} />
                  </div>
                ) : toolStatuses.length === 0 ? (
                  <div className="flex items-center gap-2 text-subtle">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    <span className="text-caption">Thinking…</span>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        )}

        {pendingUserMessage && !isChatPending && (
          <div className="flex items-center justify-between gap-3 rounded-2xl border border-pink-soft bg-pink-soft/20 px-4 py-3">
            <div className="flex items-center gap-2 text-pink">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span className="text-caption">
                Message failed to send — the AI provider may be temporarily unavailable. Your
                message is preserved.
              </span>
            </div>
            <button
              onClick={() => handleSendMessage(pendingUserMessage)}
              className="flex shrink-0 items-center gap-1.5 rounded-xl bg-pink px-3 py-1.5 text-caption font-medium text-white transition-colors hover:bg-pink/90"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Retry
            </button>
          </div>
        )}

        {conversationHistory.length === 0 && !isChatPending && (
          <div className="flex flex-wrap gap-2">
            {questions.map((question) => (
              <button
                key={question}
                onClick={() => {
                  setMessage(question);
                  handleSendMessage(question);
                }}
                className="rounded-full border border-border bg-muted/50 px-3 py-1.5 text-caption text-subtle transition-colors hover:bg-muted"
              >
                {question}
              </button>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <textarea
            id="ai-coach-message-input"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about your performance, strengths, weaknesses, or request a study plan… (Enter to send, Shift+Enter for newline)"
            className="flex-1 resize-none rounded-2xl border border-border bg-background px-4 py-3 text-caption outline-none focus:border-violet"
            rows={2}
            disabled={isChatPending}
          />
          <button
            id="ai-coach-send-btn"
            onClick={() => handleSendMessage()}
            disabled={!message.trim() || isChatPending}
            className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-violet text-white transition-colors hover:bg-violet/90 disabled:cursor-not-allowed disabled:opacity-50"
            title="Send message"
          >
            {isChatPending ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </div>
      </div>
    </Panel>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

function AICoach() {
  // Performance profile is fetched once here for suggested chat questions;
  // each section below owns its own query state so one failure can't take
  // down the whole page.
  const { data: performanceData } = useQuery({
    queryKey: ["performance-profile"],
    queryFn: getPerformanceProfile,
  });
  const profile = performanceData?.profile;

  return (
    <AppShell
      title="AI Coach"
      subtitle="Personalized recommendations and coaching grounded in your real performance data."
    >
      <div className="space-y-6">
        <StudyPlanSection />
        <RecommendationsSection />
        <AgentRecommendationsSection />
        <StrengthsWeaknessesSection />
        <ContestPrepSection />
        <ChatSection profile={profile} />
      </div>
    </AppShell>
  );
}
