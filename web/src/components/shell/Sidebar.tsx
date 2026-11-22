"use client";
import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api, API_BASE } from "@/lib/api";
import { cn } from "@/lib/cn";
import { NAV } from "@/lib/nav";
import { Moon, Plus, Sun, X } from "lucide-react";
import { useProfiles, type Status } from "@/lib/profile";
import { useTheme } from "@/lib/theme";

export function Sidebar({ open = false, onClose = () => {} }: { open?: boolean; onClose?: () => void }) {
  const path = usePathname();
  const { theme, toggle } = useTheme();
  const { profiles, active, setActive } = useProfiles();
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: () => api.get<Status>("/api/status") });
  const isActive = (href: string) => (href === "/" ? path === "/" : path.startsWith(href.replace(/\/$/, "")));

  return (
    <aside className={cn("fixed inset-y-0 left-0 z-50 flex w-72 max-w-[85vw] flex-col border-r border-line bg-surface transition-transform duration-200 lg:w-64 lg:max-w-none lg:translate-x-0", open ? "translate-x-0" : "-translate-x-full")}>
      <div className="flex items-center justify-between px-5 py-5">
        <Link href="/" aria-label="CrackMate home">
          <img src="/brand/wordmark-light.png" alt="CrackMate" width={150} height={31} className="logo-light h-[31px] w-auto" />
          <img src="/brand/wordmark-dark.png" alt="CrackMate" width={150} height={31} className="logo-dark h-[31px] w-auto" />
        </Link>
        <button onClick={onClose} aria-label="Close menu" className="flex size-9 items-center justify-center rounded-[var(--radius-control)] text-muted hover:bg-slate-100 lg:hidden"><X className="size-5" /></button>
      </div>

      <div className="px-4 pb-3">
        <label className="mb-1 block px-1 text-[11px] font-medium uppercase tracking-wide text-muted" htmlFor="profile">Profile</label>
        <select
          id="profile"
          value={active?.id ?? ""}
          onChange={(e) => setActive(e.target.value)}
          disabled={!profiles.length}
          className="h-9 w-full rounded-[var(--radius-control)] border border-line bg-surface px-2 text-sm text-ink disabled:text-muted"
        >
          {!profiles.length && <option value="">No profile yet</option>}
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>{p.name || p.role || "Profile"} · {p.id.slice(0, 6)}</option>
          ))}
        </select>
        {profiles.length > 0 && (
          <a href="/setup/?tab=new" className="mt-2 flex h-9 w-full items-center justify-center gap-1.5 rounded-[var(--radius-control)] border border-dashed border-brand-500/60 text-sm font-medium text-brand-700 transition-colors hover:bg-brand-50">
            <Plus className="size-4" aria-hidden /> Add another resume
          </a>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-3 pb-4" aria-label="Main">
        {NAV.map((group) => (
          <div key={group.title} className="mt-4 first:mt-1">
            <p className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wide text-muted">{group.title}</p>
            {group.items.map(({ href, label, icon: Icon, hint }) => (
              <Link
                key={href}
                href={href}
                title={hint}
                aria-current={isActive(href) ? "page" : undefined}
                className={cn(
                  "group relative flex items-center gap-2.5 rounded-[var(--radius-control)] px-2.5 py-2 text-sm transition-colors duration-150",
                  isActive(href) ? "bg-brand-50 font-medium text-brand-700" : "text-body hover:bg-slate-100",
                )}
              >
                {isActive(href) && <span className="absolute inset-y-1.5 left-0 w-0.5 rounded-full bg-brand-600" />}
                <Icon className="size-[18px] shrink-0" aria-hidden />
                {label}
              </Link>
            ))}
          </div>
        ))}
      </nav>

      {active && <a href={`${API_BASE}/api/profiles/${active.id}/export/all`} download className="mx-4 mb-3 block rounded-[var(--radius-control)] border border-line px-3 py-2 text-center text-xs font-medium text-body hover:bg-slate-50">Download all material</a>}
      <div className="border-t border-line px-5 py-4 text-xs">
        <div className="flex items-center justify-between gap-2">
          <p className="flex items-center gap-2 font-medium text-ink">
            <span className={cn("size-2 rounded-full", status?.has_key ? "bg-good" : "bg-warn")} />
            {status ? (status.has_key ? "Groq connected" : "Using your AI assistant (MCP)") : "Connecting…"}
          </p>
          <button onClick={toggle} aria-label={theme === "dark" ? "Switch to light theme" : "Switch to dark theme"} title={theme === "dark" ? "Light theme" : "Dark theme"}
            className="flex size-8 items-center justify-center rounded-[var(--radius-control)] text-muted transition-colors hover:bg-slate-100 hover:text-ink">
            {theme === "dark" ? <Sun className="size-4" /> : <Moon className="size-4" />}
          </button>
        </div>
        {status && <p className="mt-1 truncate text-muted" title={status.model}>{status.model}</p>}
      </div>
    </aside>
  );
}
