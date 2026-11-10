import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import {
  AlertCircle,
  CalendarClock,
  Clock3,
  ExternalLink,
  Loader2,
  PlayCircle,
  RefreshCw,
  Sparkles,
  Target,
} from "lucide-react";
import * as React from "react";

import { getStudyPlan, type StudyPlanResponse } from "@/api/recommendations";
import { Pill } from "@/components/ui-kit/Panel";
import { ActionButton, AnimatedBar, AnimatedCounter, Skeleton } from "@/components/ui-kit/motion";
import { cn } from "@/lib/utils";

function useCountdown(targetIso: string | null | undefined) {
  const [now, setNow] = React.useState(() => Date.now());
  React.useEffect(() => {
    if (!targetIso) return;
    const id = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(id);
  }, [targetIso]);
  if (!targetIso) return null;
  const diff = new Date(targetIso).getTime() - now;
  if (diff <= 0) return "Starting soon";
  const days = Math.floor(diff / 86_400_000);
  const hours = Math.floor((diff % 86_400_000) / 3_600_000);
  const minutes = Math.floor((diff % 3_600_000) / 60_000);
  if (days > 0) return `Starts in ${days}d ${hours}h`;
  if (hours > 0) return `Starts in ${hours}h ${minutes}m`;
  return `Starts in ${Math.max(minutes, 1)}m`;
}

function difficultyTone(difficulty: string | null) {
  if (difficulty === "Easy") return "bg-green-soft text-green";
  if (difficulty === "Medium") return "bg-yellow-soft text-yellow";
  if (difficulty === "Hard") return "bg-pink-soft text-pink";
  return "bg-muted text-subtle";
}

function platformLabel(platform: string) {
  return platform.charAt(0).toUpperCase() + platform.slice(1);
}

export function StudyPlanSection() {
  const {
    data: plan,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["study-plan"],
    queryFn: () => getStudyPlan(),
  });

  if (isLoading) {
    return (
      <section className="surface-card p-6 md:p-8">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="mt-4 h-8 w-2/3" />
        <div className="mt-6 space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-16 w-full rounded-2xl" />
          ))}
        </div>
      </section>
    );
  }

  if (error || !plan) {
    return (
      <section className="surface-card p-6">
        <div className="flex flex-col items-center gap-4 py-8 text-center">
          <AlertCircle className="h-8 w-8 text-pink" />
          <p className="text-body text-muted-foreground">
            Your study plan could not be loaded right now.
          </p>
          <ActionButton variant="ghost" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
            Try again
          </ActionButton>
        </div>
      </section>
    );
  }

  return <StudyPlanBody plan={plan} onRefresh={() => refetch()} />;
}

