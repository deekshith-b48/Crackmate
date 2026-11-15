"use client";
import { Activity } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { RiskBadge, Trend, WhyList } from "@/components/analyse/RiskCell";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { Tabs } from "@/components/ui/Tabs";
import { cn } from "@/lib/cn";
import { lessonHref, riskTone, useSignals } from "@/lib/career";
import { useProfiles } from "@/lib/profile";

const TILE = { bad: "bg-bad-tint border-red-200 text-bad", warn: "bg-warn-tint border-amber-200 text-warn", good: "bg-good-tint border-green-200 text-good" };

export default function Risk() {
  const { active } = useProfiles();
  const { data } = useSignals(active?.id);
  const [view, setView] = useState<"table" | "heatmap">("table");
  const [filter, setFilter] = useState<"all" | "unassessed" | "assessed">("all");
  const [open, setOpen] = useState<string | null>(null);
  const rows = useMemo(() => (data?.topics ?? []).filter((t) => filter === "all" || (filter === "assessed") === t.assessed), [data, filter]);

  return (
    <>
      <PageHeader title="Interview risk" description="Risk is 0 to 10: how likely a topic is to come up (from how many of your projects depend on it) times how weak you are on it. Hover any score to see why." />
      {!active ? <NoProfile /> : !data ? null : data.topics.length === 0 ? <EmptyState icon={Activity} title="Add a project to see your risk" text="CrackMate maps each project's technologies to the concepts interviewers ask about." /> : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-center gap-6">
            <Tabs tabs={[{ id: "table" as const, label: "Table" }, { id: "heatmap" as const, label: "Heatmap" }]} value={view} onChange={setView} />
            <div className="-mt-6"><Tabs tabs={[{ id: "all" as const, label: "All" }, { id: "unassessed" as const, label: "Not assessed" }, { id: "assessed" as const, label: "Assessed" }]} value={filter} onChange={setFilter} /></div>
          </div>
          {view === "heatmap" ? (
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
              {rows.map((t) => (
                <Link key={t.topic} href={lessonHref(t.topic)} title={t.why.join("\n")} className={cn("rounded-[var(--radius-control)] border p-3 transition-transform hover:-translate-y-0.5", TILE[riskTone(t.risk)])}>
                  <p className="text-sm font-medium leading-snug">{t.topic}</p><p className="mt-1 font-mono text-xs">{t.risk.toFixed(1)} · {t.assessed ? `${t.readiness}/10` : "unassessed"}</p>
                </Link>
              ))}
            </div>
          ) : (
            <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
              <table className="w-full text-left text-sm">
                <thead className="border-b border-line bg-slate-50 text-xs uppercase tracking-wide text-muted"><tr><th className="px-4 py-3">Topic</th><th className="px-4 py-3">Likelihood</th><th className="px-4 py-3">Your strength</th><th className="px-4 py-3">Risk</th><th className="px-4 py-3">Trend</th><th className="px-4 py-3" /></tr></thead>
                <tbody className="divide-y divide-line">
                  {rows.map((t) => (
                    <>
                      <tr key={t.topic} className="cursor-pointer hover:bg-slate-50" onClick={() => setOpen(open === t.topic ? null : t.topic)}>
                        <td className="px-4 py-3 font-medium text-ink">{t.topic}</td>
                        <td className="px-4 py-3"><div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-100" title={`${Math.round(t.likelihood * 100)}% likely`}><div className="h-full rounded-full bg-brand-600" style={{ width: `${t.likelihood * 100}%` }} /></div></td>
                        <td className="px-4 py-3">{t.assessed ? <span className="font-mono text-xs">{t.readiness}/10</span> : <span className="text-muted">Not assessed</span>}</td>
                        <td className="px-4 py-3"><RiskBadge row={t} /></td>
                        <td className="px-4 py-3"><Trend trend={t.trend} /></td>
                        <td className="px-4 py-3 text-right"><Link href={lessonHref(t.topic)} onClick={(e) => e.stopPropagation()}><Button size="sm">Fix this</Button></Link></td>
                      </tr>
                      {open === t.topic && <tr key={t.topic + "-why"}><td colSpan={6} className="bg-slate-50 px-4 py-3"><WhyList why={t.why} /></td></tr>}
                    </>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  );
}
