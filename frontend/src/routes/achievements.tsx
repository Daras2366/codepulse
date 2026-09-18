import { createFileRoute, redirect } from "@tanstack/react-router";
import { CheckCircle2, Lock, Medal, RefreshCw } from "lucide-react";

import { hasAccessToken } from "@/api/client";

import { getDashboardErrorMessage } from "@/api/client";
import { AppShell } from "@/components/layout/AppShell";
import { ActionButton, EmptyState, ErrorState, Skeleton } from "@/components/ui-kit/motion";
import { Pill } from "@/components/ui-kit/Panel";
import { useAchievements } from "@/hooks/useAchievements";
import { cn } from "@/lib/utils";

const title = "Achievements — CodePulse";
const description =
  "Badges earned across problem solving, contests and ratings, plus the milestones still waiting to be unlocked.";

export const Route = createFileRoute("/achievements")({
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
  component: Achievements,
});

function formatEarnedDate(dateString: string) {
  const d = new Date(dateString);
  if (isNaN(d.getTime())) return dateString;
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric", year: "numeric" }).format(
    d,
  );
}

function Achievements() {
  const {
    authenticated,
    catalog,
    earned,
    isLoading,
    error,
    refetch,
    evaluate,
    isEvaluating,
    evalResult,
    evalError,
  } = useAchievements();

  if (isLoading) {
    return (
      <AppShell title="Achievements" subtitle="Quiet proof of the hours you put in.">
        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3" aria-busy>
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} className="h-44 w-full rounded-[20px]" />
          ))}
        </div>
      </AppShell>
    );
  }

  if (error) {
    return (
      <AppShell title="Achievements" subtitle="Quiet proof of the hours you put in.">
        <ErrorState description={getDashboardErrorMessage(error)} onRetry={refetch} />
      </AppShell>
    );
  }

  const earnedMap = new Map(earned.map((item) => [item.achievement_id, item.earned_at]));

  return (
    <AppShell title="Achievements" subtitle="Quiet proof of the hours you put in.">
      <div className="space-y-6">
        {authenticated && (
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="text-body text-muted-foreground">
              {earned.length} of {catalog.length} achievements unlocked
            </p>
            <ActionButton variant="ghost" disabled={isEvaluating} onClick={() => void evaluate()}>
              <RefreshCw
                className={cn("h-4 w-4", isEvaluating && "animate-spin")}
                strokeWidth={1.8}
              />
              {isEvaluating ? "Evaluating…" : "Evaluate achievements"}
            </ActionButton>
          </div>
        )}

        {evalResult && (
          <div className="rounded-2xl bg-green-soft p-4 text-caption font-medium">
            <div className="flex items-center gap-2 text-foreground">
              <CheckCircle2 className="h-4 w-4 text-[var(--success)]" />
              <span>
                Evaluation complete: {evalResult.newly_granted} new achievement
                {evalResult.newly_granted === 1 ? "" : "s"} granted!
              </span>
            </div>
            {evalResult.achievement_names.length > 0 && (
              <p className="mt-1 text-muted-foreground">
                Unlocked: {evalResult.achievement_names.join(", ")}
              </p>
            )}
          </div>
        )}

        {evalError ? (
          <div className="rounded-2xl bg-destructive/10 p-4 text-caption text-destructive">
            {getDashboardErrorMessage(evalError)}
          </div>
        ) : null}

        {catalog.length === 0 ? (
          <EmptyState
            title="No achievements catalog available"
            description="Achievements catalog could not be loaded."
          />
        ) : (
          <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
            {catalog.map((a) => {
              const earnedAt = earnedMap.get(a.id);
              const unlocked = earnedAt !== undefined;

              return (
                <article
                  key={a.id}
                  className={cn(
                    "lift flex flex-col justify-between rounded-[20px] border border-border p-6",
                    unlocked ? "bg-green-soft/50 border-emerald-500/20" : "bg-card opacity-70",
                  )}
                >
                  <div>
                    <span
                      className={cn(
                        "flex h-12 w-12 items-center justify-center rounded-2xl",
                        unlocked ? "bg-card shadow-sm" : "bg-muted",
                      )}
                    >
                      {unlocked ? (
                        <Medal className="h-5 w-5 text-emerald-600" strokeWidth={1.6} />
                      ) : (
                        <Lock className="h-5 w-5 text-subtle" strokeWidth={1.6} />
                      )}
                    </span>
                    <h3 className="text-card-title mt-5">{a.name}</h3>
                    <p className="text-caption mt-1.5 text-muted-foreground">{a.description}</p>
                  </div>

                  <div className="mt-5 flex items-center justify-between">
                    <Pill tone={unlocked ? "green" : "neutral"}>
                      {unlocked ? "Unlocked" : "Locked"}
                    </Pill>
                    {unlocked && (
                      <span className="text-label text-subtle">
                        Earned {formatEarnedDate(earnedAt)}
                      </span>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </div>
    </AppShell>
  );
}
