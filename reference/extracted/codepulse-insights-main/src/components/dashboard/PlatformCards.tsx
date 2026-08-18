import { Line, LineChart, ResponsiveContainer, Tooltip } from "recharts";

import { AnimatedCounter } from "@/components/ui-kit/motion";
import { platforms } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

export function PlatformCards({ columns = 2 }: { columns?: 2 | 4 }) {
  return (
    <div className={cn("grid gap-6", columns === 4 ? "sm:grid-cols-2 xl:grid-cols-4" : "sm:grid-cols-2")}>
      {platforms.map((p) => (
        <article key={p.key} className="surface-card lift group p-6">
          <div className="flex min-w-0 items-center gap-3">
            <span
              className={cn(
                "flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl text-caption font-bold transition-transform duration-300 group-hover:scale-105",
                p.tint,
              )}
            >
              {p.short}
            </span>
            <div className="min-w-0">
              <p className="text-card-title truncate">{p.name}</p>
              <p className="text-label text-subtle">Global rank {p.rank}</p>
            </div>
          </div>

          <div className="mt-6 flex items-end justify-between gap-4">
            <div>
              <p className="text-label uppercase text-subtle">Rating</p>
              <p className="text-h2">
                <AnimatedCounter value={p.rating} />
              </p>
            </div>
            <div className="h-12 w-24 shrink-0 sm:w-28">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={p.spark.map((v, i) => ({ v, i }))}>
                  <Tooltip
                    content={({ active, payload }: any) =>
                      active && payload?.length ? (
                        <div className="surface-card px-3 py-1.5">
                          <p className="text-label text-muted-foreground">{payload[0].value} rating</p>
                        </div>
                      ) : null
                    }
                  />
                  <Line
                    type="monotone"
                    dataKey="v"
                    stroke={p.stroke}
                    strokeWidth={2.5}
                    dot={false}
                    activeDot={{ r: 3.5, strokeWidth: 2, stroke: "var(--card)" }}
                    animationDuration={900}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <dl className="mt-6 grid grid-cols-2 gap-4 border-t border-border pt-5">
            <div>
              <dt className="text-label uppercase text-subtle">Peak</dt>
              <dd className="text-caption font-semibold">{p.peak}</dd>
            </div>
            <div>
              <dt className="text-label uppercase text-subtle">Solved</dt>
              <dd className="text-caption font-semibold">{p.solved.toLocaleString()}</dd>
            </div>
          </dl>
        </article>
      ))}
    </div>
  );
}
