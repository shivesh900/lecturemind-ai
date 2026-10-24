import { useState, type FormEvent } from "react";
import { NavLink, Outlet, useNavigate, Navigate, useLocation } from "react-router-dom";
import {
  BarChart3, BookOpen, Download, GraduationCap, LayoutDashboard, LogOut, Moon, Search, Settings, Sun, UploadCloud, User as UserIcon, Monitor,
} from "lucide-react";
import { Logo } from "@/components/Logo";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { DemoBanner } from "@/components/DemoBanner";
import { useAuth } from "@/hooks/useAuth";
import { useTheme } from "@/hooks/useTheme";
import { cn } from "@/utils/cn";
import { Skeleton } from "@/components/ui/skeleton";

const NAV = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/upload", label: "Upload", icon: UploadCloud },
  { to: "/app/library", label: "Library", icon: BookOpen },
  { to: "/app/search", label: "Search", icon: Search },
  { to: "/app/study", label: "Study stats", icon: BarChart3 },
  { to: "/app/exports", label: "Export Center", icon: Download },
  { to: "/app/settings", label: "Settings", icon: Settings },
];

const MOBILE_NAV = [
  { to: "/app", label: "Home", icon: LayoutDashboard, end: true },
  { to: "/app/library", label: "Library", icon: BookOpen },
  { to: "/app/upload", label: "Upload", icon: UploadCloud, primary: true },
  { to: "/app/search", label: "Search", icon: Search },
  { to: "/app/settings", label: "Settings", icon: Settings },
];

export function ProtectedRoute() {
  const { user, loading } = useAuth();
  const loc = useLocation();
  if (loading)
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="w-64 space-y-3"><Skeleton className="h-8 w-40" /><Skeleton className="h-4 w-full" /><Skeleton className="h-4 w-3/4" /></div>
      </div>
    );
  if (!user) return <Navigate to={`/login?next=${encodeURIComponent(loc.pathname + loc.search)}`} replace />;
  return <AppLayout />;
}

function ThemeMenu() {
  const { theme, resolved, setTheme } = useTheme();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="icon" aria-label="Change theme">{resolved === "dark" ? <Moon /> : <Sun />}</Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {([["light", Sun, "Light"], ["dark", Moon, "Dark"], ["system", Monitor, "System"]] as const).map(([t, I, l]) => (
          <DropdownMenuItem key={t} onClick={() => setTheme(t)} className={cn(theme === t && "text-primary")}><I />{l}</DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function AppLayout() {
  const { user, logout } = useAuth();
  const nav = useNavigate();
  const [q, setQ] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (q.trim().length >= 2) nav(`/app/search?q=${encodeURIComponent(q.trim())}`);
  };
  const initials = (user?.name || "U").split(" ").map((x) => x[0]).slice(0, 2).join("").toUpperCase();

  return (
    <div className="min-h-screen bg-background">
      {/* Sidebar (desktop) */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r bg-[hsl(var(--sidebar))] lg:flex">
        <div className="flex h-16 items-center px-5"><Logo to="/app" /></div>
        <nav className="flex-1 space-y-1 px-3 py-2" aria-label="Main">
          {NAV.map(({ to, label, icon: Icon, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                cn("group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-muted-foreground transition-all hover:bg-secondary hover:text-foreground",
                  isActive && "bg-gradient-to-r from-indigo-500/15 to-violet-500/10 text-foreground shadow-[inset_2px_0_0_hsl(var(--primary))]")
              }
            >
              <Icon className="h-[18px] w-[18px]" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="m-3 rounded-2xl border bg-gradient-to-br from-indigo-500/15 via-violet-500/10 to-transparent p-4">
          <GraduationCap className="mb-2 h-5 w-5 text-primary" />
          <p className="text-sm font-semibold">Study smarter</p>
          <p className="mt-1 text-xs text-muted-foreground">Upload a lecture and get notes, quizzes and flashcards in minutes.</p>
          <Button size="sm" variant="gradient" className="mt-3 w-full" onClick={() => nav("/app/upload")}>
            <UploadCloud /> Upload lecture
          </Button>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b bg-background/80 backdrop-blur-xl">
          <DemoBanner />
          <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
            <div className="lg:hidden"><Logo to="/app" compact /></div>
            <form onSubmit={submit} className="relative max-w-md flex-1" role="search">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search lectures, notes, concepts…" className="h-10 rounded-xl pl-9" aria-label="Search all lectures" />
            </form>
            <div className="ml-auto flex items-center gap-1">
              <ThemeMenu />
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <button className="flex items-center gap-2 rounded-full p-0.5 focus:outline-none focus-visible:ring-2 focus-visible:ring-ring" aria-label="Account menu">
                    <span className="flex h-9 w-9 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 text-sm font-semibold text-white">{initials}</span>
                  </button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-56">
                  <DropdownMenuLabel>
                    <div className="text-sm font-medium text-foreground">{user?.name}</div>
                    <div className="truncate">{user?.email}</div>
                  </DropdownMenuLabel>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => nav("/app/settings")}><UserIcon />Profile & settings</DropdownMenuItem>
                  <DropdownMenuItem onClick={() => nav("/app/exports")}><Download />Export Center</DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={async () => { await logout(); nav("/login"); }} className="text-destructive focus:text-destructive"><LogOut />Sign out</DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 pb-28 pt-6 sm:px-6 lg:pb-12">
          <Outlet />
        </main>
      </div>

      {/* Bottom nav (mobile/tablet) */}
      <nav className="fixed inset-x-0 bottom-0 z-30 border-t bg-background/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden" aria-label="Mobile">
        <div className="mx-auto grid max-w-lg grid-cols-5">
          {MOBILE_NAV.map(({ to, label, icon: Icon, end, primary }) => (
            <NavLink key={to} to={to} end={end} className={({ isActive }) => cn("flex flex-col items-center gap-1 py-2 text-[11px] font-medium text-muted-foreground", isActive && "text-primary")}>
              {primary ? (
                <span className="-mt-5 flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-violet-600 text-white shadow-glow"><Icon className="h-5 w-5" /></span>
              ) : (
                <Icon className="h-5 w-5" />
              )}
              {label}
            </NavLink>
          ))}
        </div>
      </nav>
    </div>
  );
}
