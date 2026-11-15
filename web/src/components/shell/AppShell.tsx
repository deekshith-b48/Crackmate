"use client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { Menu } from "lucide-react";
import { ProfileProvider } from "@/lib/profile";
import { ThemeProvider } from "@/lib/theme";
import { ToastProvider } from "../ui/Toast";
import { Sidebar } from "./Sidebar";

export function AppShell({ children }: { children: ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 10_000, retry: 1, refetchOnWindowFocus: false } } }));
  const [open, setOpen] = useState(false);
  const path = usePathname();
  useEffect(() => setOpen(false), [path]);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
      <ProfileProvider>
        <ToastProvider>
          <header className="sticky top-0 z-30 flex items-center gap-3 border-b border-line bg-surface/90 px-4 py-2.5 backdrop-blur lg:hidden">
            <button onClick={() => setOpen(true)} aria-label="Open menu" aria-expanded={open} className="flex size-10 items-center justify-center rounded-[var(--radius-control)] text-ink hover:bg-slate-100">
              <Menu className="size-5" />
            </button>
            <img src="/brand/icon.png" alt="" width={28} height={28} className="size-7" />
            <span className="font-semibold text-ink">CrackMate</span>
          </header>
          {open && <div className="fixed inset-0 z-40 bg-black/50 lg:hidden" onClick={() => setOpen(false)} aria-hidden />}
          <Sidebar open={open} onClose={() => setOpen(false)} />
          <main className="min-h-screen lg:ml-64">
            <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 sm:py-8 lg:px-10 lg:py-10 2xl:max-w-6xl">{children}</div>
          </main>
        </ToastProvider>
      </ProfileProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