function StudyPlanBody({ plan, onRefresh }: { plan: StudyPlanResponse; onRefresh: () => void }) {
  const countdown = useCountdown(plan.upcoming_contest?.start_time);
  const pct =
    plan.daily.daily_target && plan.daily.daily_target > 0
      ? Math.min(100, Math.round((plan.daily.solved_today / plan.daily.daily_target) * 100))
      : null;
  const firstProblem = plan.problems[0];

  return (
    <section className="surface-card overflow-hidden">
      <div className="grid gap-8 p-6 md:p-8 lg:grid-cols-[1.5fr_1fr]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <Pill tone="green">
              <Sparkles className="h-3.5 w-3.5" strokeWidth={1.6} />
              Today&apos;s study plan
            </Pill>
            <button
              onClick={onRefresh}
              className="flex h-8 w-8 items-center justify-center rounded-full bg-muted text-subtle transition-colors hover:bg-muted/70"
              title="Refresh study plan"
            >
              <RefreshCw className="h-3.5 w-3.5" strokeWidth={1.6} />
            </button>
          </div>

          {plan.has_sufficient_data ? (
            <>
              <h2 className="text-h2 mt-5">
                {plan.focus_topic
                  ? `${plan.problems_planned} problem${plan.problems_planned === 1 ? "" : "s"} on ${plan.focus_topic}.`
                  : "Your next practice session."}
              </h2>
              {plan.focus_reason && (
                <p className="text-body mt-2 max-w-xl text-muted-foreground">{plan.focus_reason}</p>
              )}

              {plan.problems.length > 0 ? (
                <ul className="mt-6 space-y-3">
                  {plan.problems.map((p, i) => (
                    <li key={p.id}>
                      <a
                        href={p.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="lift grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-2xl border border-border bg-muted/40 p-4 transition-colors hover:bg-muted/70"
                      >
                        <span className="text-label flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-card font-semibold">
                          {i + 1}
                        </span>
                        <div className="min-w-0">
                          <p className="text-caption truncate font-semibold">{p.title}</p>
                          <p className="text-label mt-0.5 flex flex-wrap items-center gap-1.5 truncate text-subtle">
                            <span>{platformLabel(p.platform)}</span>
                            {p.difficulty && (
                              <span
                                className={cn(
                                  "rounded-full px-1.5 py-px text-[10px] font-medium",
                                  difficultyTone(p.difficulty),
                                )}
                              >
                                {p.difficulty}
                              </span>
                            )}
                            {p.topics.slice(0, 2).map((t) => (
                              <span key={t} className="truncate">
                                · {t}
                              </span>
                            ))}
                          </p>
                        </div>
                        <span className="text-label flex shrink-0 items-center gap-1.5 text-subtle">
                          <Clock3 className="h-3.5 w-3.5" strokeWidth={1.6} />
                          {p.estimated_minutes}m
                        </span>
                      </a>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-body mt-6 text-muted-foreground">
                  No unsolved problems matched your focus area in the local catalog yet.
                </p>
              )}

              <div className="mt-6 flex flex-wrap gap-3">
                <div className="flex items-center gap-3 rounded-2xl bg-blue-soft px-4 py-3">
                  <Clock3 className="h-[18px] w-[18px]" strokeWidth={1.6} />
                  <div>
                    <p className="text-label uppercase text-subtle">Estimated session</p>
                    <p className="text-card-title">
                      <AnimatedCounter value={plan.total_estimated_minutes} suffix=" min" />
                    </p>
                  </div>
                </div>
                {plan.focus_topic && (
                  <div className="flex items-center gap-3 rounded-2xl bg-violet-soft px-4 py-3">
                    <Target className="h-[18px] w-[18px]" strokeWidth={1.6} />
                    <div>
                      <p className="text-label uppercase text-subtle">Focus topic</p>
                      <p className="text-card-title">{plan.focus_topic}</p>
                    </div>
                  </div>
                )}
              </div>
              <p className="text-caption mt-3 text-subtle">{plan.estimate_note}</p>
            </>
          ) : (
            <div className="mt-5">
              <h2 className="text-h2">No study plan yet.</h2>
              <p className="text-body mt-2 max-w-xl text-muted-foreground">
                Sync a platform and solve some problems — your plan is generated from your real
                submission history, never sample data.
              </p>
              <Link to="/platforms" className="mt-4 inline-block">
                <ActionButton variant="ghost">
                  <ExternalLink className="h-4 w-4" />
                  Connect a platform
                </ActionButton>
              </Link>
            </div>
          )}

          {plan.limitations.length > 0 && plan.has_sufficient_data && (
            <ul className="mt-4 space-y-1">
              {plan.limitations.map((lim) => (
                <li key={lim} className="text-caption text-subtle">
                  · {lim}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex flex-col justify-between gap-6 rounded-2xl bg-green-soft/70 p-6">
          <div>
            <p className="text-label uppercase text-subtle">Daily progress</p>
            {plan.daily.daily_target != null ? (
              <>
                <p className="text-h2 mt-1">
                  {plan.daily.solved_today} / {plan.daily.daily_target}
                </p>
                <div className="mt-4">
                  <AnimatedBar value={pct ?? 0} color="var(--success)" />
                </div>
                <p className="text-caption mt-3 text-muted-foreground">
                  {plan.daily.target_label ?? "Problems solved today (local day)."}
                </p>
              </>
            ) : (
              <>
                <p className="text-h2 mt-1">{plan.daily.solved_today} solved today</p>
                <p className="text-caption mt-3 text-muted-foreground">
                  No daily target yet —{" "}
                  <Link
                    to="/goals"
                    className="font-medium text-violet underline underline-offset-2"
                  >
                    create a goal
                  </Link>{" "}
                  to get a personalized daily target.
                </p>
              </>
            )}
          </div>

          <div className="rounded-2xl bg-card p-4">
            <p className="text-label flex items-center gap-2 uppercase text-subtle">
              <CalendarClock className="h-3.5 w-3.5" strokeWidth={1.6} />
              Upcoming contest
            </p>
            {plan.upcoming_contest ? (
              <>
                <a
                  href={plan.upcoming_contest.contest_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-caption mt-2 block truncate font-semibold hover:text-violet"
                >
                  {plan.upcoming_contest.title}
                </a>
                <p className="text-label mt-1 text-subtle">
                  {platformLabel(plan.upcoming_contest.platform)} ·{" "}
                  {new Date(plan.upcoming_contest.start_time).toLocaleString(undefined, {
                    dateStyle: "medium",
                    timeStyle: "short",
                  })}
                </p>
                {countdown && (
                  <Pill tone="yellow" className="mt-3">
                    {countdown}
                  </Pill>
                )}
              </>
            ) : (
              <p className="text-caption mt-2 text-muted-foreground">
                No upcoming contests found. Contest data syncs from your connected platforms.
              </p>
            )}
          </div>

          {firstProblem && (
            <ActionButton
              className="w-full"
              onClick={() => window.open(firstProblem.url, "_blank", "noopener,noreferrer")}
            >
              <PlayCircle className="h-4 w-4" strokeWidth={1.8} />
              Start practice
            </ActionButton>
          )}
        </div>
      </div>
    </section>
  );
}
