import { createFileRoute } from "@tanstack/react-router";
import { Brain, Flame, Target, Trophy } from "lucide-react";

import { ActivityTimeline } from "@/components/dashboard/ActivityTimeline";
import { Heatmap } from "@/components/dashboard/Heatmap";
import { PlatformCards } from "@/components/dashboard/PlatformCards";
import { RatingChart } from "@/components/dashboard/RatingChart";
import { StatCard } from "@/components/dashboard/StatCard";
import { Leaderboard } from "@/components/dashboard/Tables";
import { TopicDonut } from "@/components/dashboard/TopicDonut";
import { WelcomeCard } from "@/components/dashboard/WelcomeCard";
import { AppShell } from "@/components/layout/AppShell";

const title = "CodePulse — Competitive Programming Tracker";
const description =
  "Track LeetCode, Codeforces, CodeChef and AtCoder progress in one calm dashboard, with AI-powered insights and personalized practice recommendations.";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: Dashboard,
});

function Dashboard() {
  return (
    <AppShell title="Dashboard" subtitle="A calm view of your practice across every platform.">
      <div className="space-y-6">
        <WelcomeCard />

        <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Problems solved" value="2,283" delta={38} note="Across four platforms" icon={Target} tint="bg-blue-soft" />
          <StatCard label="Contest rating" value="2,148" delta={34} note="LeetCode · peak 2,210" icon={Trophy} tint="bg-yellow-soft" />
          <StatCard label="Daily streak" value="47" suffix="days" delta={1} note="Longest run: 92 days" icon={Flame} tint="bg-pink-soft" />
          <StatCard label="Interview readiness" value="78" suffix="%" delta={6} note="Ready for mid-level loops" icon={Brain} tint="bg-violet-soft" />
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
          <RatingChart compact />
          <TopicDonut />
        </div>

        <Heatmap />

        <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
          <ActivityTimeline limit={5} />
          <Leaderboard />
        </div>

        <div>
          <h2 className="text-h3 mb-5">Platforms</h2>
          <PlatformCards columns={4} />
        </div>
      </div>
    </AppShell>
  );
}
