import { createFileRoute } from "@tanstack/react-router";

import { Heatmap } from "@/components/dashboard/Heatmap";
import { RatingChart } from "@/components/dashboard/RatingChart";
import { TopicDonut } from "@/components/dashboard/TopicDonut";
import { AppShell } from "@/components/layout/AppShell";
import { Panel } from "@/components/ui-kit/Panel";
import { platforms } from "@/lib/mock-data";

const title = "Analytics — CodePulse";
const description =
  "Rating progress, topic distribution and submission heatmaps filtered by platform and time range across your competitive programming history.";

export const Route = createFileRoute("/analytics")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: Analytics,
});

function Analytics() {
  return (
    <AppShell title="Analytics" subtitle="Slice your history by platform, topic and time range.">
      <div className="space-y-6">
        <RatingChart />

        <div className="grid gap-6 xl:grid-cols-[1fr_1.2fr]">
          <TopicDonut />
          <Panel title="Difficulty split" caption="Solved problems by difficulty band">
            <ul className="space-y-5">
              {[
                { label: "Easy", value: 912, pct: 40, color: "var(--pastel-green)" },
                { label: "Medium", value: 1043, pct: 46, color: "var(--pastel-yellow)" },
                { label: "Hard", value: 328, pct: 14, color: "var(--pastel-pink)" },
              ].map((d) => (
                <li key={d.label}>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-caption text-muted-foreground">{d.label}</span>
                    <span className="text-caption font-semibold">
                      {d.value.toLocaleString()} · {d.pct}%
                    </span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full"
                      style={{ width: `${d.pct}%`, background: d.color }}
                    />
                  </div>
                </li>
              ))}
            </ul>

            <div className="mt-8 grid gap-4 border-t border-border pt-6 sm:grid-cols-2">
              {platforms.map((p) => (
                <div
                  key={p.key}
                  className="flex items-center justify-between rounded-2xl bg-muted px-4 py-3"
                >
                  <span className="text-caption text-muted-foreground">{p.name}</span>
                  <span className="text-caption font-semibold">{p.solved.toLocaleString()}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>

        <Heatmap />
      </div>
    </AppShell>
  );
}
