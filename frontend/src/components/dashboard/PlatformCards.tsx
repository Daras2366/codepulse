import { Line, LineChart, ResponsiveContainer, Tooltip, type TooltipProps } from "recharts";

import type { DashboardOverview, DashboardPlatformSummary, DashboardRating } from "@/api/dashboard";
import { AnimatedCounter } from "@/components/ui-kit/motion";

export function PlatformCards({
  overview,
  rating,
}: {
  overview: DashboardOverview | DashboardPlatformSummary;
  rating?: DashboardRating | undefined;
}) {
  const spark =
    rating?.history.map((item) => ({ rating: item.rating, date: item.recorded_at })) ?? [];

  // Platform-specific styling
  const platformConfig = {
    leetcode: {
      short: "LC",
      name: "LeetCode",
      tint: "bg-yellow-soft",
      color: "var(--pastel-yellow)",
    },
    codeforces: {
      short: "CF",
      name: "Codeforces",
      tint: "bg-blue-soft",
      color: "var(--pastel-blue)",
    },
    codechef: {
      short: "CC",
      name: "CodeChef",
      tint: "bg-green-soft",
      color: "var(--pastel-green)",
    },
    atcoder: {
      short: "AC",
      name: "AtCoder",
      tint: "bg-pink-soft",
      color: "var(--pastel-pink)",
    },
  };

  const config = platformConfig[overview.platform] || platformConfig.codeforces;

  return (
    <article className="surface-card lift group max-w-md p-6">
      <div className="flex min-w-0 items-center gap-3">
        <span
          className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl ${config.tint} text-caption font-bold transition-transform duration-300 group-hover:scale-105`}
        >
          {config.short}
        </span>
        <div className="min-w-0">
          <p className="text-card-title truncate">{config.name}</p>
          <p className="text-label text-subtle">{overview.rank ?? "No current rank"}</p>
        </div>
      </div>

      <div className="mt-6 flex items-end justify-between gap-4">
        <div>
          <p className="text-label uppercase text-subtle">Rating</p>
          <p className="text-h2">
            {overview.current_rating === null ? (
              "Unrated"
            ) : (
              <AnimatedCounter value={overview.current_rating} />
            )}
          </p>
        </div>
        {spark.length > 0 && (
          <div className="h-12 w-24 shrink-0 sm:w-28">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={spark}>
                <Tooltip
                  content={({ active, payload }: TooltipProps<number, string>) =>
                    active && payload?.length ? (
                      <div className="surface-card px-3 py-1.5">
                        <p className="text-label text-muted-foreground">
                          {payload[0]?.value} rating
                        </p>
                      </div>
                    ) : null
                  }
                />
                <Line
                  type="monotone"
                  dataKey="rating"
                  stroke={config.color}
                  strokeWidth={2.5}
                  dot={false}
                  activeDot={{ r: 3.5, strokeWidth: 2, stroke: "var(--card)" }}
                  animationDuration={900}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-border pt-5">
        <div>
          <dt className="text-label uppercase text-subtle">Peak</dt>
          <dd className="text-caption font-semibold">
            {overview.max_rating?.toLocaleString() ?? "—"}
          </dd>
        </div>
        <div>
          <dt className="text-label uppercase text-subtle">Solved</dt>
          <dd className="text-caption font-semibold">
            {overview.total_problems_solved.toLocaleString()}
          </dd>
        </div>
        {overview.rank && (
          <div className="col-span-2">
            <dt className="text-label uppercase text-subtle">Global rank</dt>
            <dd className="text-caption font-semibold">{overview.rank}</dd>
          </div>
        )}
      </dl>
    </article>
  );
}
