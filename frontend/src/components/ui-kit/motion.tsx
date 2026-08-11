import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type ReactNode,
} from "react";
import { AlertTriangle, Inbox } from "lucide-react";

import { cn } from "@/lib/utils";

const useIsoLayoutEffect = typeof window === "undefined" ? useEffect : useLayoutEffect;

function prefersReducedMotion() {
  return (
    typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

export function useInView<T extends HTMLElement>(rootMargin = "-40px") {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          setInView(true);
          io.disconnect();
        }
      },
      { rootMargin },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [rootMargin]);

  return { ref, inView };
}

export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const { ref, inView } = useInView<HTMLDivElement>();
  return (
    <div
      ref={ref}
      className={cn("reveal", inView && "reveal-in", className)}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </div>
  );
}

export function AnimatedCounter({
  value,
  decimals = 0,
  prefix = "",
  suffix = "",
  duration = 1100,
  className,
}: {
  value: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
  className?: string;
}) {
  const [display, setDisplay] = useState(value);
  const { ref, inView } = useInView<HTMLSpanElement>("0px");
  const started = useRef(false);

  useIsoLayoutEffect(() => {
    if (started.current || prefersReducedMotion()) return;
    setDisplay(0);
  }, []);

  useEffect(() => {
    if (!inView || started.current || prefersReducedMotion()) return;
    started.current = true;
    let raf = 0;
    const t0 = performance.now();
    const tick = (now: number) => {
      const p = Math.min(1, (now - t0) / duration);
      setDisplay(value * easeOut(p));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [inView, value, duration]);

  const formatted = display.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });

  return (
    <span ref={ref} className={className}>
      {prefix}
      {formatted}
      {suffix}
    </span>
  );
}

export function AnimatedBar({
  value,
  color,
  className,
  height = 10,
}: {
  value: number;
  color: string;
  className?: string;
  height?: number;
}) {
  const { ref, inView } = useInView<HTMLDivElement>("0px");
  const pct = Math.max(0, Math.min(100, value));

  return (
    <div
      ref={ref}
      className={cn("w-full overflow-hidden rounded-full bg-muted", className)}
      style={{ height }}
      role="progressbar"
      aria-valuenow={Math.round(pct)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className="h-full rounded-full"
        style={{
          width: inView ? `${pct}%` : "0%",
          background: color,
          transition: "width 900ms cubic-bezier(0.22,1,0.36,1)",
        }}
      />
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} aria-hidden />;
}

export function ChartSkeleton({ height = 260 }: { height?: number }) {
  const bars = [52, 74, 41, 88, 63, 79, 48, 92, 68, 57];
  return (
    <div className="flex flex-col justify-end gap-3" style={{ height }} aria-busy>
      <div className="flex flex-1 items-end gap-3">
        {bars.map((h, i) => (
          <div key={i} className="flex-1" style={{ height: `${h}%` }}>
            <Skeleton className="h-full w-full rounded-2xl" />
          </div>
        ))}
      </div>

      <div className="flex gap-3">
        {Array.from({ length: 4 }).map((_, i) => (
          <Skeleton key={i} className="h-3 w-16" />
        ))}
      </div>
    </div>
  );
}

export function ListSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <ul className="space-y-4" aria-busy>
      {Array.from({ length: rows }).map((_, i) => (
        <li key={i} className="flex items-center gap-4">
          <Skeleton className="h-10 w-10 shrink-0" />
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-3.5 w-1/2" />
            <Skeleton className="h-3 w-1/3" />
          </div>
          <Skeleton className="h-3.5 w-12 shrink-0" />
        </li>
      ))}
    </ul>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon: Icon = Inbox,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: typeof Inbox;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border px-6 py-12 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted">
        <Icon className="h-5 w-5 text-subtle" strokeWidth={1.6} />
      </span>
      <p className="text-card-title mt-4">{title}</p>
      <p className="text-caption mt-1 max-w-sm text-muted-foreground">{description}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function ErrorState({
  title = "Couldn't load this data",
  description = "The platform API didn't respond. Retry in a moment — nothing was lost.",
  onRetry,
}: {
  title?: string;
  description?: string;
  onRetry?: (() => void) | undefined;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border px-6 py-12 text-center">
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-pink-soft">
        <AlertTriangle className="h-5 w-5" strokeWidth={1.6} />
      </span>
      <p className="text-card-title mt-4">{title}</p>
      <p className="text-caption mt-1 max-w-sm text-muted-foreground">{description}</p>
      {onRetry && (
        <ActionButton className="mt-5" onClick={onRetry}>
          Try again
        </ActionButton>
      )}
    </div>
  );
}

export function ActionButton({
  children,
  variant = "primary",
  className,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "ghost" | "quiet" }) {
  return (
    <button
      type="button"
      className={cn(
        "press inline-flex items-center justify-center gap-2 rounded-full px-5 py-2.5 text-caption font-semibold disabled:pointer-events-none disabled:opacity-60",
        variant === "primary" && "bg-primary text-primary-foreground",
        variant === "ghost" && "border border-border bg-card text-foreground hover:bg-accent",
        variant === "quiet" && "text-muted-foreground hover:text-foreground",
        className,
      )}
      {...rest}
    >
      {children}
    </button>
  );
}
