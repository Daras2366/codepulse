/**
 * TopicDonut — canonical DSA topic distribution for CodePulse Analytics.
 *
 * The backend provides normalized DSA topics such as:
 * Arrays, Graphs, Dynamic Programming, Trees, Greedy, etc.
 *
 * The backend is the source of truth for topic classification.
 */

import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip, type TooltipProps } from "recharts";

import type { AggregateTopicBreakdown } from "@/api/analytics";
import { ChartSkeleton, EmptyState, ErrorState } from "@/components/ui-kit/motion";
import { Panel } from "@/components/ui-kit/Panel";

// ---------------------------------------------------------------------------
// Color palette — fixed hex values, no CSS variables
// ---------------------------------------------------------------------------
//
// Each canonical DSA topic maps to a stable pastel hex color so the same
// topic always renders in the same color regardless of sort order.

const TOPIC_COLORS: Record<string, string> = {
  Arrays: "#AFC9F5",
  Searching: "#B8E6B8",
  Sorting: "#F7D774",
  Recursion: "#F3A6C7",
  Hashing: "#C7B3F5",
  "Linked List": "#F6B86A",
  Stack: "#9ED8E8",
  Queue: "#B7DDAA",
  Trees: "#9ED8E8",
  Graphs: "#B7DDAA",
  "Dynamic Programming": "#D9B8F3",
  "Bit Manipulation": "#F2C49B",
  Greedy: "#A8D5E5",
  Strings: "#E7B8D8",
  Math: "#F5C6A5",
  "Binary Search": "#B9C9F5",
  "Two Pointers": "#C4E7D4",
  "Sliding Window": "#FAD4A6",
  "Heap / Priority Queue": "#D4C5F5",
  Backtracking: "#F9C8D9",
  Intervals: "#C8E6C9",
  "Prefix Sum": "#B3E0F5",
  "Union Find / DSU": "#E8D5B7",
  Trie: "#D5F0E8",
  "Segment Tree / Fenwick Tree": "#F5D5C8",
  "Monotonic Stack": "#D8C8F5",
  "Advanced Data Structures": "#C8D8F5",
  // "Other" bucket — neutral pastel
  Other: "#D8D4C8",
};

// Fallback palette for any topic not explicitly listed above.
// These are safe pastels that never resolve to black.
const FALLBACK_COLORS = [
  "#AFC9F5",
  "#B8E6B8",
  "#F7D774",
  "#F3A6C7",
  "#C7B3F5",
  "#F6B86A",
  "#9ED8E8",
  "#B7DDAA",
  "#D9B8F3",
  "#F2C49B",
  "#A8D5E5",
  "#E7B8D8",
];

function colorForTopic(topic: string, index: number): string {
  return TOPIC_COLORS[topic] ?? FALLBACK_COLORS[index % FALLBACK_COLORS.length];
}

// ---------------------------------------------------------------------------
// Donut data preparation — collapse overflow into "Other"
// ---------------------------------------------------------------------------

const MAX_VISIBLE_TOPICS = 8;

interface DonutSlice {
  name: string;
  value: number;
  percentage: number;
  color: string;
}

/**
 * Build the list of donut slices.
 *
 * - Shows up to MAX_VISIBLE_TOPICS individual slices.
 * - If the backend already includes an "Other" entry, it is used as-is.
 * - Remaining topics beyond MAX_VISIBLE_TOPICS are collapsed into a single
 *   "Other" slice so the donut always sums to 100 % of total_topic_assignments.
 */
