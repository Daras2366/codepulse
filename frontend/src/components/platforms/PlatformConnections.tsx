import { useState } from "react";
import { CheckCircle2, Clock3, Lock, Plus, RefreshCw, Trophy, X } from "lucide-react";

import { getDashboardErrorMessage } from "@/api/client";
import type { SyncResult } from "@/api/dashboard";
import type { PlatformProfile, PlatformProfileCreate } from "@/api/platform-profiles";
import { createPlatformProfile, deletePlatformProfile } from "@/api/platform-profiles";
import { Panel, Pill } from "@/components/ui-kit/Panel";
import {
  ActionButton,
  AnimatedCounter,
  EmptyState,
  ErrorState,
  Skeleton,
} from "@/components/ui-kit/motion";
import { usePlatforms } from "@/hooks/usePlatforms";
import { cn } from "@/lib/utils";

const availablePlatforms = [
  { name: "LeetCode", short: "LC", tint: "bg-yellow-soft", value: "leetcode" as const },
  { name: "Codeforces", short: "CF", tint: "bg-blue-soft", value: "codeforces" as const },
];

const comingSoonPlatforms = [
  { name: "CodeChef", short: "CC", tint: "bg-pink-soft", note: "API sync integration planned" },
  { name: "AtCoder", short: "AC", tint: "bg-violet-soft", note: "API sync integration planned" },
];

function formatLastSync(dateString: string | null) {
  if (!dateString) return "Never";
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));

  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return new Intl.DateTimeFormat("en", { month: "short", day: "numeric" }).format(date);
}

function ProfileCard({
  profile,
  onSync,
  onDelete,
  isSyncing,
  syncError,
  syncResult,
  showSyncResult,
}: {
  profile: PlatformProfile;
  onSync: (profile: PlatformProfile) => void;
  onDelete: () => void;
  isSyncing: boolean;
  syncError: unknown;
  syncResult?: SyncResult;
  showSyncResult: boolean;
}) {
  const isCodeforces = profile.platform === "codeforces";
  const isLeetCode = profile.platform === "leetcode";
  const canSync = isCodeforces || isLeetCode;

  const platformName = isCodeforces ? "Codeforces" : isLeetCode ? "LeetCode" : profile.platform;
  const platformShort = isCodeforces
    ? "CF"
    : isLeetCode
      ? "LC"
      : profile.platform.slice(0, 2).toUpperCase();
  const tint = isCodeforces ? "bg-blue-soft" : isLeetCode ? "bg-yellow-soft" : "bg-muted";

  return (
    <article className="surface-card lift group flex flex-col p-6">
      <div className="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <span
            className={cn(
              "flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl text-caption font-bold transition-transform duration-300 group-hover:scale-105",
              tint,
            )}
            aria-hidden
          >
            {platformShort}
          </span>
          <div className="min-w-0">
            <p className="text-card-title truncate">{platformName}</p>
            <p className="text-label truncate text-subtle">@{profile.username}</p>
          </div>
        </div>
        {isSyncing ? (
          <Pill tone="blue">
            <RefreshCw className="h-3.5 w-3.5 animate-spin" strokeWidth={1.8} />
            Syncing
          </Pill>
        ) : profile.is_connected ? (
          <Pill tone="green">
            <CheckCircle2 className="h-3.5 w-3.5" strokeWidth={1.8} />
            Connected
          </Pill>
        ) : (
          <Pill tone="neutral">Disconnected</Pill>
        )}
      </div>

      <dl className="mt-6 grid grid-cols-2 gap-x-4 gap-y-5 border-t border-border pt-5">
        <div>
          <dt className="text-label uppercase text-subtle">Contest rating</dt>
          <dd className="mt-0.5 text-h3">
            {profile.current_rating === null ? (
              <span className="text-muted-foreground">Unrated</span>
            ) : (
              <AnimatedCounter value={profile.current_rating} />
            )}
          </dd>
        </div>
        <div>
          <dt className="text-label uppercase text-subtle">Peak rating</dt>
          <dd className="mt-0.5 text-h3">
            {profile.max_rating === null ? (
              <span className="text-muted-foreground">—</span>
            ) : (
              <AnimatedCounter value={profile.max_rating} />
            )}
          </dd>
        </div>
        <div>
          <dt className="text-label uppercase text-subtle">Problems solved</dt>
          <dd className="text-caption mt-0.5 font-semibold">
            {profile.problems_solved.toLocaleString()}
          </dd>
        </div>
        <div>
          <dt className="text-label uppercase text-subtle">Contests attended</dt>
          <dd className="text-caption mt-0.5 font-semibold">
            {profile.contests_attended.toLocaleString()}
          </dd>
        </div>
        {profile.rank && (
          <div className="col-span-2">
            <dt className="text-label uppercase text-subtle">Global rank</dt>
            <dd className="text-caption mt-0.5 font-semibold">{profile.rank}</dd>
          </div>
        )}
        <div className="col-span-2">
          <dt className="text-label uppercase text-subtle">Last sync</dt>
          <dd className="text-caption mt-0.5 flex items-center gap-1.5 font-semibold text-muted-foreground">
            <Clock3 className="h-3.5 w-3.5 shrink-0 text-subtle" strokeWidth={1.6} />
            {isSyncing ? "Syncing…" : formatLastSync(profile.last_synced_at)}
          </dd>
        </div>
      </dl>

      {/* Sync success banner */}
      {showSyncResult && syncResult && !isSyncing && !syncError && (
        <div className="mt-4 rounded-xl bg-green-soft p-3">
          <div className="flex items-center gap-2 text-caption font-semibold">
            <CheckCircle2 className="h-4 w-4 shrink-0 text-[var(--success)]" strokeWidth={1.8} />
            <span>Sync complete!</span>
          </div>
          <p className="text-label mt-1.5 text-muted-foreground">
            {syncResult.submissions_created} new submission
            {syncResult.submissions_created === 1 ? "" : "s"} ·{" "}
            {syncResult.problems_solved.toLocaleString()} problems solved ·{" "}
            {syncResult.contests_attended} contest
            {syncResult.contests_attended === 1 ? "" : "s"} attended
          </p>
        </div>
      )}

      {syncError ? (
        <div className="mt-4 rounded-xl bg-destructive/10 p-3 text-caption text-destructive">
          {getDashboardErrorMessage(syncError)}
        </div>
      ) : null}

      <div className="mt-6 flex flex-wrap gap-2.5">
        {canSync && (
          <ActionButton
            variant="ghost"
            className="px-4 py-2"
            disabled={isSyncing}
            onClick={() => onSync(profile)}
          >
            <RefreshCw
              className={cn("h-3.5 w-3.5", isSyncing && "animate-spin")}
              strokeWidth={1.8}
            />
            {isSyncing ? "Syncing" : "Sync now"}
          </ActionButton>
        )}
        <ActionButton
          variant="ghost"
          className="px-4 py-2 text-destructive hover:text-destructive"
          disabled={isSyncing}
          onClick={onDelete}
        >
          <X className="h-3.5 w-3.5" strokeWidth={1.8} />
          Disconnect
        </ActionButton>
      </div>
    </article>
  );
}

