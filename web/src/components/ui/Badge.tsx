import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "neutral" | "brand" | "good" | "warn" | "bad";
const TONES: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700",
  brand: "bg-brand-50 text-brand-700",
  good: "bg-good-tint text-good",
  warn: "bg-warn-tint text-warn",
  bad: "bg-bad-tint text-bad",
};

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cn("inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-medium", TONES[tone], className)}>
      {children}
    </span>
  );
}

/** Easy/Medium/Hard by position in a lesson. Colour carries meaning only here. */
export function DifficultyBadge({ position, total }: { position: number; total: number }) {
  const level = Math.min(2, Math.floor((position * 3) / Math.max(total, 1)));
  const [label, tone] = [["Easy", "good"], ["Medium", "warn"], ["Hard", "bad"]][level] as [string, Tone];
  return <Badge tone={tone}>{label}</Badge>;
}
