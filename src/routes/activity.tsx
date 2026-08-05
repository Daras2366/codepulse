import { createFileRoute } from "@tanstack/react-router";

import { ActivityTimeline } from "@/components/dashboard/ActivityTimeline";
import { Heatmap } from "@/components/dashboard/Heatmap";
import { AppShell } from "@/components/layout/AppShell";
import { Panel } from "@/components/ui-kit/Panel";

const title = "Submission Activity — CodePulse";
const description =
  "A year of submissions in a rounded contribution heatmap, paired with a timeline of solved problems, contests and milestones.";

export const Route = createFileRoute("/activity")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: ActivityPage,
});

function ActivityPage() {
  return (
    <AppShell title="Submission Activity" subtitle="One square per day, one year of practice.">
      <div className="space-y-6">
        <Heatmap />
        <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
          <ActivityTimeline />
          <Panel title="This week" caption="Rolling seven-day summary">
            <ul className="space-y-4">
              {[
                { label: "Problems solved", value: "23" },
                { label: "Hard problems", value: "6" },
                { label: "Avg. solve time", value: "18m 40s" },
                { label: "Contests entered", value: "2" },
                { label: "Accuracy", value: "81%" },
              ].map((s) => (
                <li
                  key={s.label}
                  className="flex items-center justify-between rounded-2xl bg-muted px-4 py-3"
                >
                  <span className="text-caption text-muted-foreground">{s.label}</span>
                  <span className="text-caption font-semibold">{s.value}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
