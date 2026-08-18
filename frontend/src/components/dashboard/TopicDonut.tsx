import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip, type TooltipProps } from "recharts";

import type { AggregateTopicBreakdown } from "@/api/analytics";
import { ChartSkeleton, EmptyState, ErrorState } from "@/components/ui-kit/motion";
import { Panel } from "@/components/ui-kit/Panel";

const TOPIC_COLORS: Record<string, string> = {
  Arrays: "var(--pastel-blue)",
  Graphs: "var(--pastel-green)",
  Trees: "var(--pastel-yellow)",
  DP: "var(--pastel-pink)",
  Greedy: "var(--pastel-purple)",
  Strings: "var(--pastel-orange)",
  Math: "var(--pastel-red)",
  "Binary Search": "var(--pastel-cyan)",
  "Bit Manipulation": "var(--pastel-magenta)",
  Recursion: "var(--pastel-lime)",
};

export function TopicDonut({
  topicData,
  isLoading = false,
  error,
  onRetry,
}: {
  topicData?: AggregateTopicBreakdown | undefined;
  isLoading?: boolean;
  error?: string | undefined;
  onRetry?: (() => void) | undefined;
}) {
  const data =
    topicData?.topics.map((item) => ({
      name: item.topic,
      value: item.solved_count,
      color: TOPIC_COLORS[item.topic] || "var(--pastel-blue)",
    })) || [];
  const totalSolved = topicData?.total_solved || 0;
  const taggedSolved = topicData?.tagged_solved || 0;
  const total = taggedSolved; // Use tagged solved for the donut total

  return (
    <Panel title="Topic breakdown" caption="Where your solved problems come from">
      {isLoading ? (
        <ChartSkeleton height={220} />
      ) : error ? (
        <ErrorState description={error} onRetry={onRetry} />
      ) : data.length === 0 ? (
        <EmptyState
          title="No topics tagged yet"
          description={
            totalSolved > 0
              ? `You have ${totalSolved} solved problems, but topic data is not available for them yet. Re-sync your profile to populate topic information.`
              : "Solve problems with topic tags to see your topic distribution."
          }
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
              <span className="text-h2">{taggedSolved}</span>
              <span className="text-label text-subtle">
                {totalSolved > taggedSolved ? `of ${totalSolved} tagged` : "tagged"}
              </span>
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
