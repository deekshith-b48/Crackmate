"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpenCheck, RefreshCw, Search } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Input } from "@/components/ui/Field";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { Tabs } from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { useProfiles, type Status } from "@/lib/profile";
import { useJob } from "@/lib/stream";
import type { WikiRow } from "@/lib/types";

const TONE = { fresh: "good", stale: "warn", none: "neutral" } as const;
const LABEL = { fresh: "Fresh", stale: "Stale", none: "Not generated" } as const;

export default function Wiki() {
  const { active } = useProfiles();
  const pid = active?.id;
  const client = useQueryClient();
  const toast = useToast();
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: () => api.get<Status>("/api/status") });
  const { data: rows = [] } = useQuery({ queryKey: ["wiki", pid], queryFn: () => api.get<WikiRow[]>(`/api/profiles/${pid}/career/wiki`), enabled: !!pid });
  const [filter, setFilter] = useState<"all" | "fresh" | "stale" | "none">("all");
  const [q, setQ] = useState("");
  const job = useJob<{ refreshed: number; failed: string[]; remaining: number }>();
  const stale = rows.filter((r) => r.status === "stale").length;
  const shown = useMemo(() => rows.filter((r) => (filter === "all" || r.status === filter) && `${r.group} ${r.title} ${r.kind}`.toLowerCase().includes(q.toLowerCase())), [rows, filter, q]);
  const groups = useMemo(() => shown.reduce<Record<string, WikiRow[]>>((acc, r) => ({ ...acc, [r.group]: [...(acc[r.group] ?? []), r] }), {}), [shown]);

  async function refresh() {
    const out = await job.run(`/api/profiles/${pid}/career/wiki/refresh`, { limit: 4 });
    if (!out) return;
    client.invalidateQueries({ queryKey: ["wiki", pid] });
    client.invalidateQueries({ queryKey: ["career-summary", pid] });
    toast(out.failed.length ? "bad" : "good", `${out.refreshed} page${out.refreshed === 1 ? "" : "s"} rewritten.` + (out.remaining ? ` ${out.remaining} more are still stale.` : "") + (out.failed.length ? ` Could not finish: ${out.failed[0]}` : ""));
  }

  return (
    <>
      <PageHeader title="Study wiki" description="Every page CrackMate can write for you, with a badge showing whether it still matches your profile, repository and models." />
      {!pid ? <NoProfile /> : rows.length === 0 ? <EmptyState icon={BookOpenCheck} title="Your wiki starts with a project" text="Add a project and its pages will be listed here, ready to generate." /> : (
        <div className="space-y-5">
          {stale > 0 && (
            <Card className="flex flex-wrap items-center gap-4 border-amber-200 bg-warn-tint py-4">
              <div className="min-w-0 flex-1"><p className="font-semibold text-ink">{stale} page{stale === 1 ? " is" : "s are"} out of date</p><p className="text-sm text-body">Refreshing rewrites up to four pages at a time, and each is one model call. Pages you have not generated are left alone.</p></div>
              <Button variant="primary" onClick={refresh} loading={job.status === "running"} disabled={!status?.has_key}><RefreshCw className="size-4" /> Refresh stale pages</Button>
            </Card>
          )}
          {job.status === "running" && <StepGenerating title="Refreshing stale pages" steps={job.steps} running startedAt={job.startedAt} />}
          {job.status === "error" && <p role="alert" className="text-sm text-bad">{job.error}</p>}
          <div className="flex flex-wrap items-center gap-x-6 gap-y-3 [&_[role=tablist]]:mb-0">
            <Tabs tabs={[{ id: "all" as const, label: `All ${rows.length}` }, { id: "fresh" as const, label: "Fresh" }, { id: "stale" as const, label: "Stale" }, { id: "none" as const, label: "Not generated" }]} value={filter} onChange={setFilter} />
            <div className="relative min-w-60 flex-1 sm:max-w-xs"><Search className="absolute left-3 top-3 size-4 text-muted" aria-hidden /><Input aria-label="Search pages" placeholder="Search pages" value={q} onChange={(e) => setQ(e.target.value)} className="pl-9" /></div>
          </div>
          {Object.entries(groups).map(([group, list]) => (
            <section key={group}>
              <h2 className="mb-2 text-sm font-semibold text-ink">{group}</h2>
              <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
                <ul className="divide-y divide-line">
                  {list.map((r) => (
                    <li key={r.slot} className="flex flex-wrap items-center gap-3 px-4 py-3">
                      <div className="min-w-0 flex-1"><p className="truncate font-medium text-ink">{r.title}</p><p className="truncate text-xs text-muted" title={r.why}>{r.kind} · {r.status === "stale" ? r.why : r.model ? `written with ${r.model.split("/").pop()}` : r.why}</p></div>
                      <span title={r.why} className="cursor-help"><Badge tone={TONE[r.status]}>{LABEL[r.status]}</Badge></span>
                      <Link href={r.href}><Button size="sm" variant={r.status === "none" ? "primary" : "secondary"}>{r.status === "none" ? "Generate" : r.status === "stale" ? "Review" : "Open"}</Button></Link>
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          ))}
          {shown.length === 0 && <p className="text-sm text-muted">No pages match this filter.</p>}
        </div>
      )}
    </>
  );
}