export function PlatformConnections() {
  const {
    authenticated,
    profiles,
    isLoading,
    error,
    refetch,
    syncProfile,
    isSyncing,
    syncError,
    syncResult,
  } = usePlatforms();
  const [syncingProfileId, setSyncingProfileId] = useState<number | null>(null);
  const [lastSyncedProfileId, setLastSyncedProfileId] = useState<number | null>(null);
  const [showConnectDialog, setShowConnectDialog] = useState(false);
  const [selectedPlatform, setSelectedPlatform] = useState<
    (typeof availablePlatforms)[number] | null
  >(null);
  const [username, setUsername] = useState("");
  const [isConnecting, setIsConnecting] = useState(false);
  const [connectError, setConnectError] = useState<string | null>(null);

  // Filter out platforms from coming soon if user has a profile for them
  const connectedPlatformNames = new Set(profiles.map((p) => p.platform.toLowerCase()));
  const filteredComingSoonPlatforms = comingSoonPlatforms.filter(
    (p) => !connectedPlatformNames.has(p.name.toLowerCase()),
  );

  // Filter available platforms to show only those not connected
  const availablePlatformsToConnect = availablePlatforms.filter(
    (p) => !connectedPlatformNames.has(p.value),
  );

  const handleSync = async (profile: PlatformProfile) => {
    setSyncingProfileId(profile.id);
    setLastSyncedProfileId(null);
    try {
      await syncProfile(profile);
      setLastSyncedProfileId(profile.id);
    } catch {
      // Error state captured by syncError hook
    } finally {
      setSyncingProfileId(null);
    }
  };

  const handleConnectClick = (platform: (typeof availablePlatforms)[number]) => {
    setSelectedPlatform(platform);
    setUsername("");
    setConnectError(null);
    setShowConnectDialog(true);
  };

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedPlatform || !username.trim()) return;

    setIsConnecting(true);
    setConnectError(null);

    try {
      const data: PlatformProfileCreate = {
        platform: selectedPlatform.value,
        username: username.trim(),
      };
      await createPlatformProfile(data);
      setShowConnectDialog(false);
      setUsername("");
      await refetch();
    } catch (error) {
      setConnectError(getDashboardErrorMessage(error));
    } finally {
      setIsConnecting(false);
    }
  };

  const handleDeleteProfile = async (profileId: number) => {
    try {
      await deletePlatformProfile(profileId);
      await refetch();
    } catch (error) {
      console.error("Failed to delete profile:", error);
    }
  };

  if (!authenticated) {
    return (
      <EmptyState
        title="Sign in to view your platforms"
        description="Sign in with your CodePulse account to view and sync your connected platform profiles."
      />
    );
  }

  if (isLoading) {
    return (
      <div className="grid gap-6 xl:grid-cols-2" aria-busy>
        {Array.from({ length: 2 }).map((_, i) => (
          <div key={i} className="surface-card space-y-6 p-6">
            <div className="flex items-center gap-3">
              <Skeleton className="h-12 w-12 rounded-2xl" />
              <div className="space-y-2">
                <Skeleton className="h-5 w-32" />
                <Skeleton className="h-3 w-20" />
              </div>
            </div>
            <Skeleton className="h-20 w-full rounded-xl" />
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return <ErrorState description={getDashboardErrorMessage(error)} onRetry={() => refetch()} />;
  }

  return (
    <div className="space-y-6">
      {/* Connect Platform Section */}
      {availablePlatformsToConnect.length > 0 && (
        <Panel
          title="Connect a platform"
          caption="Add your competitive programming handles to sync your progress"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            {availablePlatformsToConnect.map((platform) => (
              <button
                key={platform.value}
                onClick={() => handleConnectClick(platform)}
                className="lift flex items-center gap-3 rounded-2xl border border-border bg-muted/40 p-4 text-left transition-colors hover:bg-muted/60"
              >
                <span
                  className={cn(
                    "flex h-10 w-10 shrink-0 items-center justify-center rounded-xl text-label font-bold",
                    platform.tint,
                  )}
                  aria-hidden
                >
                  {platform.short}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-caption font-semibold">{platform.name}</p>
                  <p className="text-label text-subtle">Connect your account</p>
                </div>
                <Plus className="h-4 w-4 text-subtle" strokeWidth={1.8} />
              </button>
            ))}
          </div>
        </Panel>
      )}

      {profiles.length === 0 ? (
        <EmptyState
          title="No platform profiles connected"
          description="Connect a platform above to start tracking your competitive programming progress."
        />
      ) : (
        <div className="grid gap-6 xl:grid-cols-2">
          {profiles.map((p) => (
            <ProfileCard
              key={p.id}
              profile={p}
              onSync={handleSync}
              onDelete={() => handleDeleteProfile(p.id)}
              isSyncing={isSyncing && syncingProfileId === p.id}
              syncError={
                syncingProfileId === p.id || lastSyncedProfileId === p.id ? syncError : null
              }
              syncResult={syncResult}
              showSyncResult={lastSyncedProfileId === p.id}
            />
          ))}
        </div>
      )}

      <Panel
        title="Coming soon"
        caption="More integrations on the roadmap — join the waitlist to get them first"
        action={
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-muted">
            <Trophy className="h-4 w-4 text-subtle" strokeWidth={1.6} />
          </span>
        }
      >
        {filteredComingSoonPlatforms.length > 0 ? (
          <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {filteredComingSoonPlatforms.map((p) => (
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
        ) : (
          <p className="text-caption text-muted-foreground">
            All available platforms are connected!
          </p>
        )}
      </Panel>

      {/* Connect Platform Dialog */}
      {showConnectDialog && selectedPlatform && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="surface-card w-full max-w-md p-6">
            <h2 className="text-h2 mb-2">Connect {selectedPlatform.name}</h2>
            <p className="text-label text-muted-foreground mb-6">
              Enter your {selectedPlatform.name} username to connect your account.
            </p>

            <form onSubmit={handleConnect} className="space-y-4">
              <div>
                <label htmlFor="username" className="text-label mb-2 block">
                  Username
                </label>
                <input
                  id="username"
                  type="text"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder={`Your ${selectedPlatform.name} username`}
                  className="w-full rounded-lg border border-border bg-background px-4 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-ring"
                  disabled={isConnecting}
                  autoFocus
                />
              </div>

              {connectError && (
                <div className="rounded-lg bg-destructive/10 p-3 text-caption text-destructive">
                  {connectError}
                </div>
              )}

              <div className="flex gap-3 justify-end">
                <ActionButton
                  type="button"
                  variant="ghost"
                  onClick={() => setShowConnectDialog(false)}
                  disabled={isConnecting}
                >
                  Cancel
                </ActionButton>
                <ActionButton type="submit" disabled={isConnecting || !username.trim()}>
                  {isConnecting ? "Connecting..." : "Connect"}
                </ActionButton>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
