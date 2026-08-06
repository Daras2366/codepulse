import { useMemo, useState } from "react";

import { Panel } from "@/components/ui-kit/Panel";
import { buildHeatmap } from "@/lib/mock-data";

const levels = [
  "bg-muted",
  "bg-[color-mix(in_oklab,var(--pastel-green)_35%,var(--card))]",
  "bg-[color-mix(in_oklab,var(--pastel-green)_60%,var(--card))]",
  "bg-[color-mix(in_oklab,var(--pastel-green)_85%,var(--card))]",
  "bg-[var(--success)]",
];

const months = ["Aug", "Sep", "Oct", "Nov", "Dec", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"];

export function Heatmap() {
  const weeks = useMemo(() => buildHeatmap(), []);
  const [hover, setHover] = useState<{ label: string; count: number } | null>(null);
  const total = weeks.flat().reduce((s, d) => s + d.count, 0);

  return (
    <Panel
      title="Submission activity"
      caption={`${total.toLocaleString()} submissions in the last year`}
      action={
        <div className="flex items-center gap-2">
          <span className="text-label text-subtle">Less</span>
          {levels.map((l, i) => (
            <span key={i} className={`h-3 w-3 rounded-[4px] ${l}`} />
          ))}
          <span className="text-label text-subtle">More</span>
        </div>
      }
    >
      <div className="relative">
        <div className="no-scrollbar overflow-x-auto pb-2">
          <div className="min-w-[720px]">
            <div className="mb-2 flex text-label text-subtle">
              {months.map((m) => (
                <span key={m} className="flex-1">
                  {m}
                </span>
              ))}
            </div>
            <div className="flex gap-[3px]">
              {weeks.map((week, wi) => (
                <div key={wi} className="flex flex-col gap-[3px]">
                  {week.map((day, di) => (
                    <span
                      key={di}
                      onMouseEnter={() => setHover(day)}
                      onMouseLeave={() => setHover(null)}
                      className={`h-3 w-3 rounded-[4px] transition-transform duration-150 hover:scale-125 ${levels[day.level]}`}
                    />
                  ))}
                </div>
              ))}
            </div>
          </div>
        </div>
        <div className="mt-4 h-6">
          {hover && (
            <span className="text-caption rounded-full bg-muted px-3 py-1 text-muted-foreground">
              {hover.count} submissions · {hover.label}
            </span>
          )}
        </div>
      </div>
    </Panel>
  );
}
