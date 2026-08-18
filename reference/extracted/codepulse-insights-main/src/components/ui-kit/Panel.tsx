import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

export function Panel({
  title,
  caption,
  action,
  className,
  bodyClassName,
  children,
}: {
  title?: string;
  caption?: string;
  action?: ReactNode;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <section className={cn("surface-card p-6", className)}>
      {(title || action) && (
        <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-card-title">{title}</h2>}
            {caption && <p className="mt-1 text-caption text-muted-foreground">{caption}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}

export function Pill({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "pink" | "yellow" | "blue" | "violet" | "green" | "danger";
  className?: string;
}) {
  const tones: Record<string, string> = {
    neutral: "bg-muted text-muted-foreground",
    pink: "bg-pink-soft text-foreground",
    yellow: "bg-yellow-soft text-foreground",
    blue: "bg-blue-soft text-foreground",
    violet: "bg-violet-soft text-foreground",
    green: "bg-green-soft text-foreground",
    danger: "bg-[color-mix(in_oklab,var(--danger)_18%,transparent)] text-foreground",
  };
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-label font-medium whitespace-nowrap",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ChipToggle({
  options,
  value,
  onChange,
  className,
}: {
  options: { key: string; label: string }[];
  value: string[];
  onChange: (key: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-2", className)}>
      {options.map((o) => {
        const active = value.includes(o.key);
        return (
          <button
            key={o.key}
            type="button"
            onClick={() => onChange(o.key)}
            className={cn(
              "rounded-full border px-3.5 py-1.5 text-caption transition-all duration-200",
              active
                ? "border-transparent bg-primary text-primary-foreground"
                : "border-border bg-card text-muted-foreground hover:border-subtle hover:text-foreground",
            )}
          >
            {o.label}
          </button>
        );
      })}
    </div>
  );
}
