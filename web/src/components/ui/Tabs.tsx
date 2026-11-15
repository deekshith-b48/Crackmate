"use client";
import { cn } from "@/lib/cn";

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string }[]; value: T; onChange: (id: T) => void }) {
  return (
    <div role="tablist" className="mb-6 inline-flex max-w-full overflow-x-auto rounded-[var(--radius-control)] bg-slate-100 p-1">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          role="tab"
          aria-selected={value === tab.id}
          onClick={() => onChange(tab.id)}
          className={cn("rounded-md px-4 py-1.5 text-sm font-medium transition-colors duration-150", value === tab.id ? "bg-surface text-ink shadow-[0_0_0_1px_var(--color-line)]" : "text-muted hover:text-ink")}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}
