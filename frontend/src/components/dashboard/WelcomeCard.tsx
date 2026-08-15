import { Link } from "@tanstack/react-router";
import { RefreshCw, Target, Trophy } from "lucide-react";

import type { DashboardOverview } from "@/api/dashboard";
import type { Platform } from "@/api/dashboard";

function formatLastSynced(lastSyncedAt: string | null) {
  if (!lastSyncedAt) return "Not synced yet";

  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(lastSyncedAt));
}

export function WelcomeCard({
  overview,
  platform,
}: {
  overview: DashboardOverview;
  platform?: Platform;
}) {
  const ratingText = overview.current_rating?.toLocaleString() ?? "Unrated";
  const rankText = overview.rank ?? "No current rank";

  const platformName =
    platform === "leetcode"
      ? "LeetCode"
      : platform === "codeforces"
        ? "Codeforces"
        : platform === "codechef"
          ? "CodeChef"
          : platform === "atcoder"
            ? "AtCoder"
            : platform || "Platform";

  return (
    <section className="surface-card overflow-hidden">
      <div className="grid gap-8 p-6 md:p-8 lg:grid-cols-[1.4fr_1fr]">
        <div className="flex flex-col justify-between gap-8">
          <div>
            <span className="text-label inline-flex items-center gap-2 rounded-full bg-yellow-soft px-3 py-1 uppercase">
              {platformName} profile
            </span>
            <h2 className="text-h2 mt-5">Welcome back, @{overview.username}.</h2>
            <p className="text-body mt-2 max-w-lg text-muted-foreground">
              Your synced {platformName} record is ready to explore.
            </p>
          </div>

          <p className="text-caption flex items-center gap-2 text-muted-foreground">
            <RefreshCw className="h-4 w-4 shrink-0 text-subtle" strokeWidth={1.6} />
            Last synced {formatLastSynced(overview.last_synced_at)}
          </p>
        </div>

        <div className="flex flex-col justify-center gap-4 rounded-2xl bg-green-soft/70 p-6">
          <div className="flex items-center gap-3 rounded-2xl bg-card/70 p-4">
            <Trophy className="h-[18px] w-[18px]" strokeWidth={1.6} />
            <div>
              <p className="text-label uppercase text-subtle">Current rating</p>
              <p className="text-card-title">
                {ratingText}{" "}
                <span className="text-caption font-medium text-muted-foreground">· {rankText}</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3 rounded-2xl bg-card/70 p-4">
            <Target className="h-[18px] w-[18px]" strokeWidth={1.6} />
            <div>
              <p className="text-label uppercase text-subtle">Problems solved</p>
              <p className="text-card-title">{overview.total_problems_solved.toLocaleString()}</p>
            </div>
          </div>
          <Link
            to="/platforms"
            className="press inline-flex items-center justify-center rounded-full bg-primary px-5 py-2.5 text-caption font-semibold text-primary-foreground"
          >
            Manage platform
          </Link>
        </div>
      </div>
    </section>
  );
}
