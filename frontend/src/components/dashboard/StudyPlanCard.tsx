import { CalendarClock, Clock3, PlayCircle, Sparkles, Target } from "lucide-react";

import { Pill } from "@/components/ui-kit/Panel";
import { ActionButton, AnimatedBar, AnimatedCounter } from "@/components/ui-kit/motion";
import { studyPlan } from "@/lib/mock-data";

export function StudyPlanCard() {
  const pct = Math.round((studyPlan.dailyDone / studyPlan.dailyTarget) * 100);

  return (
    <section className="surface-card overflow-hidden">
      <div className="grid gap-8 p-6 md:p-8 lg:grid-cols-[1.5fr_1fr]">
        <div className="min-w-0">
          <Pill tone="green">
            <Sparkles className="h-3.5 w-3.5" strokeWidth={1.6} />
            Study plan
          </Pill>
          {/* NOTE: This card uses placeholder data. Personalized plans are not yet implemented. */}
          <h2 className="text-h2 mt-5">Three problems on {studyPlan.topic}.</h2>
          <p className="text-body mt-2 max-w-xl text-muted-foreground">
            Sample study plan — personalized plans coming soon.
          </p>

          <ul className="mt-6 space-y-3">
            {studyPlan.problems.map((p, i) => (
              <li
                key={p.title}
                className="lift grid grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-3 rounded-2xl border border-border bg-muted/40 p-4"
              >
                <span className="text-label flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-card font-semibold">
                  {i + 1}
                </span>
                <div className="min-w-0">
                  <p className="text-caption truncate font-semibold">{p.title}</p>
                  <p className="text-label truncate text-subtle">
                    {p.platform} · {p.difficulty}
                  </p>
                </div>
                <span className="text-label flex shrink-0 items-center gap-1.5 text-subtle">
                  <Clock3 className="h-3.5 w-3.5" strokeWidth={1.6} />
                  {p.minutes}m
                </span>
              </li>
            ))}
          </ul>

          <div className="mt-6 flex flex-wrap gap-3">
            <div className="flex items-center gap-3 rounded-2xl bg-blue-soft px-4 py-3">
              <Clock3 className="h-[18px] w-[18px]" strokeWidth={1.6} />
              <div>
                <p className="text-label uppercase text-subtle">Estimated session</p>
                <p className="text-card-title">
                  <AnimatedCounter value={studyPlan.durationMinutes} suffix=" min" />
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-2xl bg-violet-soft px-4 py-3">
              <Target className="h-[18px] w-[18px]" strokeWidth={1.6} />
              <div>
                <p className="text-label uppercase text-subtle">Focus topic</p>
                <p className="text-card-title">{studyPlan.topic}</p>
              </div>
            </div>
          </div>
        </div>

        <div className="flex flex-col justify-between gap-6 rounded-2xl bg-green-soft/70 p-6">
          <div>
            <p className="text-label uppercase text-subtle">Daily target</p>
            <p className="text-h2 mt-1">
              {studyPlan.dailyDone} / {studyPlan.dailyTarget}
            </p>
            <div className="mt-4">
              <AnimatedBar value={pct} color="var(--success)" />
            </div>
            <p className="text-caption mt-3 text-muted-foreground">
              {studyPlan.dailyTarget - studyPlan.dailyDone} problems left to hit today's target.
            </p>
          </div>

          <div className="rounded-2xl bg-card p-4">
            <p className="text-label flex items-center gap-2 uppercase text-subtle">
              <CalendarClock className="h-3.5 w-3.5" strokeWidth={1.6} />
              Upcoming contest
            </p>
            <p className="text-caption mt-2 font-semibold">{studyPlan.upcomingContest.name}</p>
            <p className="text-label mt-1 text-subtle">{studyPlan.upcomingContest.date}</p>
            <Pill tone="yellow" className="mt-3">
              Starts in {studyPlan.upcomingContest.startsIn}
            </Pill>
          </div>

          <ActionButton className="w-full">
            <PlayCircle className="h-4 w-4" strokeWidth={1.8} />
            Start practice
          </ActionButton>
        </div>
      </div>
    </section>
  );
}
