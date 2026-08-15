import type { AnalyticsContestEntry } from "@/api/analytics";
import type { DashboardContests } from "@/api/dashboard";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui-kit/motion";
import { Panel, Pill } from "@/components/ui-kit/Panel";
import { cn } from "@/lib/utils";

function deltaClass(delta: number | null) {
  return cn(
    delta !== null && delta > 0 && "text-[var(--success)]",
    delta !== null && delta < 0 && "text-[var(--danger)]",
    (delta === null || delta === 0) && "text-muted-foreground",
  );
}

type GenericContest = {
  contest_name: string;
  start_time?: string;
  date?: string;
  rank: number | null;
  rating_change: number | null;
  solved?: number;
  platform?: string;
};

export function ContestsTable({
  limit,
  contests,
  isLoading = false,
  error,
  onRetry,
}: {
  limit?: number;
  contests?: DashboardContests | { contests: AnalyticsContestEntry[] } | undefined;
  isLoading?: boolean;
  error?: string | undefined;
  onRetry?: (() => void) | undefined;
}) {
  const sourceRows = contests
    ? contests.contests.map((contest: GenericContest) => {
        const rawDate = contest.start_time ?? contest.date ?? "";
        const dateObj = new Date(rawDate);
        const formattedDate = isNaN(dateObj.getTime())
          ? rawDate
          : new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(dateObj);
        return {
          name: contest.contest_name,
          platform: (contest as any).platform || "Codeforces",
          date: formattedDate,
          rank: contest.rank,
          delta: contest.rating_change,
          status: contest.rating_change === null ? "Unrated" : "Rated",
        };
      })
    : [];
  const rows = limit ? sourceRows.slice(0, limit) : sourceRows;

  return (
    <Panel title="Recent contests" caption="Your synced contest history" bodyClassName="md:-mx-2">
      {isLoading ? (
        <ListSkeleton rows={limit ?? 4} />
      ) : error ? (
        <ErrorState description={error} onRetry={onRetry} />
      ) : rows.length === 0 ? (
        <EmptyState
          title="No contests yet"
          description="Enter a rated contest and sync your profile to see it here."
        />
      ) : (
        <>
          <ul className="space-y-3 md:hidden">
            {rows.map((c, index) => (
              <li
                key={`${c.name}-${index}`}
                className="lift rounded-2xl border border-border bg-muted/40 p-4"
              >
                <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-3">
                  <div className="min-w-0">
                    <p className="text-caption font-semibold">{c.name}</p>
                    <p className="text-label mt-0.5 text-subtle">
                      {c.platform} · {c.date}
                    </p>
                  </div>
                  <Pill tone={c.status === "Rated" ? "green" : "neutral"}>{c.status}</Pill>
                </div>
                <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-border pt-3">
                  <div>
                    <dt className="text-label uppercase text-subtle">Rank</dt>
                    <dd className="text-caption font-semibold">
                      {c.rank === null ? "—" : `#${c.rank.toLocaleString()}`}
                    </dd>
                  </div>
                  <div className="text-right">
                    <dt className="text-label uppercase text-subtle">Δ Rating</dt>
                    <dd className={cn("text-caption font-semibold", deltaClass(c.delta))}>
                      {c.delta === null ? "—" : `${c.delta > 0 ? "+" : ""}${c.delta}`}
                    </dd>
                  </div>
                </dl>
              </li>
            ))}
          </ul>

          <div className="no-scrollbar hidden overflow-x-auto md:block">
            <table className="w-full min-w-[620px] border-separate border-spacing-y-1.5">
              <thead>
                <tr className="text-label uppercase text-subtle">
                  <th className="px-4 pb-2 text-left font-normal">Contest</th>
                  <th className="px-4 pb-2 text-left font-normal">Platform</th>
                  <th className="px-4 pb-2 text-left font-normal">Date</th>
                  <th className="px-4 pb-2 text-right font-normal">Rank</th>
                  <th className="px-4 pb-2 text-right font-normal">Δ Rating</th>
                  <th className="px-4 pb-2 text-right font-normal">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c, index) => (
                  <tr key={`${c.name}-${index}`} className="group transition-colors">
                    <td className="rounded-l-2xl bg-transparent px-4 py-3.5 transition-colors group-hover:bg-muted">
                      <p className="text-caption font-semibold">{c.name}</p>
                    </td>
                    <td className="text-caption px-4 py-3.5 text-muted-foreground transition-colors group-hover:bg-muted">
                      {c.platform}
                    </td>
                    <td className="text-caption px-4 py-3.5 text-muted-foreground transition-colors group-hover:bg-muted">
                      {c.date}
                    </td>
                    <td className="text-caption px-4 py-3.5 text-right font-semibold transition-colors group-hover:bg-muted">
                      {c.rank === null ? "—" : `#${c.rank.toLocaleString()}`}
                    </td>
                    <td
                      className={cn(
                        "text-caption px-4 py-3.5 text-right font-semibold transition-colors group-hover:bg-muted",
                        deltaClass(c.delta),
                      )}
                    >
                      {c.delta === null ? "—" : `${c.delta > 0 ? "+" : ""}${c.delta}`}
                    </td>
                    <td className="rounded-r-2xl px-4 py-3.5 text-right transition-colors group-hover:bg-muted">
                      <Pill tone={c.status === "Rated" ? "green" : "neutral"}>{c.status}</Pill>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Panel>
  );
}

export function Leaderboard() {
  return (
    <Panel title="Circle Leaderboard" caption="Compare progress with friends">
      <EmptyState
        title="Leaderboard coming soon"
        description="Connect with friends and compare rating movements once social features are released."
      />
    </Panel>
  );
}
