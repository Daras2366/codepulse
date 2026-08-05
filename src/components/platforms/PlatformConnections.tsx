import { useState } from "react";
import { CheckCircle2, Clock3, Link2Off, Lock, RefreshCw, Trophy } from "lucide-react";

import { Panel, Pill } from "@/components/ui-kit/Panel";
import { ActionButton, AnimatedCounter, Skeleton } from "@/components/ui-kit/motion";
import { comingSoonPlatforms, platformAccounts, platforms } from "@/lib/mock-data";
import { cn } from "@/lib/utils";

type Status = "connected" | "syncing" | "disconnected";

function PlatformCard({ platform }: { platform: (typeof platforms)[number] }) {
  const account = platformAccounts[platform.key];
  const [status, setStatus] = useState<Status>("connected");
  const [lastSync, setLastSync] = useState(account.lastSync);

  function sync() {
    setStatus("syncing");
    setTimeout(() => {
      setLastSync("just now");
      setStatus("connected");
    }, 1400);
  }

  const syncing = status === "syncing";
  const disconnected = status === "disconnected";

  return (
    <article className="surface-card lift group flex flex-col p-6">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span
            className={cn(
              "flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl text-caption font-bold transition-transform duration-300 group-hover:scale-105",
              platform.tint,
              disconnected && "opacity-50",
            )}
            aria-hidden
          >
            {platform.short}
          </span>
          <div className="min-w-0">
            <p className="text-card-title truncate">{platform.name}</p>
            <p className="text-label truncate text-subtle">@{account.username}</p>
          </div>
        </div>
        {disconnected ? (
          <Pill tone="neutral">Disconnected</Pill>
        ) : syncing ? (
          <Pill tone="blue">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" strokeWidth={1.8} />
            Syncing
          </Pill>
        ) : (
          <Pill tone="green">
            <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={1.8} />
            Connected
          </Pill>
        )}
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-x-4 gap-y-5 border-t border-border pt-5">
        <div>
          <dt className="text-label uppercase text-subtle">Contest rating</dt>
          <dd className="mt-0.5 text-h3">
            {syncing ? (
              <Skeleton className="mt-1 h-6 w-20" />
            ) : disconnected ? (
              <span className="text-muted-foreground">—</span>
            ) : (
              <AnimatedCounter value={platform.rating} />
            )}
          </dd>
        </div>
        <div>
          <dt className="text-label uppercase text-subtle">Peak rating</dt>
          <dd className="mt-0.5 text-h3">
            {syncing ? (
              <Skeleton className="mt-1 h-6 w-20" />
            ) : disconnected ? (
              <span className="text-muted-foreground">—</span>
            ) : (
              <AnimatedCounter value={platform.peak} />
            )}
          </dd>
        </div>
        <div>
          <dt className="text-label uppercase text-subtle">Problems solved</dt>
          <dd className="text-caption mt-0.5 font-semibold">
            {syncing ? (
              <Skeleton className="mt-1 h-4 w-16" />
            ) : disconnected ? (
              "—"
            ) : (
              platform.solved.toLocaleString()
            )}
          </dd>
        </div>
        <div>
          <dt className="text-label uppercase text-subtle">Last sync</dt>
          <dd className="text-caption mt-0.5 flex items-center gap-1.5 font-semibold text-muted-foreground">
            <Clock3 className="h-3.5 w-3.5 shrink-0 text-subtle" strokeWidth={1.6} />
            {disconnected ? "Never" : syncing ? "Syncing…" : lastSync}
          </dd>
        </div>
      </dl>

      <div className="mt-6 flex flex-wrap gap-2.5">
        {disconnected ? (
          <ActionButton className="px-4 py-2" onClick={() => setStatus("connected")}>
            Reconnect
          </ActionButton>
        ) : (
          <>
            <ActionButton variant="ghost" className="px-4 py-2" disabled={syncing} onClick={sync}>
              <RefreshCw
                className={cn("h-3.5 w-3.5", syncing && "animate-spin")}
                strokeWidth={1.8}
              />
              {syncing ? "Syncing" : "Sync now"}
            </ActionButton>
            <ActionButton
              variant="quiet"
              className="px-4 py-2"
              onClick={() => setStatus("disconnected")}
            >
              <Link2Off className="h-3.5 w-3.5" strokeWidth={1.8} />
              Disconnect
            </ActionButton>
          </>
        )}
      </div>
    </article>
  );
}

export function PlatformConnections() {
  return (
    <div className="space-y-6">
      <div className="grid gap-6 xl:grid-cols-2">
        {platforms.map((p) => (
          <PlatformCard key={p.key} platform={p} />
        ))}
      </div>

      <Panel
        title="Coming soon"
        caption="More integrations on the roadmap — join the waitlist to get them first"
        action={
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-muted">
            <Trophy className="h-4 w-4 text-subtle" strokeWidth={1.6} />
          </span>
        }
      >
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {comingSoonPlatforms.map((p) => (
            <li
              key={p.name}
              className="lift flex items-center gap-3 rounded-2xl border border-dashed border-border bg-muted/40 p-4"
            >
              <span
                className={cn(
                  "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-label font-bold opacity-70",
                  p.tint,
                )}
                aria-hidden
              >
                {p.short}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-caption truncate font-semibold">{p.name}</p>
                <p className="text-label truncate text-subtle">{p.note}</p>
              </div>
              <Pill tone="neutral" className="shrink-0">
                <Lock className="h-3 w-3" strokeWidth={1.8} />
                Soon
              </Pill>
            </li>
          ))}
        </ul>
      </Panel>
    </div>
  );
}
