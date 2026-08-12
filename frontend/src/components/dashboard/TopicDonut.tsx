import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip, type TooltipProps } from "recharts";

import type { DashboardProblems } from "@/api/dashboard";
import { ChartSkeleton, EmptyState, ErrorState } from "@/components/ui-kit/motion";
import { Panel } from "@/components/ui-kit/Panel";

const difficultyColors: Record<string, string> = {
  Easy: "var(--pastel-green)",
  Medium: "var(--pastel-yellow)",
  Hard: "var(--pastel-pink)",
};

export function TopicDonut({
  problems,
  isLoading = false,
  error,
  onRetry,
}: {
  problems?: DashboardProblems | undefined;
  isLoading?: boolean;
  error?: string | undefined;
  onRetry?: (() => void) | undefined;
}) {
  const data = problems
    ? problems.solved_by_difficulty.map((item) => ({
        name: item.difficulty,
        value: item.solved_count,
        color: difficultyColors[item.difficulty] ?? "var(--pastel-blue)",
      }))
    : [];
  const total = data.reduce((sum, item) => sum + item.value, 0);

  return (
    <Panel
      title="Solved by difficulty"
      caption="Accepted problems from your synced Codeforces history"
    >
      {isLoading ? (
        <ChartSkeleton height={220} />
      ) : error ? (
        <ErrorState description={error} onRetry={onRetry} />
      ) : data.length === 0 ? (
        <EmptyState
          title="No solved problems yet"
          description="Sync your Codeforces profile after an accepted submission to see this breakdown."
        />
      ) : (
        <div className="flex flex-col items-center gap-6 sm:flex-row sm:gap-8">
          <div className="relative h-[220px] w-[220px] shrink-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data}
                  dataKey="value"
                  innerRadius={68}
                  outerRadius={100}
                  paddingAngle={3}
                  cornerRadius={8}
                  stroke="none"
                  animationDuration={900}
                >
                  {data.map((item) => (
                    <Cell key={item.name} fill={item.color} />
                  ))}
                </Pie>
                <Tooltip
                  content={({ active, payload }: TooltipProps<number, string>) =>
                    active && payload?.length ? (
                      <div className="surface-card px-3.5 py-2">
                        <p className="text-caption font-semibold">{payload[0]?.name}</p>
                        <p className="text-label text-muted-foreground">
                          {payload[0]?.value} solved ·{" "}
                          {total > 0 ? Math.round(((payload[0]?.value ?? 0) / total) * 100) : 0}%
                        </p>
                      </div>
                    ) : null
                  }
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-h2">{total}</span>
              <span className="text-label text-subtle">solved</span>
            </div>
          </div>

          <ul className="w-full space-y-2.5">
            {data.map((item) => (
              <li key={item.name} className="flex items-center gap-3">
                <span
                  className="h-2.5 w-2.5 shrink-0 rounded-full"
                  style={{ background: item.color }}
                />
                <span className="text-caption text-muted-foreground">{item.name}</span>
                <span className="text-caption ml-auto font-semibold">{item.value}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Panel>
  );
}
