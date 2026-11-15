"use client";
import { motion } from "framer-motion";

/** Animated progress ring. Shows a dash when nothing has been assessed yet. */
export function ReadinessRing({ value, size = 168, max = 100 }: { value: number | null; size?: number; max?: number }) {
  const stroke = 12;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  return (
    <div className="relative" style={{ width: size, height: size }} role="img" aria-label={value === null ? "Readiness not assessed yet" : `Readiness ${value} out of ${max}`}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--color-brand-100)" strokeWidth={stroke} />
        <motion.circle cx={size / 2} cy={size / 2} r={radius} fill="none" stroke="var(--color-brand-600)" strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={circumference} initial={{ strokeDashoffset: circumference }} animate={{ strokeDashoffset: circumference * (1 - Math.min(1, (value ?? 0) / max)) }} transition={{ duration: 1, ease: "easeOut" }} />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-4xl font-semibold tracking-tight text-ink">{value ?? "—"}</span>
        <span className="text-xs text-muted">{value === null ? "not assessed" : `out of ${max}`}</span>
      </div>
    </div>
  );
}
