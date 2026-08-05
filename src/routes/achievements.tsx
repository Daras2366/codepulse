import { createFileRoute } from "@tanstack/react-router";
import { Lock, Medal } from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { Pill } from "@/components/ui-kit/Panel";
import { achievements } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

const title = "Achievements — CodePulse";
const description =
  "Badges earned across streaks, contests and topic mastery, plus the milestones still waiting to be unlocked.";

export const Route = createFileRoute("/achievements")({
  head: () => ({
    meta: [
      { title },
      { name: "description", content: description },
      { property: "og:title", content: title },
      { property: "og:description", content: description },
    ],
  }),
  component: Achievements,
});

function Achievements() {
  return (
    <AppShell title="Achievements" subtitle="Quiet proof of the hours you put in.">
      <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-3">
        {achievements.map((a) => (
          <article
            key={a.title}
            className={cn(
              "lift rounded-[20px] border border-border p-6",
              a.unlocked ? a.tint : "bg-card opacity-70",
            )}
          >
            <span
              className={cn(
                "flex h-12 w-12 items-center justify-center rounded-2xl",
                a.unlocked ? "bg-card" : "bg-muted",
              )}
            >
              {a.unlocked ? (
                <Medal className="h-5 w-5" strokeWidth={1.6} />
              ) : (
                <Lock className="h-5 w-5 text-subtle" strokeWidth={1.6} />
              )}
            </span>
            <h3 className="text-card-title mt-5">{a.title}</h3>
            <p className="text-caption mt-1.5 text-muted-foreground">{a.desc}</p>
            <div className="mt-5">
              <Pill tone={a.unlocked ? "green" : "neutral"}>
                {a.unlocked ? "Unlocked" : "Locked"}
              </Pill>
            </div>
          </article>
        ))}
      </div>
    </AppShell>
  );
}
