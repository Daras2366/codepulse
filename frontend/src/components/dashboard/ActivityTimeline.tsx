import { CheckCircle2, Flag, Sparkles, Trophy } from "lucide-react";

import { Panel, Pill } from "@/components/ui-kit/Panel";
import { activity, type ActivityKind } from "@/lib/mock-data";

const config: Record<
  ActivityKind,
  { icon: typeof Trophy; tint: string; tone: "green" | "blue" | "yellow" | "violet"; label: string }
> = {
  solved: { icon: CheckCircle2, tint: "bg-green-soft", tone: "green", label: "Solved" },
  contest: { icon: Trophy, tint: "bg-blue-soft", tone: "blue", label: "Contest" },
  milestone: { icon: Sparkles, tint: "bg-yellow-soft", tone: "yellow", label: "Milestone" },
  topic: { icon: Flag, tint: "bg-violet-soft", tone: "violet", label: "Topic" },
};

export function ActivityTimeline({ limit }: { limit?: number }) {
  const items = limit ? activity.slice(0, limit) : activity;

  return (
    <Panel title="Recent activity" caption="Everything you shipped this week">
      <ol className="relative space-y-5 before:absolute before:top-2 before:bottom-2 before:left-[19px] before:w-px before:bg-border">
        {items.map((item, i) => {
          const c = config[item.kind];
          return (
            <li key={i} className="relative flex gap-4">
              <span
                className={`relative z-10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${c.tint}`}
              >
                <c.icon className="h-[17px] w-[17px]" strokeWidth={1.6} />
              </span>
              <div className="min-w-0 flex-1 pt-1">
                <div className="flex flex-wrap items-center gap-2.5">
                  <p className="text-caption font-semibold">{item.title}</p>
                  <Pill tone={c.tone}>{c.label}</Pill>
                </div>
                <p className="text-caption mt-1 text-muted-foreground">
                  {item.meta} · {item.time}
                </p>
              </div>
            </li>
          );
        })}
      </ol>
    </Panel>
  );
}
