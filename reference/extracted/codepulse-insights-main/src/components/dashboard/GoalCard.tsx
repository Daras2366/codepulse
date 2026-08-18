import { AnimatedBar, AnimatedCounter } from "@/components/ui-kit/motion";
import { cn } from "@/lib/utils";

export function ProgressBar({ value, color }: { value: number; color: string }) {
  return <AnimatedBar value={value} color={color} />;
}

export function GoalCard({
  title,
  current,
  target,
  note,
  tint,
  bar,
}: {
  title: string;
  current: number;
  target: number;
  note: string;
  tint: string;
  bar: string;
}) {
  const pct = Math.round((current / target) * 100);
  return (
    <article className={cn("lift rounded-[20px] border border-border p-6", tint)}>
      <div className="flex items-start justify-between gap-4">
        <h3 className="text-card-title">{title}</h3>
        <span className="text-caption font-semibold">
          <AnimatedCounter value={pct} suffix="%" />
        </span>
      </div>
      <p className="text-caption mt-1 text-muted-foreground">{note}</p>
      <div className="mt-5">
        <AnimatedBar value={pct} color={bar} />
      </div>
      <p className="text-label mt-3 text-subtle">
        {current.toLocaleString()} of {target.toLocaleString()}
      </p>
    </article>
  );
}
