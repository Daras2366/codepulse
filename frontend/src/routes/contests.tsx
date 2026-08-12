import { createFileRoute } from "@tanstack/react-router";

import { getDashboardErrorMessage } from "@/api/client";
import { ContestsTable, Leaderboard } from "@/components/dashboard/Tables";
import { AppShell } from "@/components/layout/AppShell";
import { EmptyState, Skeleton } from "@/components/ui-kit/motion";
import { useAnalytics } from "@/hooks/useAnalytics";

const title = "Contests — CodePulse";
const description = "Every rated contest you entered, with rank, rating delta and status.";

export const Route = createFileRoute("/contests")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: Contests,
});

function Contests() {
  const { authenticated, profile, isLoadingProfiles, contests } = useAnalytics();

  if (!authenticated) {
    return (
      <AppShell title="Contests" subtitle="Rated rounds, ranks and rating movement.">
        <EmptyState
          title="Sign in to view contests"
          description="Sign in with your CodePulse account to view your rated contest history."
        />
      </AppShell>
    );
  }

  if (isLoadingProfiles) {
    return (
      <AppShell title="Contests" subtitle="Rated rounds, ranks and rating movement.">
        <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]" aria-busy>
          <Skeleton className="h-[360px] w-full rounded-2xl" />
          <Skeleton className="h-[360px] w-full rounded-2xl" />
        </div>
      </AppShell>
    );
  }

  if (!profile) {
    return (
      <AppShell title="Contests" subtitle="Rated rounds, ranks and rating movement.">
        <EmptyState
          title="No Codeforces profile connected"
          description="Connect and sync a Codeforces profile to view contest performance."
        />
      </AppShell>
    );
  }

  return (
    <AppShell title="Contests" subtitle="Rated rounds, ranks and rating movement.">
      <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <ContestsTable
          contests={contests.data}
          isLoading={contests.isLoading}
          error={contests.error ? getDashboardErrorMessage(contests.error) : undefined}
          onRetry={() => contests.refetch()}
        />
        <Leaderboard />
      </div>
    </AppShell>
  );
}
