import { createFileRoute } from "@tanstack/react-router";
import { Plus } from "lucide-react";

import { GoalCard } from "@/components/dashboard/GoalCard";
import { AppShell } from "@/components/layout/AppShell";
import { Panel } from "@/components/ui-kit/Panel";
import { goals } from "@/lib/mock-data";

const title = "Goals — CodePulse";
const description =
  "Milestone cards for problem counts, rating targets, streaks and roadmaps, each with a rounded progress bar and pacing note.";

export const Route = createFileRoute("/goals")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: Goals,
});

function Goals() {
  return (
    <AppShell title="Goals" subtitle="Small targets, kept visible.">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <p className="text-body text-muted-foreground">5 active goals · 3 on pace</p>
          <button className="inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-caption font-semibold text-primary-foreground press">
            <Plus className="h-4 w-4" strokeWidth={1.8} />
            New goal
          </button>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
          {goals.map((g) => (
            <GoalCard key={g.title} {...g} />
          ))}
        </div>

        <Panel title="Weekly cadence" caption="Target vs. actual, last four weeks">
          <ul className="space-y-5">
            {[
              { week: "Week 27", target: 30, actual: 23 },
              { week: "Week 26", target: 30, actual: 31 },
              { week: "Week 25", target: 25, actual: 26 },
              { week: "Week 24", target: 25, actual: 19 },
            ].map((w) => {
              const pct = Math.min(100, Math.round((w.actual / w.target) * 100));
              return (
                <li key={w.week}>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-caption text-muted-foreground">{w.week}</span>
                    <span className="text-caption font-semibold">
                      {w.actual} / {w.target}
                    </span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${pct}%`,
                        background: pct >= 100 ? "var(--success)" : "var(--pastel-blue)",
                      }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>
        </Panel>
      </div>
    </AppShell>
  );
}
