import type { AggregateDifficultyDistribution } from "@/api/analytics";
import { ChartSkeleton, EmptyState, ErrorState } from "@/components/ui-kit/motion";
import { Panel } from "@/components/ui-kit/Panel";

const difficultyColors: Record<string, string> = {
  Easy: "var(--pastel-green)",
  Medium: "var(--pastel-yellow)",
  Hard: "var(--pastel-pink)",
};

export function DifficultySplit({
  difficultyData,
  isLoading = false,
  error,
  onRetry,
}: {
  difficultyData?: AggregateDifficultyDistribution | undefined;
  isLoading?: boolean;
  error?: string | undefined;
  onRetry?: (() => void) | undefined;
}) {
  const difficultyItems = difficultyData?.difficulties ?? [];
  const totalSolved = difficultyData?.total_solved || 0;
  const platformTotals = difficultyData?.platform_totals ?? [];

  return (
    <Panel title="Difficulty split" caption="Solved problems by difficulty band">
      {isLoading ? (
        <div className="space-y-4 py-4">
          <div className="h-4 w-full rounded bg-muted" />
          <div className="h-4 w-full rounded bg-muted" />
          <div className="h-4 w-full rounded bg-muted" />
        </div>
      ) : error ? (
        <ErrorState description={error} onRetry={onRetry} />
      ) : difficultyItems.length === 0 ? (
        <EmptyState
          title="No difficulty breakdown yet"
          description="Sync your submissions to categorize solved problems by difficulty."
        />
      ) : (
        <>
          <ul className="space-y-5">
            {difficultyItems.map((d) => {
              const color = difficultyColors[d.difficulty] ?? "var(--pastel-blue)";
              return (
                <li key={d.difficulty}>
                  <div className="mb-2 flex items-center justify-between">
                    <span className="text-caption text-muted-foreground">{d.difficulty}</span>
                    <span className="text-caption font-semibold">
                      {d.solved_count.toLocaleString()} · {d.percentage}%
                    </span>
                  </div>
                  <div className="h-2.5 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full transition-all duration-500"
                      style={{ width: `${d.percentage}%`, background: color }}
                    />
                  </div>
                </li>
              );
            })}
          </ul>

          {platformTotals.length > 0 && (
            <div className="mt-8 grid gap-4 border-t border-border pt-6 sm:grid-cols-2">
              {platformTotals.map((p) => (
                <div
                  key={p.platform}
                  className="flex items-center justify-between rounded-2xl bg-muted px-4 py-3"
                >
                  <span className="text-caption text-muted-foreground capitalize">
                    {p.platform}
                  </span>
                  <span className="text-caption font-semibold">
                    {(p.easy + p.medium + p.hard).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </Panel>
  );
}
