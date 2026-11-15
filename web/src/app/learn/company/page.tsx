"use client";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field } from "@/components/ui/Field";
import { Tabs } from "@/components/ui/Tabs";
import { api } from "@/lib/api";
import { useProfiles } from "@/lib/profile";
import { useProfile } from "@/lib/queries";
import type { CompanyProblem } from "@/lib/types";
import { Building2 } from "lucide-react";

const WINDOWS = ["Last 30 days", "3 months", "6 months", "Over 6 months", "All time"];
const TONE = { Easy: "good", Medium: "warn", Hard: "bad" } as const;

export default function Company() {
  const { active } = useProfiles();
  const { data: record } = useProfile(active?.id);
  const list = useQuery({ queryKey: ["companies"], queryFn: () => api.get<{ companies: string[] }>("/api/company/list"), retry: false });
  const fallback = useQuery({ queryKey: ["company-fallback"], queryFn: () => api.get<{ topics: string[] }>("/api/company/fallback"), enabled: list.isError });
  const [company, setCompany] = useState("");
  const [window_, setWindow] = useState("All time");
  const [levels, setLevels] = useState<string[]>(["Easy", "Medium", "Hard"]);
  useEffect(() => {
    if (company || !list.data) return;
    const mine = (record?.profile.company ?? "").toLowerCase();
    setCompany(list.data.companies.find((c) => c.toLowerCase() === mine) ?? list.data.companies[0] ?? "");
  }, [list.data, record, company]);
  const problems = useQuery({
    queryKey: ["company-problems", company, window_, levels.join()], enabled: !!company, retry: false,
    queryFn: () => api.get<{ rows: CompanyProblem[]; focus: [string, number][] }>(`/api/company/problems?company_name=${encodeURIComponent(company)}&window=${encodeURIComponent(window_)}&levels=${levels.join(",")}`),
  });
  const toggle = (l: string) => setLevels((old) => (old.includes(l) ? old.filter((x) => x !== l) : [...old, l]));

  return (
    <>
      <PageHeader title="Company DSA" description="Problems a company is reported to tag most often. Frequencies are community-reported and relative, never a guarantee. Use them to decide where to spend your DSA time." />
      {list.isError ? (
        <Card><p className="mb-3 text-sm text-warn">{(list.error as Error).message} Showing general DSA topics instead.</p><div className="flex flex-wrap gap-2">{fallback.data?.topics.map((t) => <Badge key={t} tone="brand">{t}</Badge>)}</div></Card>
      ) : (
        <div className="space-y-6">
          <div className="flex flex-wrap items-end gap-6">
            <Field label="Company" htmlFor="company" className="min-w-64"><select id="company" value={company} onChange={(e) => setCompany(e.target.value)} className="h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm text-ink">{list.data?.companies.map((c) => <option key={c}>{c}</option>)}</select></Field>
            <div><p className="mb-1.5 text-sm font-medium text-ink">Time window</p><div className="-mb-6"><Tabs tabs={WINDOWS.map((w) => ({ id: w, label: w }))} value={window_} onChange={setWindow} /></div></div>
            <div><p className="mb-1.5 text-sm font-medium text-ink">Difficulty</p><div className="flex gap-2">{(["Easy", "Medium", "Hard"] as const).map((l) => <button key={l} onClick={() => toggle(l)} aria-pressed={levels.includes(l)} className={`rounded-full border px-3 py-1 text-sm font-medium ${levels.includes(l) ? "border-brand-600 bg-brand-50 text-brand-700" : "border-line text-muted"}`}>{l}</button>)}</div></div>
          </div>
          {problems.isError ? <p role="alert" className="text-sm text-warn">{(problems.error as Error).message}</p> : !problems.data?.rows.length ? (
            problems.isLoading ? null : <EmptyState icon={Building2} title="No problems for this choice" text="Try another time window or difficulty." />
          ) : (
            <>
              <Card><p className="mb-2 text-sm font-semibold text-ink">Focus topics</p><div className="flex flex-wrap gap-2">{problems.data.focus.map(([t, n]) => <Badge key={t} tone="brand">{t} · {n}</Badge>)}</div></Card>
              <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
                <table className="w-full text-left text-sm">
                  <thead className="border-b border-line bg-slate-50 text-xs uppercase tracking-wide text-muted"><tr><th className="px-4 py-3">Problem</th><th className="px-4 py-3">Level</th><th className="px-4 py-3">Frequency</th><th className="hidden px-4 py-3 md:table-cell">Topics</th><th className="px-4 py-3" /></tr></thead>
                  <tbody className="divide-y divide-line">
                    {problems.data.rows.map((r) => (
                      <tr key={r.Link}><td className="px-4 py-3 font-medium text-ink">{r.Title}</td><td className="px-4 py-3"><Badge tone={TONE[r.Difficulty as keyof typeof TONE] ?? "neutral"}>{r.Difficulty}</Badge></td><td className="px-4 py-3 font-mono text-xs">{Math.round(r.Frequency)}</td><td className="hidden px-4 py-3 text-muted md:table-cell">{r.Topics}</td><td className="px-4 py-3 text-right"><a href={r.Link} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 text-brand-600 hover:underline">Open <ExternalLink className="size-3.5" /></a></td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted">Data: <a className="underline" href="https://github.com/liquidslr/leetcode-company-wise-problems" target="_blank" rel="noreferrer noopener">liquidslr/leetcode-company-wise-problems</a>, fetched live and cached for 24 hours. Problem statements stay on LeetCode.</p>
            </>
          )}
        </div>
      )}
    </>
  );
}
