"use client";
import { FileCheck2 } from "lucide-react";
import Link from "next/link";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { lessonHref, riskLabel, riskTone, useClaims } from "@/lib/career";
import { useProfiles } from "@/lib/profile";

const TONE = { High: "good", Medium: "brand", Low: "bad", Unchecked: "neutral" } as const;

export default function Claims() {
  const { active } = useProfiles();
  const { data } = useClaims(active?.id);
  const unchecked = data?.filter((r) => r.tier === "Unchecked").length ?? 0;
  return (
    <>
      <PageHeader title="Resume claims" description="Each technology you list, checked against the real code of its project. Weakest evidence first. For resume lines like “improved speed by 40%”, use the Claim Checker."
        actions={<Link href="/learn/claims/"><Button size="sm">Open Claim Checker</Button></Link>} />
      {!active ? <NoProfile /> : !data ? null : data.length === 0 ? <EmptyState icon={FileCheck2} title="No technologies to check yet" text="Add technologies to your projects, then attach each project's GitHub repo to check them against the code." /> : (
        <div className="space-y-4">
          {unchecked > 0 && <Card className="border-brand-200 bg-brand-50/40 py-3 text-sm text-body">{unchecked} claim{unchecked === 1 ? " is" : "s are"} unchecked because no repository is attached. Add one under <Link href="/learn/projects/" className="font-medium text-brand-700 underline">Learn → Projects</Link>.</Card>}
          <div className="overflow-hidden rounded-[var(--radius-card)] border border-line bg-surface">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-line bg-slate-50 text-xs uppercase tracking-wide text-muted"><tr><th className="px-4 py-3">Technology</th><th className="px-4 py-3">Evidence</th><th className="hidden px-4 py-3 md:table-cell">Found in</th><th className="px-4 py-3">Readiness</th><th className="px-4 py-3" /></tr></thead>
              <tbody className="divide-y divide-line">
                {data.map((r) => (
                  <tr key={r.project_id + r.technology}>
                    <td className="px-4 py-3"><p className="font-medium text-ink">{r.technology}</p><p className="text-xs text-muted">{r.project}</p></td>
                    <td className="px-4 py-3"><span title={r.tier_note} className="cursor-help"><Badge tone={TONE[r.tier]}>{r.tier === "Unchecked" ? "Unchecked" : `${r.tier} confidence`}</Badge></span></td>
                    <td className="hidden max-w-56 px-4 py-3 md:table-cell">{r.evidence.length ? r.evidence.slice(0, 2).map((e) => <code key={e.file} className="mr-1 block truncate font-mono text-xs text-muted" title={`${e.kind}: ${e.file}`}>{e.file}</code>) : <span className="text-xs text-muted">{r.tier_note}</span>}</td>
                    <td className="px-4 py-3">{r.readiness === null ? <span className="text-muted">Not assessed</span> : <span className="font-mono text-xs">{r.readiness}/10</span>} {r.risk > 0 && <Badge tone={riskTone(r.risk)} className="ml-1">{riskLabel(r.risk)} risk</Badge>}</td>
                    <td className="px-4 py-3 text-right">{r.weakest_concept && <Link href={lessonHref(r.weakest_concept)}><Button size="sm">Practise defending this</Button></Link>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted">High: imported in code. Medium: declared in a dependency or config file. Low: not found in the attached repo (it may live elsewhere, but expect to be asked where). Readiness is the average of the concepts behind the technology.</p>
        </div>
      )}
    </>
  );
}
