"use client";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Download } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Markdown } from "@/components/ui/Markdown";
import { api } from "@/lib/api";
import type { InterviewReport as Report } from "@/lib/types";

export function InterviewReport({ pid, sid }: { pid: string; sid: string }) {
  const { data } = useQuery({ queryKey: ["report", pid, sid], queryFn: () => api.get<Report>(`/api/profiles/${pid}/interviews/${sid}/report`) });
  if (!data) return null;
  const download = () => {
    const url = URL.createObjectURL(new Blob([data.markdown], { type: "text/markdown" }));
    Object.assign(document.createElement("a"), { href: url, download: "crackmate-interview.md" }).click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="space-y-6">
      <Card>
        <div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold text-ink">Interview report</h2><Button size="sm" onClick={download}><Download className="size-4" /> Download</Button></div>
        <p className="mb-4 text-sm text-muted">Scored {data.scored} · Skipped {data.skipped}. Coaching estimates; a short session gives limited coverage.</p>
        {data.scores.length ? (
          <div className="space-y-3">
            {data.scores.map((s) => (
              <div key={s.label}><div className="mb-1 flex justify-between text-sm"><span className="text-ink">{s.label}</span><span className="font-mono text-xs text-muted">{s.average.toFixed(1)} / 4</span></div><div className="h-2 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-600" style={{ width: `${(s.average / 4) * 100}%` }} /></div></div>
            ))}
          </div>
        ) : <p className="text-sm text-muted">No answers were scored in this interview.</p>}
      </Card>
      {data.study_next.length > 0 && (
        <Card>
          <h3 className="mb-3 font-semibold text-ink">Study next from this interview</h3>
          <div className="flex flex-wrap gap-2">{data.study_next.map((s) => <Link key={s.href} href={s.href}><Button size="sm">{s.topic} <ArrowRight className="size-4" /></Button></Link>)}</div>
        </Card>
      )}
      <details className="rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3"><summary className="cursor-pointer text-sm font-medium text-ink">Full written report</summary><div className="mt-3"><Markdown>{data.markdown}</Markdown></div></details>
    </div>
  );
}
