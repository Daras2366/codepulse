import { createFileRoute, redirect } from "@tanstack/react-router";

import { hasAccessToken } from "@/api/client";

import { AppShell } from "@/components/layout/AppShell";
import { PlatformConnections } from "@/components/platforms/PlatformConnections";

const title = "Platforms — CodePulse";
const description =
  "Connected handles for LeetCode, Codeforces, CodeChef and AtCoder with rating, peak rating, problems solved and global rank.";

export const Route = createFileRoute("/platforms")({
  beforeLoad: () => {
    if (!hasAccessToken()) {
      throw redirect({ to: "/auth" });
    }
  },
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: Platforms,
});

function Platforms() {
  return (
    <AppShell title="Platforms" subtitle="Four handles, one synced profile.">
      <PlatformConnections />
    </AppShell>
  );
}
