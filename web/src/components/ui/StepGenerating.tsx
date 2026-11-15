"use client";
import { AnimatePresence, motion } from "framer-motion";
import { Check, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { cn } from "@/lib/cn";

/**
 * The generating animation: a live checklist of what the server is doing right now, an elapsed
 * timer and a shimmering preview of the content that is on its way. Never a blank spinner.
 */
export function StepGenerating({ title, steps, running, startedAt }: { title: string; steps: string[]; running: boolean; startedAt?: number }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(timer);
  }, [running]);
  const seconds = startedAt ? Math.max(0, Math.round((now - startedAt) / 1000)) : 0;
  const shown = steps.length ? steps : ["Getting started…"];

  return (
    <div className="rounded-[var(--radius-card)] border border-brand-100 bg-brand-50/40 p-6" role="status" aria-live="polite">
      <div className="flex items-center gap-3">
        <motion.div animate={running ? { rotate: [0, 12, -12, 0] } : {}} transition={{ repeat: Infinity, duration: 2.4 }} className="flex size-9 items-center justify-center rounded-full bg-brand-600 text-white">
          <Sparkles className="size-4" aria-hidden />
        </motion.div>
        <div className="flex-1">
          <p className="font-semibold text-ink">{title}</p>
          <p className="text-xs text-muted">{running ? `Working… ${seconds}s` : "Finished"}</p>
        </div>
      </div>
      <ul className="mt-5 space-y-2.5">
        <AnimatePresence initial={false}>
          {shown.map((text, index) => {
            const active = running && index === shown.length - 1;
            return (
              <motion.li key={index + text} initial={{ opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.2 }} className="flex items-center gap-3 text-sm">
                <span className={cn("flex size-5 shrink-0 items-center justify-center rounded-full", active ? "bg-brand-100" : "bg-good text-white")}>
                  {active ? <span className="size-2 animate-pulse rounded-full bg-brand-600" /> : <Check className="size-3 animate-pop" aria-hidden />}
                </span>
                <span className={active ? "font-medium text-ink" : "text-muted"}>{text}</span>
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ul>
      {running && (
        <div className="mt-5 space-y-2" aria-hidden>
          {[92, 78, 64].map((width) => (
            <div key={width} style={{ width: `${width}%` }} className="h-3 animate-shimmer rounded shimmer" />
          ))}
        </div>
      )}
    </div>
  );
}
