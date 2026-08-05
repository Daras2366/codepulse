import { createFileRoute } from "@tanstack/react-router";
import { ArrowUpRight, Bot, BrainCircuit, Sparkles, TrendingUp, Waypoints } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { StudyPlanCard } from "@/components/dashboard/StudyPlanCard";
import { Panel, Pill } from "@/components/ui-kit/Panel";
import { recommended, strengths, weaknesses } from "@/lib/mock-data";

const title = "AI Coach — CodePulse";
const description =
  "AI-generated strengths, weaknesses, recommended problems, interview readiness and a 30-day rating forecast for your practice.";

export const Route = createFileRoute("/ai-coach")({
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

function Meter({ label, score, color }: { label: string; score: number; color: string }) {
  return (
    <li>
      <div className="mb-2 flex items-center justify-between gap-4">
        <span className="text-caption text-muted-foreground">{label}</span>
        <span className="text-caption font-semibold">{score}</span>
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full rounded-full" style={{ width: `${score}%`, background: color }} />
      </div>
    </li>
  );
}

function AICoach() {
  const readiness = 78;
  const r = 52;
  const c = 2 * Math.PI * r;

  return (
    <AppShell title="AI Coach" subtitle="A weekly read on what to practice next — and why.">
      <div className="space-y-6">
        <StudyPlanCard />

        <section className="surface-card overflow-hidden">
          <div className="grid gap-8 p-6 md:p-8 lg:grid-cols-[1.5fr_1fr]">
            <div>
              <Pill tone="violet">
                <Sparkles className="h-3.5 w-3.5" strokeWidth={1.6} />
                Weekly AI summary
              </Pill>
              <h2 className="text-h2 mt-5">
                Your graph work is compounding. DP is the bottleneck.
              </h2>
              <p className="text-body mt-3 max-w-2xl text-muted-foreground">
                You solved 23 problems this week with 81% accuracy, and your Codeforces curve gained
                34 points on the back of two clean graph implementations. The pattern that costs you
                most is digit and bitmask DP: three of your four contest misses this month were
                DP-tagged. Four focused sessions should close it.
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <div className="flex items-center gap-3 rounded-2xl bg-blue-soft px-4 py-3">
                  <TrendingUp className="h-[18px] w-[18px]" strokeWidth={1.6} />
                  <div>
                    <p className="text-label uppercase text-subtle">Expected in 30 days</p>
                    <p className="text-card-title">1,904 CF</p>
                  </div>
                </div>
                <div className="flex items-center gap-3 rounded-2xl bg-yellow-soft px-4 py-3">
                  <Waypoints className="h-[18px] w-[18px]" strokeWidth={1.6} />
                  <div>
                    <p className="text-label uppercase text-subtle">Confidence</p>
                    <p className="text-card-title">High · 84%</p>
                  </div>
                </div>
              </div>
            </div>

            <div className="flex flex-col items-center justify-center gap-5 rounded-2xl bg-violet-soft/70 p-6">
              <div className="relative h-[148px] w-[148px]">
                <svg viewBox="0 0 120 120" className="h-full w-full -rotate-90">
                  <circle
                    cx="60"
                    cy="60"
                    r={r}
                    fill="none"
                    stroke="var(--border)"
                    strokeWidth="10"
                  />
                  <circle
                    cx="60"
                    cy="60"
                    r={r}
                    fill="none"
                    stroke="var(--pastel-violet)"
                    strokeWidth="10"
                    strokeLinecap="round"
                    strokeDasharray={c}
                    strokeDashoffset={c * (1 - readiness / 100)}
                    style={{ transition: "stroke-dashoffset 900ms cubic-bezier(0.22,1,0.36,1)" }}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className="text-h1">{readiness}</span>
                  <span className="text-label text-subtle">readiness</span>
                </div>
              </div>
              <p className="text-caption text-center text-muted-foreground">
                Ready for mid-level loops. Systems-heavy rounds need two more mock sessions.
              </p>
            </div>
          </div>
        </section>

        <div className="grid gap-6 xl:grid-cols-2">
          <Panel
            title="Strengths"
            caption="Patterns you convert reliably under contest pressure"
            action={
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-green-soft">
                <BrainCircuit className="h-4 w-4" strokeWidth={1.6} />
              </span>
            }
          >
            <ul className="space-y-5">
              {strengths.map((s) => (
                <Meter key={s.label} label={s.label} score={s.score} color="var(--pastel-green)" />
              ))}
            </ul>
          </Panel>

          <Panel
            title="Weaknesses"
            caption="Where your contest attempts stall out"
            action={
              <span className="flex h-9 w-9 items-center justify-center rounded-full bg-pink-soft">
                <Bot className="h-4 w-4" strokeWidth={1.6} />
              </span>
            }
          >
            <ul className="space-y-5">
              {weaknesses.map((s) => (
                <Meter key={s.label} label={s.label} score={s.score} color="var(--pastel-pink)" />
              ))}
            </ul>
          </Panel>
        </div>

        <Panel
          title="Recommended problems"
          caption="Chosen from your gaps, not from a generic list"
        >
          <ul className="grid gap-4 sm:grid-cols-2">
            {recommended.map((p) => (
              <li
                key={p.title}
                className="lift group rounded-2xl border border-border bg-muted/50 p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-card-title">{p.title}</p>
                    <p className="text-label mt-1 text-subtle">
                      {p.platform} · {p.difficulty} · {p.topic}
                    </p>
                  </div>
                  <ArrowUpRight
                    className="h-4 w-4 shrink-0 text-subtle transition-transform duration-200 group-hover:-translate-y-0.5 group-hover:translate-x-0.5"
                    strokeWidth={1.6}
                  />
                </div>
                <p className="text-caption mt-4 text-muted-foreground">{p.why}</p>
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </AppShell>
  );
}
