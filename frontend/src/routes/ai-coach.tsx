import { createFileRoute, redirect } from "@tanstack/react-router";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  Bot,
  BrainCircuit,
  Loader2,
  RefreshCw,
  RotateCcw,
  Send,
} from "lucide-react";
import * as React from "react";

import { hasAccessToken } from "@/api/client";
import {
  chatWithCoach,
  getRecommendations,
  type Recommendation,
} from "@/api/recommendations";
import { getPerformanceProfile } from "@/api/analytics";

import { AppShell } from "@/components/layout/AppShell";
import { StudyPlanCard } from "@/components/dashboard/StudyPlanCard";
import { Panel } from "@/components/ui-kit/Panel";

const title = "AI Coach — CodePulse";
const description =
  "Personalized recommendations and AI coaching based on your actual DSA performance data.";

export const Route = createFileRoute("/ai-coach")({
  beforeLoad: () => {
    if (!hasAccessToken()) {
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
// Sub-components
// ---------------------------------------------------------------------------

function StrengthItem({
  description,
  metric_value,
  supporting_metric,
}: {
  description: string;
  metric_value: number | string;
  supporting_metric: string;
}) {
  return (
    <li className="flex items-start gap-3 rounded-2xl bg-green-soft/30 p-3">
      <BrainCircuit className="h-5 w-5 shrink-0 text-green mt-0.5" strokeWidth={1.6} />
      <div>
        <p className="text-card-title">{description}</p>
        <p className="text-caption mt-1 text-subtle">
          {supporting_metric}: <strong>{metric_value}</strong>
        </p>
      </div>
    </li>
  );
}

function WeaknessItem({
  description,
  metric_value,
  supporting_metric,
  confidence,
}: {
  description: string;
  metric_value: number | string;
  supporting_metric: string;
  confidence: string;
}) {
  return (
    <li className="flex items-start gap-3 rounded-2xl bg-pink-soft/30 p-3">
      <Bot className="h-5 w-5 shrink-0 text-pink mt-0.5" strokeWidth={1.6} />
      <div>
        <p className="text-card-title">{description}</p>
        <p className="text-caption mt-1 text-subtle">
          {supporting_metric}: <strong>{metric_value}</strong> · Confidence:{" "}
          {confidence}
        </p>
      </div>
    </li>
  );
}

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

function AICoach() {
  const queryClient = useQueryClient();

  const {
    data: recommendationsData,
    isLoading: recommendationsLoading,
    error: recommendationsError,
    refetch: refetchRecommendations,
  } = useQuery({
    queryKey: ["recommendations"],
    queryFn: getRecommendations,
  });

  const {
    data: performanceData,
    isLoading: performanceLoading,
    refetch: refetchPerformance,
  } = useQuery({
    queryKey: ["performance-profile"],
    queryFn: getPerformanceProfile,
  });

  const chatMutation = useMutation({
    mutationFn: chatWithCoach,
  });

  const [message, setMessage] = React.useState("");
  const [conversationHistory, setConversationHistory] = React.useState<ChatMsg[]>([]);
  // Preserve the last failed user message so it can be retried.
  const [pendingUserMessage, setPendingUserMessage] = React.useState<string | null>(null);

  const chatScrollRef = React.useRef<HTMLDivElement>(null);

  // Scroll to bottom whenever the conversation updates.
  React.useEffect(() => {
    if (chatScrollRef.current) {
      chatScrollRef.current.scrollTop = chatScrollRef.current.scrollHeight;
    }
  }, [conversationHistory, chatMutation.isPending]);

  const handleSendMessage = (overrideMessage?: string) => {
    const text = (overrideMessage ?? message).trim();
    if (!text || chatMutation.isPending) return;

    // Optimistically add to history and clear input.
    if (!overrideMessage) setMessage("");
    setPendingUserMessage(null);
    chatMutation.reset();

    const nextHistory: ChatMsg[] = [
      ...conversationHistory,
      { role: "user", content: text },
    ];
    setConversationHistory(nextHistory);

    chatMutation.mutate(
      {
        message: text,
        // Send only the history that existed BEFORE this message.
        conversation_history: conversationHistory,
      },
      {
        onSuccess: (data) => {
          setConversationHistory((prev) => [
            ...prev,
            { role: "assistant", content: data.response },
          ]);
          setPendingUserMessage(null);
        },
        onError: () => {
          // Remove the optimistically added user message and preserve it for retry.
          setConversationHistory(conversationHistory);
          setPendingUserMessage(text);
        },
      },
    );
  };

  const handleRetry = () => {
    if (pendingUserMessage) {
      handleSendMessage(pendingUserMessage);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
    // Shift+Enter: default textarea newline behaviour — no preventDefault needed.
  };

  const handleRefreshAll = () => {
    refetchRecommendations();
    refetchPerformance();
  };

  if (recommendationsLoading || performanceLoading) {
    return (
      <AppShell title="AI Coach" subtitle="Loading your personalized recommendations...">
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-8 w-8 animate-spin text-violet" />
        </div>
      </AppShell>
    );
  }

  if (recommendationsError) {
    return (
      <AppShell title="AI Coach" subtitle="Unable to load recommendations">
        <div className="flex flex-col items-center gap-4 py-12">
          <AlertCircle className="h-8 w-8 text-pink" />
          <p className="text-body text-muted-foreground">
            Failed to load recommendations. Please try again.
          </p>
          <button
            id="retry-recommendations-btn"
            onClick={() => refetchRecommendations()}
            className="flex items-center gap-2 rounded-2xl bg-violet px-4 py-2 text-caption font-medium text-white transition-colors hover:bg-violet/90"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      </AppShell>
    );
  }

  const recommendations = recommendationsData?.recommendations ?? [];
  const hasSufficientData = recommendationsData?.has_sufficient_data ?? false;
  const dataQuality = recommendationsData?.data_quality;

  const profile = performanceData?.profile;
  const strengths = profile?.strengths ?? [];
  const weaknesses = profile?.weaknesses ?? [];

  return (
    <AppShell
      title="AI Coach"
      subtitle="Personalized recommendations based on your actual performance data."
    >
      <div className="space-y-6">
        {/* StudyPlanCard uses static placeholder data — not AI-generated. */}
        <StudyPlanCard />

        {!hasSufficientData ? (
          <Panel
            title="Insufficient Data"
            caption="Sync your platforms to get personalized recommendations"
          >
            <p className="text-body text-muted-foreground">
              We need more of your practice data to generate meaningful recommendations.
              Please sync your Codeforces or LeetCode profile to get started.
            </p>
          </Panel>
        ) : (
          <>
            {/* Data quality notice */}
            {dataQuality && (
              (!dataQuality.has_topic_data ||
                !dataQuality.has_contest_data ||
                dataQuality.locally_tagged_solved < dataQuality.profile_reported_solved) && (
                <div className="rounded-2xl border border-yellow-soft bg-yellow-soft/20 px-4 py-3 text-caption text-yellow-700">
                  <strong>Note:</strong> Some data may be incomplete.
                  {!dataQuality.has_topic_data && " No topic data is available."}
                  {!dataQuality.has_contest_data && " No contest data is available."}
                  {dataQuality.locally_tagged_solved < dataQuality.profile_reported_solved &&
                    ` Only ${dataQuality.locally_tagged_solved} of ${dataQuality.profile_reported_solved} solved problems have topic tags.`}
                </div>
              )
            )}

            {/* Recommendations */}
            <Panel
              title="Personalized Recommendations"
              caption="Based on your actual performance data — not AI-generated text"
              action={
                <button
                  id="refresh-recommendations-btn"
                  onClick={handleRefreshAll}
                  className="flex h-9 w-9 items-center justify-center rounded-full bg-violet-soft text-violet transition-colors hover:bg-violet-soft/80"
                  title="Refresh recommendations and performance data"
                >
                  <RefreshCw className="h-4 w-4" strokeWidth={1.6} />
                </button>
              }
            >
              {recommendations.length === 0 ? (
                <p className="text-body text-muted-foreground">
                  No recommendations available at this time. Keep practicing to get
                  personalized suggestions!
                </p>
              ) : (
                <ul className="space-y-4">
                  {recommendations.map((rec, index) => (
                    <li
                      key={index}
                      className="lift group rounded-2xl border border-border bg-muted/50 p-5"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex-1">
                          <div className="mb-2 flex items-center gap-2">
                            <span
                              className={`text-label rounded-full px-2 py-0.5 text-xs font-medium ${
                                rec.priority === "high"
                                  ? "bg-pink-soft text-pink"
                                  : rec.priority === "medium"
                                    ? "bg-yellow-soft text-yellow"
                                    : "bg-green-soft text-green"
                              }`}
                            >
                              {rec.priority.toUpperCase()}
                            </span>
                            <span className="text-label text-subtle uppercase">
                              {rec.category}
                            </span>
                          </div>
                          <p className="text-card-title">{rec.title}</p>
                          <p className="text-body mt-2 text-muted-foreground">{rec.reason}</p>
                          <p className="text-caption mt-3 text-subtle">
                            <strong>Suggested:</strong> {rec.suggested_activity}
                          </p>
                          <p className="text-caption mt-1 text-subtle">
                            <strong>Target:</strong> {rec.target_metric}
                          </p>
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>

            {/* Strengths and Weaknesses */}
            {profile && (profile.strengths.length > 0 || profile.weaknesses.length > 0) && (
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
                  {profile.strengths.length > 0 ? (
                    <ul className="space-y-3">
                      {profile.strengths.slice(0, 3).map((s, index) => (
                        <StrengthItem
                          key={index}
                          description={s.description}
                          metric_value={s.metric_value}
                          supporting_metric={s.supporting_metric}
                        />
                      ))}
                    </ul>
                  ) : (
                    <p className="text-body text-muted-foreground">
                      No strengths identified yet. Keep practicing to build your profile!
                    </p>
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
                  {profile.weaknesses.length > 0 ? (
                    <ul className="space-y-3">
                      {profile.weaknesses.slice(0, 3).map((w, index) => (
                        <WeaknessItem
                          key={index}
                          description={w.description}
                          metric_value={w.metric_value}
                          supporting_metric={w.supporting_metric}
                          confidence={w.confidence}
                        />
                      ))}
                    </ul>
                  ) : (
                    <p className="text-body text-muted-foreground">
                      No weaknesses identified. Great job maintaining balance across topics!
                    </p>
                  )}
                </Panel>
              </div>
            )}

            {/* AI Chat */}
            <Panel
              title="Ask Your AI Coach"
              caption="Powered by Gemini — grounded in your actual backend performance data"
            >
              <div className="space-y-4">
                {/* Conversation */}
                {(conversationHistory.length > 0 || chatMutation.isPending) && (
                  <div
                    ref={chatScrollRef}
                    className="max-h-96 space-y-3 overflow-y-auto rounded-2xl bg-muted/50 p-4"
                  >
                    {conversationHistory.map((msg, index) => (
                      <div
                        key={index}
                        className={`rounded-2xl p-3 ${
                          msg.role === "user"
                            ? "bg-violet-soft ml-auto max-w-[80%]"
                            : "bg-muted mr-auto max-w-[80%]"
                        }`}
                      >
                        <p className="text-body whitespace-pre-wrap">{msg.content}</p>
                      </div>
                    ))}

                    {chatMutation.isPending && (
                      <div className="flex items-center gap-2 text-subtle">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span className="text-caption">Thinking…</span>
                      </div>
                    )}
                  </div>
                )}

                {/* Error state with retry */}
                {chatMutation.isError && pendingUserMessage && (
                  <div className="flex items-center justify-between gap-3 rounded-2xl border border-pink-soft bg-pink-soft/20 px-4 py-3">
                    <div className="flex items-center gap-2 text-pink">
                      <AlertCircle className="h-4 w-4 shrink-0" />
                      <span className="text-caption">
                        Message failed to send. Your message is preserved.
                      </span>
                    </div>
                    <button
                      id="retry-chat-btn"
                      onClick={handleRetry}
                      className="flex shrink-0 items-center gap-1.5 rounded-xl bg-pink px-3 py-1.5 text-caption font-medium text-white transition-colors hover:bg-pink/90"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                      Retry
                    </button>
                  </div>
                )}

                {/* Suggested questions (only when no conversation yet) */}
                {conversationHistory.length === 0 && !chatMutation.isPending && (
                  <div className="flex flex-wrap gap-2">
                    {[
                      "What should I practice today?",
                      "What are my weak topics?",
                      "How has my performance changed recently?",
                      "Create a seven-day revision plan.",
                    ].map((question) => (
                      <button
                        key={question}
                        onClick={() => setMessage(question)}
                        className="rounded-full border border-border bg-muted/50 px-3 py-1.5 text-caption text-subtle transition-colors hover:bg-muted"
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                )}

                {/* Unconfigured notice (after first response reveals it) */}
                {chatMutation.data?.is_configured === false && (
                  <p className="text-caption text-subtle rounded-2xl bg-muted/50 p-3">
                    AI Coach is not configured. Set{" "}
                    <code className="font-mono">GEMINI_API_KEY</code> in the backend
                    environment to enable chat.
                  </p>
                )}

                {/* Input */}
                <div className="flex gap-2">
                  <textarea
                    id="ai-coach-message-input"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about your performance, strengths, weaknesses, or request a study plan… (Enter to send, Shift+Enter for newline)"
                    className="flex-1 rounded-2xl border border-border bg-background px-4 py-3 text-caption outline-none focus:border-violet resize-none"
                    rows={2}
                    disabled={chatMutation.isPending}
                  />
                  <button
                    id="ai-coach-send-btn"
                    onClick={() => handleSendMessage()}
                    disabled={!message.trim() || chatMutation.isPending}
                    className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-violet text-white transition-colors hover:bg-violet/90 disabled:opacity-50 disabled:cursor-not-allowed"
                    title="Send message"
                  >
                    {chatMutation.isPending ? (
                      <Loader2 className="h-5 w-5 animate-spin" />
                    ) : (
                      <Send className="h-5 w-5" />
                    )}
                  </button>
                </div>
              </div>
            </Panel>
          </>
        )}
      </div>
    </AppShell>
  );
}
