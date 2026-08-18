import type { LucideIcon } from "lucide-react";
import { ArrowDownRight, ArrowUpRight } from "lucide-react";

import { AnimatedCounter } from "@/components/ui-kit/motion";
import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  suffix,
  delta,
  note,
  icon: Icon,
  tint,
}: {
  label: string;
  value: string;
  suffix?: string;
  delta?: number;
  note: string;
  icon: LucideIcon;
  tint: string;
}) {
  const up = (delta ?? 0) >= 0;
  const numeric = Number(value.replace(/,/g, ""));
  return (
    <article className="surface-card lift group p-6">
      <div className="flex items-start justify-between">
        <span
          className={cn(
            "flex h-11 w-11 items-center justify-center rounded-2xl transition-transform duration-300 group-hover:scale-105",
            tint,
          )}
        >
          <Icon className="h-[18px] w-[18px] text-foreground" strokeWidth={1.6} />
        </span>
        {delta !== undefined && (
          <span
            className={cn(
              "inline-flex items-center gap-1 text-caption",
              up ? "text-[var(--success)]" : "text-[var(--danger)]",
            )}
          >
            {up ? (
              <ArrowUpRight
                className="h-3.5 w-3.5 transition-transform duration-300 group-hover:-translate-y-0.5"
                strokeWidth={1.8}
              />
            ) : (
              <ArrowDownRight
                className="h-3.5 w-3.5 transition-transform duration-300 group-hover:translate-y-0.5"
                strokeWidth={1.8}
              />
            )}
            {up ? "+" : ""}
            {delta}
          </span>
        )}
      </div>
      <p className="text-label mt-6 uppercase text-subtle">{label}</p>
      <p className="mt-1.5 text-[28px] leading-tight font-bold tracking-tight">
        {Number.isFinite(numeric) ? <AnimatedCounter value={numeric} /> : value}
        {suffix && <span className="text-body ml-1 font-medium text-muted-foreground">{suffix}</span>}
      </p>
      <p className="mt-2 text-caption text-muted-foreground">{note}</p>
    </article>
  );
}
