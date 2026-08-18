import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/layout/AppShell";
import { Panel } from "@/components/ui-kit/Panel";
import { platforms } from "@/lib/mock-data";

const title = "Settings — CodePulse";
const description =
  "Manage your CodePulse profile, connected competitive programming handles, daily goal targets and notification preferences.";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: Settings,
});

function Field({ label, value }: { label: string; value: string }) {
  return (
    <label className="block">
      <span className="text-label uppercase text-subtle">{label}</span>
      <input
        defaultValue={value}
        className="mt-2 h-11 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none transition-colors focus:border-violet"
      />
    </label>
  );
}

function Toggle({ label, desc, on }: { label: string; desc: string; on?: boolean }) {
  return (
    <li className="flex items-start justify-between gap-6 py-4 first:pt-0 last:pb-0">
      <div>
        <p className="text-caption font-semibold">{label}</p>
        <p className="text-caption mt-0.5 text-muted-foreground">{desc}</p>
      </div>
      <span
        className={`mt-1 flex h-6 w-11 shrink-0 items-center rounded-full px-0.5 transition-colors ${on ? "bg-success" : "bg-muted"}`}
      >
        <span className={`h-5 w-5 rounded-full bg-card transition-transform ${on ? "translate-x-5" : ""}`} />
      </span>
    </li>
  );
}

function Settings() {
  return (
    <AppShell title="Settings" subtitle="Profile, handles and how loud CodePulse should be.">
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Profile">
          <div className="space-y-5">
            <Field label="Display name" value="Devarsh V." />
            <Field label="Email" value="devarsh@codepulse.dev" />
            <Field label="Country" value="India" />
            <Field label="Daily goal (problems)" value="5" />
            <button className="rounded-full bg-primary px-5 py-2.5 text-caption font-semibold text-primary-foreground transition-transform duration-200 hover:-translate-y-0.5">
              Save changes
            </button>
          </div>
        </Panel>

        <div className="space-y-6">
          <Panel title="Connected handles">
            <div className="space-y-4">
              {platforms.map((p) => (
                <Field key={p.key} label={p.name} value="devarsh" />
              ))}
            </div>
          </Panel>

          <Panel title="Notifications">
            <ul className="divide-y divide-border">
              <Toggle label="Contest reminders" desc="One hour before a rated round starts" on />
              <Toggle label="Streak nudge" desc="Evening reminder if the daily goal is unmet" on />
              <Toggle label="Weekly AI summary" desc="Sunday digest with next week's plan" on />
              <Toggle label="Leaderboard moves" desc="When someone in your circle passes you" />
            </ul>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