function buildDonutSlices(
  topics: AggregateTopicBreakdown["topics"],
  totalAssignments: number,
): DonutSlice[] {
  if (!topics.length) return [];

  // Separate any backend-provided "Other" from the sorted topic list.
  const otherFromBackend = topics.find((t) => t.topic === "Other");
  const namedTopics = topics.filter((t) => t.topic !== "Other");

  const primaryTopics = namedTopics.slice(0, MAX_VISIBLE_TOPICS);
  const overflowTopics = namedTopics.slice(MAX_VISIBLE_TOPICS);

  const slices: DonutSlice[] = primaryTopics.map((t, index) => ({
    name: t.topic,
    value: t.solved_count,
    percentage: t.percentage,
    color: colorForTopic(t.topic, index),
  }));

  // Build the "Other" slice from overflow + any backend-provided "Other".
  const overflowCount = overflowTopics.reduce((sum, t) => sum + t.solved_count, 0);
  const backendOtherCount = otherFromBackend?.solved_count ?? 0;
  const combinedOtherCount = overflowCount + backendOtherCount;

  if (combinedOtherCount > 0) {
    const otherPct =
      totalAssignments > 0
        ? Math.round((combinedOtherCount / totalAssignments) * 1000) / 10
        : 0;

    slices.push({
      name: "Other",
      value: combinedOtherCount,
      percentage: otherPct,
      color: TOPIC_COLORS["Other"],
    });
  }

  return slices;
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

function TopicTooltip({ active, payload }: TooltipProps<number, string>) {
  if (!active || !payload?.length) {
    return null;
  }

  const item = payload[0]?.payload as DonutSlice | undefined;

  if (!item) {
    return null;
  }

  return (
    <div className="surface-card min-w-[160px] rounded-xl px-3.5 py-2.5 shadow-lg">
      <p className="text-caption font-semibold">{item.name}</p>

      <p className="text-label mt-1 text-muted-foreground">
        {item.value.toLocaleString()} problems
      </p>

      <p className="text-label text-muted-foreground">{item.percentage}%</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Coverage note helpers
// ---------------------------------------------------------------------------

/**
 * Capitalise the first letter of a platform string.
 * "codeforces" → "Codeforces", "leetcode" → "LeetCode"
 */
function formatPlatformName(platform: string): string {
  const known: Record<string, string> = {
    codeforces: "Codeforces",
    leetcode: "LeetCode",
    atcoder: "AtCoder",
  };
  return known[platform.toLowerCase()] ?? platform.charAt(0).toUpperCase() + platform.slice(1);
}

function CoverageNote({
  topicData,
  hasTopicData,
}: {
  topicData: AggregateTopicBreakdown;
  hasTopicData: boolean;
}) {
  if (!hasTopicData) return null;

  const { platform_coverage, tagged_solved, total_solved } = topicData;

  // --- Platform-aware note (preferred) ---
  if (platform_coverage && platform_coverage.length > 0) {
    const lines: string[] = [];

    for (const pc of platform_coverage) {
      const name = formatPlatformName(pc.platform);
      if (pc.tagged_solved === 0 && pc.total_solved > 0) {
        // Platform has solved problems but zero topic coverage.
        lines.push(
          `${name}: topic data unavailable for ${pc.total_solved.toLocaleString()} solved problems.`,
        );
      } else if (pc.total_solved > 0) {
        lines.push(
          `Topic data available for ${pc.tagged_solved.toLocaleString()} of ${pc.total_solved.toLocaleString()} ${name} solved problems.`,
        );
      }
    }

    if (lines.length === 0) return null;

    return (
      <p className="text-label mt-4 text-subtle">
        {lines.join(" ")}
      </p>
    );
  }

  // --- Fallback: aggregate note when platform_coverage isn't present ---
  const hasPartialCoverage =
    tagged_solved > 0 && total_solved > 0 && tagged_solved < total_solved;

  if (!hasPartialCoverage) return null;

  return (
    <p className="text-label mt-4 text-subtle">
      Topic data available for {tagged_solved.toLocaleString()} of{" "}
      {total_solved.toLocaleString()} solved problems.
    </p>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function TopicDonut({
  topicData,
  isLoading = false,
  error,
  onRetry,
}: {
  topicData?: AggregateTopicBreakdown;
  isLoading?: boolean;
  error?: string;
  onRetry?: () => void;
}) {
  const totalSolved = topicData?.total_solved ?? 0;
  const taggedSolved = topicData?.tagged_solved ?? 0;
  const totalAssignments = topicData?.total_topic_assignments ?? 0;

  // -------------------------------------------------------------------------
  // Build donut slices
  // -------------------------------------------------------------------------

  const slices = buildDonutSlices(topicData?.topics ?? [], totalAssignments);

  const hasTopicData = slices.length > 0;

  const showCenterFraction =
    taggedSolved > 0 && totalSolved > 0 && taggedSolved < totalSolved;

  return (
    <Panel title="Topic breakdown" caption="What you're solving across DSA topics">
      {isLoading ? (
        <ChartSkeleton height={260} />
      ) : error ? (
        <ErrorState description={error} onRetry={onRetry} />
      ) : !hasTopicData ? (
        <EmptyState
          title="No topic data yet"
          description={
            totalSolved > 0
              ? `You have ${totalSolved.toLocaleString()} solved problems, but no canonical DSA topic data is available yet.`
              : "Solve problems with topic tags to see your DSA topic distribution."
          }
        />
      ) : (
        <div className="flex flex-col gap-6 sm:flex-row sm:items-center sm:gap-8">
          {/* =============================================================== */}
          {/* Donut                                                          */}
          {/* =============================================================== */}

          <div className="relative mx-auto h-[240px] w-[240px] shrink-0 sm:mx-0">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={slices}
                  dataKey="value"
                  nameKey="name"
                  innerRadius={72}
                  outerRadius={104}
                  paddingAngle={2}
                  cornerRadius={5}
                  stroke="none"
                  animationDuration={700}
                  animationBegin={0}
                >
                  {slices.map((item) => (
                    <Cell key={item.name} fill={item.color} />
                  ))}
                </Pie>

                <Tooltip content={<TopicTooltip />} />
              </PieChart>
            </ResponsiveContainer>

            {/* ============================================================= */}
            {/* Center label                                                  */}
            {/* ============================================================= */}

            <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
              <span className="text-h2 tabular-nums">{taggedSolved.toLocaleString()}</span>

              <span className="text-label mt-0.5 text-subtle">tagged problems</span>

              {showCenterFraction && (
                <span
                  className="text-label mt-1 max-w-[115px] text-center leading-tight text-muted-foreground"
                  title={`${taggedSolved.toLocaleString()} of ${totalSolved.toLocaleString()} solved problems have usable topic data`}
                >
                  {taggedSolved.toLocaleString()} / {totalSolved.toLocaleString()} solved
                </span>
              )}
            </div>
          </div>

          {/* =============================================================== */}
          {/* Legend                                                         */}
          {/* =============================================================== */}

          <div className="min-w-0 flex-1">
            <ul className="space-y-2.5">
              {slices.map((item) => (
                <li key={item.name} className="flex min-w-0 items-center gap-2.5">
                  {/* Color dot — same hex as the corresponding donut slice */}

                  <span
                    className="h-2.5 w-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: item.color }}
                    aria-hidden
                  />

                  {/* Topic name */}

                  <span className="text-caption min-w-0 flex-1 truncate" title={item.name}>
                    {item.name}
                  </span>

                  {/* Count — right-aligned, no percentage */}

                  <span className="text-caption shrink-0 tabular-nums font-semibold">
                    {item.value.toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* ================================================================= */}
      {/* Coverage note                                                     */}
      {/* ================================================================= */}

      {topicData && (
        <CoverageNote topicData={topicData} hasTopicData={hasTopicData} />
      )}
    </Panel>
  );
}
