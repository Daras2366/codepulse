import { Link, useNavigate, useRouter, useRouterState } from "@tanstack/react-router";
import {
  Bell,
  Bot,
  ChevronsLeft,
  Flag,
  Gauge,
  LayoutGrid,
  LineChart,
  LogOut,
  Menu,
  Moon,
  Search,
  Settings,
  Sun,
  Trophy,
  Medal,
  User,
  X,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { logout } from "@/api/auth";
import { useTheme } from "@/hooks/use-theme";
import { useUser } from "@/hooks/useUser";
import { cn } from "@/lib/utils";

const nav = [
  { to: "/", label: "Dashboard", icon: LayoutGrid },
  { to: "/analytics", label: "Analytics", icon: LineChart },
  { to: "/platforms", label: "Platforms", icon: Gauge },
  { to: "/contests", label: "Contests", icon: Trophy },
  { to: "/goals", label: "Goals", icon: Flag },
  { to: "/achievements", label: "Achievements", icon: Medal },
  { to: "/ai-coach", label: "AI Coach", icon: Bot },
  { to: "/settings", label: "Settings", icon: Settings },
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Derive initials from a username or full_name (max 2 chars, uppercase). */
function deriveInitials(username: string | undefined, fullName: string | null | undefined): string {
  // Prefer full_name initials (e.g. "Jane Doe" → "JD")
  if (fullName) {
    const parts = fullName.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    }
    return fullName.slice(0, 2).toUpperCase();
  }
  // Fall back to first two chars of username
  if (username) {
    return username.slice(0, 2).toUpperCase();
  }
  return "?";
}

// ---------------------------------------------------------------------------
// Theme toggle
// ---------------------------------------------------------------------------

function ThemeToggle({
  dark,
  onToggle,
  tone,
}: {
  dark: boolean;
  onToggle: () => void;
  tone?: "sidebar";
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-label="Toggle theme"
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-full border transition-colors duration-300",
        tone === "sidebar"
          ? "border-sidebar-border text-sidebar-foreground hover:bg-sidebar-accent"
          : "border-border bg-card text-foreground hover:bg-accent",
      )}
    >
      {dark ? (
        <Sun className="h-4 w-4" strokeWidth={1.6} />
      ) : (
        <Moon className="h-4 w-4" strokeWidth={1.6} />
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Sidebar inner
// ---------------------------------------------------------------------------

function SidebarInner({
  collapsed,
  dark,
  onToggleTheme,
  onNavigate,
}: {
  collapsed: boolean;
  dark: boolean;
  onToggleTheme: () => void;
  onNavigate?: () => void;
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { user, authenticated } = useUser();
  const navigate = useNavigate();
  const router = useRouter();
  const queryClient = useQueryClient();

  const handleLogout = () => {
    logout();
    queryClient.clear();
    void router.invalidate().then(() => navigate({ to: "/auth" }));
  };

  const initials = authenticated && user ? deriveInitials(user.username, user.full_name) : "?";
  const displayName = authenticated && user ? user.username : null;
  const displaySub = authenticated && user ? user.email : null;

  return (
    <div className="flex h-full flex-col bg-sidebar px-4 py-6 text-sidebar-foreground">
      <div className={cn("flex items-center gap-3 px-2", collapsed && "justify-center px-0")}>
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-green text-[15px] font-bold text-[#111111]">
          ~
        </span>
        {!collapsed && (
          <span className="text-card-title tracking-tight">
            Code<span className="text-sidebar-muted">Pulse</span>
          </span>
        )}
      </div>

      <nav className="mt-9 flex flex-1 flex-col gap-1">
        {nav.map((item) => {
          const active = pathname === item.to;
          return (
            <Link
              key={item.to}
              to={item.to}
              onClick={onNavigate}
              className={cn(
                "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-caption font-medium transition-all duration-200 hover:translate-x-0.5",
                active
                  ? "bg-sidebar-accent text-sidebar-foreground"
                  : "text-sidebar-muted hover:bg-sidebar-accent/60 hover:text-sidebar-foreground",
                collapsed && "justify-center px-0",
              )}
            >
              <item.icon className="h-[18px] w-[18px] shrink-0" strokeWidth={1.6} />
              {!collapsed && <span className="truncate">{item.label}</span>}
              {!collapsed && active && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-green" />
              )}
            </Link>
          );
        })}
      </nav>

      {/* User identity footer */}
      <div className="mt-6 border-t border-sidebar-border pt-4">
        <div className={cn("flex items-center gap-3", collapsed && "flex-col gap-3")}>
          <span
            className={cn(
              "flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-caption font-semibold text-[#111111]",
              authenticated ? "bg-pink" : "bg-muted text-muted-foreground",
            )}
            aria-label={authenticated ? `Signed in as ${displayName ?? ""}` : "Not signed in"}
          >
            {authenticated ? (
              initials
            ) : (
              <User className="h-4 w-4 text-muted-foreground" strokeWidth={1.6} />
            )}
          </span>
          {!collapsed && (
            <div className="min-w-0 flex-1">
              {authenticated && displayName ? (
                <>
                  <p className="truncate text-caption font-semibold">{displayName}</p>
                  {displaySub && (
                    <p className="truncate text-label text-sidebar-muted">{displaySub}</p>
                  )}
                </>
              ) : (
                <p className="truncate text-caption text-sidebar-muted">Not signed in</p>
              )}
            </div>
          )}
          <ThemeToggle dark={dark} onToggle={onToggleTheme} tone="sidebar" />
          {authenticated && (
            <button
              type="button"
              onClick={handleLogout}
              aria-label="Log out"
              title="Log out"
              className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-sidebar-border text-sidebar-foreground transition-colors hover:bg-sidebar-accent hover:text-destructive"
            >
              <LogOut className="h-4 w-4" strokeWidth={1.6} />
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AppShell
// ---------------------------------------------------------------------------

export function AppShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: ReactNode;
}) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const { theme, toggle } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const dark = theme === "dark";

  const { user, authenticated } = useUser();
  const initials = authenticated && user ? deriveInitials(user.username, user.full_name) : "?";

  return (
    <div className="flex min-h-screen w-full bg-background">
      <aside
        className={cn(
          "hidden shrink-0 transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] lg:block",
          collapsed ? "w-[84px]" : "w-[280px]",
        )}
      >
        <div
          className={cn(
            "fixed top-0 bottom-0 left-0 transition-[width] duration-300 ease-out",
            collapsed ? "w-[84px]" : "w-[280px]",
          )}
        >
          <SidebarInner collapsed={collapsed} dark={dark} onToggleTheme={toggle} />
        </div>
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 animate-in fade-in bg-black/45 duration-200"
            onClick={() => setMobileOpen(false)}
          />
          <div className="absolute top-0 bottom-0 left-0 w-[280px] animate-in slide-in-from-left duration-300">
            <SidebarInner
              collapsed={false}
              dark={dark}
              onToggleTheme={toggle}
              onNavigate={() => setMobileOpen(false)}
            />
          </div>
          <button
            type="button"
            aria-label="Close navigation"
            onClick={() => setMobileOpen(false)}
            className="absolute top-5 right-5 inline-flex h-9 w-9 items-center justify-center rounded-full bg-card text-foreground"
          >
            <X className="h-4 w-4" strokeWidth={1.6} />
          </button>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 border-b border-border/70 bg-background/85 backdrop-blur-md">
          <div className="flex items-center gap-3 px-5 py-4 md:px-8 lg:px-10">
            <button
              type="button"
              aria-label="Open navigation"
              onClick={() => setMobileOpen(true)}
              className="press inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card lg:hidden"
            >
              <Menu className="h-4 w-4" strokeWidth={1.6} />
            </button>
            <button
              type="button"
              aria-label="Collapse sidebar"
              onClick={() => setCollapsed((c) => !c)}
              className="press hidden h-9 w-9 items-center justify-center rounded-full border border-border bg-card hover:bg-accent lg:inline-flex"
            >
              <ChevronsLeft
                className={cn(
                  "h-4 w-4 transition-transform duration-300",
                  collapsed && "rotate-180",
                )}
                strokeWidth={1.6}
              />
            </button>

            <label className="relative ml-1 hidden min-w-0 flex-1 items-center sm:flex">
              <Search
                className="pointer-events-none absolute left-4 h-4 w-4 text-subtle"
                strokeWidth={1.6}
              />
              <input
                placeholder="Search problems, contests, topics…"
                className="h-10 w-full max-w-md rounded-full border border-border bg-card pr-4 pl-11 text-caption text-foreground outline-none transition-colors placeholder:text-subtle focus:border-violet"
              />
            </label>

            <div className="ml-auto flex items-center gap-2">
              <button
                type="button"
                aria-label="Notifications"
                className="press relative inline-flex h-9 w-9 items-center justify-center rounded-full border border-border bg-card hover:bg-accent"
              >
                <Bell className="h-4 w-4" strokeWidth={1.6} />
                <span className="absolute top-2 right-2.5 h-1.5 w-1.5 rounded-full bg-danger" />
              </button>
              <ThemeToggle dark={dark} onToggle={toggle} />
              {/* Header avatar — mirrors sidebar identity */}
              <span
                className={cn(
                  "flex h-9 w-9 items-center justify-center rounded-full text-caption font-semibold text-[#111111]",
                  authenticated ? "bg-violet" : "bg-muted",
                )}
                aria-label={
                  authenticated ? `Signed in as ${user?.username ?? ""}` : "Not signed in"
                }
              >
                {authenticated ? (
                  initials
                ) : (
                  <User className="h-4 w-4 text-muted-foreground" strokeWidth={1.6} />
                )}
              </span>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1400px] flex-1 px-5 py-8 md:px-8 lg:px-10 lg:py-10">
          <div key={`${pathname}-head`} className="page-enter mb-8">
            <h1 className="text-h1">{title}</h1>
            <p className="mt-2 text-body text-muted-foreground">{subtitle}</p>
          </div>
          <div key={pathname} className="page-enter">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
