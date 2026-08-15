import { createFileRoute } from "@tanstack/react-router";

import { AppShell } from "@/components/layout/AppShell";
import { Skeleton } from "@/components/ui-kit/motion";
import { Panel } from "@/components/ui-kit/Panel";
import { usePlatforms } from "@/hooks/usePlatforms";
import { useUser } from "@/hooks/useUser";

const title = "Settings — CodePulse";
const description =
  "Manage your CodePulse profile settings, connected handles, and notification preferences.";

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

function Field({
  label,
  value,
  disabled = false,
}: {
  label: string;
  value: string;
  disabled?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-label uppercase text-subtle">{label}</span>
      <input
        defaultValue={value}
        disabled={disabled}
        className="mt-2 h-11 w-full rounded-2xl border border-border bg-background px-4 text-caption outline-none transition-colors focus:border-violet disabled:opacity-60"
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
        <span
          className={`h-5 w-5 rounded-full bg-card transition-transform ${on ? "translate-x-5" : ""}`}
        />
      </span>
    </li>
  );
}

function Settings() {
  const { authenticated, profiles, isLoading: isLoadingProfiles } = usePlatforms();
  const { user, isLoading: isLoadingUser } = useUser();

  const isLoading = isLoadingProfiles || isLoadingUser;

  if (isLoading) {
    return (
      <AppShell title="Settings" subtitle="Profile, handles and preferences.">
        <div className="grid gap-6 xl:grid-cols-2" aria-busy>
          <Skeleton className="h-[320px] w-full rounded-2xl" />
          <Skeleton className="h-[320px] w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  const codeforcesProfile = profiles.find((p) => p.platform === "codeforces");
  const leetcodeProfile = profiles.find((p) => p.platform === "leetcode");
  const codechefProfile = profiles.find((p) => p.platform === "codechef");
  const atcoderProfile = profiles.find((p) => p.platform === "atcoder");

  // Build a meaningful account identity from real data.
  // If signed out or the user fetch failed, show a neutral placeholder.
  const displayUsername = user?.username ?? (authenticated ? "—" : "Signed out");
  const displayEmail = user?.email ?? (authenticated ? "—" : "");
  const displayName = user?.full_name ?? "";

  return (
    <AppShell title="Settings" subtitle="Profile, handles and how loud CodePulse should be.">
      <div className="grid gap-6 xl:grid-cols-2">
        <Panel title="Account Profile">
          <div className="space-y-5">
            <Field label="Username" value={displayUsername} disabled />
            {displayEmail && <Field label="Email" value={displayEmail} disabled />}
            {displayName && <Field label="Full name" value={displayName} disabled />}
            <Field
              label="Connected Codeforces Handle"
              value={codeforcesProfile ? codeforcesProfile.username : "None"}
              disabled
            />
            <button className="rounded-full bg-primary px-5 py-2.5 text-caption font-semibold text-primary-foreground transition-transform duration-200 hover:-translate-y-0.5">
              Save changes
            </button>
          </div>
        </Panel>

        <div className="space-y-6">
          <Panel title="Connected handles">
            <div className="space-y-4">
              <Field
                label="Codeforces"
                value={codeforcesProfile ? `@${codeforcesProfile.username}` : "Not connected"}
                disabled
              />
              <Field
                label="LeetCode"
                value={leetcodeProfile ? `@${leetcodeProfile.username}` : "Not connected"}
                disabled
              />
              <Field
                label="CodeChef"
                value={codechefProfile ? `@${codechefProfile.username}` : "Not connected"}
                disabled
              />
              <Field
                label="AtCoder"
                value={atcoderProfile ? `@${atcoderProfile.username}` : "Not connected"}
                disabled
              />
            </div>
          </Panel>

          <Panel title="Notifications">
            <ul className="divide-y divide-border">
              <Toggle label="Contest reminders" desc="One hour before a rated round starts" on />
              <Toggle label="Streak nudge" desc="Evening reminder if daily goal is unmet" on />
              <Toggle
                label="Weekly summary"
                desc="Digest with next week's practice recommendations"
                on
              />
            </ul>
          </Panel>
        </div>
      </div>
    </AppShell>
  );
}
