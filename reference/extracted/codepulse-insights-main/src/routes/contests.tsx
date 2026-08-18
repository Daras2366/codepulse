import { createFileRoute } from "@tanstack/react-router";

import { ContestsTable, Leaderboard } from "@/components/dashboard/Tables";
import { AppShell } from "@/components/layout/AppShell";

const title = "Contests — CodePulse";
const description =
  "Every rated contest you entered, with rank, rating delta and status, plus how you stack up against your circle this week.";

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
  return (
    <AppShell title="Contests" subtitle="Rated rounds, ranks and rating movement.">
      <div className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <ContestsTable />
        <Leaderboard />
      </div>
    </AppShell>
  );
}
