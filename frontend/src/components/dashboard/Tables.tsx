import { Panel, Pill } from "@/components/ui-kit/Panel";
import { AnimatedCounter, EmptyState } from "@/components/ui-kit/motion";
import { contests, leaderboard } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

function deltaClass(delta: number) {
  return cn(
    delta > 0 && "text-[var(--success)]",
    delta < 0 && "text-[var(--danger)]",
    delta === 0 && "text-muted-foreground",
  );
}

export function ContestsTable({ limit }: { limit?: number }) {
  const rows = limit ? contests.slice(0, limit) : contests;

  return (
    <Panel title="Recent contests" caption="Rated performance history" bodyClassName="md:-mx-2">
      {rows.length === 0 ? (
        <EmptyState
          title="No contests yet"
          description="Enter a rated round on any connected platform and it will show up here within an hour."
        />
      ) : (
        <>
          <ul className="space-y-3 md:hidden">
            {rows.map((c) => (
              <li key={c.name} className="lift rounded-2xl border border-border bg-muted/40 p-4">
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
                    <dd className="text-caption font-semibold">#{c.rank.toLocaleString()}</dd>
                  </div>
                  <div className="text-right">
                    <dt className="text-label uppercase text-subtle">Δ Rating</dt>
                    <dd className={cn("text-caption font-semibold", deltaClass(c.delta))}>
                      {c.delta > 0 ? "+" : ""}
                      {c.delta}
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
                  <th className="px-4 pb-2 text-left font-normal">Date</th>
                  <th className="px-4 pb-2 text-right font-normal">Rank</th>
                  <th className="px-4 pb-2 text-right font-normal">Δ Rating</th>
                  <th className="px-4 pb-2 text-right font-normal">Status</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((c) => (
                  <tr key={c.name} className="group transition-colors">
                    <td className="rounded-l-2xl bg-transparent px-4 py-3.5 transition-colors group-hover:bg-muted">
                      <p className="text-caption font-semibold">{c.name}</p>
                      <p className="text-label text-subtle">{c.platform}</p>
                    </td>
                    <td className="text-caption px-4 py-3.5 text-muted-foreground transition-colors group-hover:bg-muted">
                      {c.date}
                    </td>
                    <td className="text-caption px-4 py-3.5 text-right font-semibold transition-colors group-hover:bg-muted">
                      #{c.rank.toLocaleString()}
                    </td>
                    <td
                      className={cn(
                        "text-caption px-4 py-3.5 text-right font-semibold transition-colors group-hover:bg-muted",
                        deltaClass(c.delta),
                      )}
                    >
                      {c.delta > 0 ? "+" : ""}
                      {c.delta}
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
    <Panel title="Leaderboard" caption="Your circle, this week">
      {leaderboard.length === 0 ? (
        <EmptyState
          title="No one to compare with yet"
          description="Follow a few friends and their weekly rating movement will appear here."
        />
      ) : (
        <ul className="space-y-1.5">
          {leaderboard.map((u, i) => (
            <li
              key={u.handle}
              className={cn(
                "flex items-center gap-4 rounded-2xl px-3 py-3 transition-all duration-200 hover:-translate-y-px hover:bg-muted",
                u.name === "You" && "bg-yellow-soft/60",
              )}
            >
              <span className="text-caption w-5 text-subtle">{i + 1}</span>
              <span
                className={cn(
                  "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-label font-semibold",
                  u.tint,
                )}
              >
                {u.name
                  .split(" ")
                  .map((n) => n[0])
                  .join("")}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-caption truncate font-semibold">{u.name}</p>
                <p className="text-label truncate text-subtle">
                  {u.handle} · {u.country}
                </p>
              </div>
              <div className="text-right">
                <p className="text-caption font-semibold">
                  <AnimatedCounter value={u.rating} />
                </p>
                <p
                  className={cn(
                    "text-label",
                    u.growth >= 0 ? "text-[var(--success)]" : "text-[var(--danger)]",
                  )}
                >
                  {u.growth >= 0 ? "+" : ""}
                  {u.growth} wk
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
