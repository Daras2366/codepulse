import { Flame, Quote, Target } from "lucide-react";

function Ring({ value, target }: { value: number; target: number }) {
  const pct = Math.min(1, value / target);
  const r = 42;
  const c = 2 * Math.PI * r;
  return (
    <div className="relative h-[116px] w-[116px] shrink-0">
      <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
        <circle cx="50" cy="50" r={r} fill="none" stroke="var(--border)" strokeWidth="9" />
        <circle
          cx="50"
          cy="50"
          r={r}
          fill="none"
          stroke="var(--pastel-green)"
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={c * (1 - pct)}
          style={{ transition: "stroke-dashoffset 900ms cubic-bezier(0.22,1,0.36,1)" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-h3">
          {value}
          <span className="text-caption text-muted-foreground">/{target}</span>
        </span>
        <span className="text-label text-subtle">today</span>
      </div>
    </div>
  );
}

export function WelcomeCard() {
  return (
    <section className="surface-card overflow-hidden">
      <div className="grid gap-8 p-6 md:p-8 lg:grid-cols-[1.4fr_1fr]">
        <div className="flex flex-col justify-between gap-8">
          <div>
            <span className="text-label inline-flex items-center gap-2 rounded-full bg-yellow-soft px-3 py-1 uppercase">
              Tuesday · Week 27
            </span>
            <h2 className="text-h2 mt-5">Good evening, Demo User.</h2>
            <p className="text-body mt-2 max-w-lg text-muted-foreground">
              Your Codeforces curve turned upward this week. Two clean DP sets would put 1900 within
              reach before the next Div. 2.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-3 rounded-2xl bg-pink-soft px-4 py-3">
              <Flame className="h-[18px] w-[18px]" strokeWidth={1.6} />
              <div>
                <p className="text-label uppercase text-subtle">Current streak</p>
                <p className="text-card-title">47 days</p>
              </div>
            </div>
            <div className="flex items-center gap-3 rounded-2xl bg-blue-soft px-4 py-3">
              <Target className="h-[18px] w-[18px]" strokeWidth={1.6} />
              <div>
                <p className="text-label uppercase text-subtle">Longest streak</p>
                <p className="text-card-title">92 days</p>
              </div>
            </div>
          </div>

          <p className="text-caption flex items-start gap-2 text-muted-foreground">
            <Quote className="mt-0.5 h-4 w-4 shrink-0 text-subtle" strokeWidth={1.6} />
            "Consistency compounds faster than talent — one problem a day beats ten on Sunday."
          </p>
        </div>

        <div className="flex flex-col items-center justify-center gap-6 rounded-2xl bg-green-soft/70 p-6">
          <Ring value={3} target={5} />
          <div className="text-center">
            <p className="text-card-title">Daily goal</p>
            <p className="text-caption mt-1 text-muted-foreground">
              2 problems left to keep the streak alive
            </p>
          </div>
          <button className="press rounded-full bg-primary px-5 py-2.5 text-caption font-semibold text-primary-foreground">
            Resume practice
          </button>
        </div>
      </div>
    </section>
  );
}
