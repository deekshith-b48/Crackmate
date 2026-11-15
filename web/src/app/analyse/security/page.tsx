"use client";
import { CheckCircle2, Mic, ShieldAlert } from "lucide-react";
import Link from "next/link";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useSecurity } from "@/lib/career";
import { useProfiles } from "@/lib/profile";

export default function Security() {
  const { active } = useProfiles();
  const { data } = useSecurity(active?.id);
  const found = data?.projects.reduce((n, p) => n + p.secrets.length, 0) ?? 0;
  return (
    <>
      <PageHeader title="Security check" description="Find secrets committed to your repos before an interviewer does, and get the security questions your stack invites. Secret values are masked and never stored." />
      {!active ? <NoProfile /> : !data ? null : (
        <div className="space-y-5">
          {found > 0 && (
            <Card className="border-red-200 bg-bad-tint" role="alert">
              <p className="flex items-center gap-2 font-semibold text-bad"><ShieldAlert className="size-5" /> {found} possible secret{found === 1 ? "" : "s"} committed. Fix this before any interview.</p>
              <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm text-body">{data.remediation.map((r) => <li key={r}>{r}</li>)}</ol>
            </Card>
          )}
          {data.projects.map((p) => (
            <Card key={p.project_id} className="space-y-4">
              <div className="flex flex-wrap items-center gap-3"><h2 className="flex-1 text-lg font-semibold text-ink">{p.title}</h2>
                {!p.has_repo ? <Badge>Repo not attached</Badge> : p.secrets.length ? <Badge tone="bad">{p.secrets.length} finding{p.secrets.length === 1 ? "" : "s"}</Badge> : <Badge tone="good">Clean</Badge>}</div>
              {!p.has_repo ? <p className="text-sm text-muted">Attach this project&apos;s repository to scan it. <Link href="/learn/projects/" className="text-brand-700 underline">Learn → Projects</Link></p> : p.secrets.length === 0 ? <p className="flex items-center gap-2 text-sm text-good"><CheckCircle2 className="size-4" /> No committed secrets found.</p> : (
                <ul className="space-y-1.5 text-sm">{p.secrets.map((s, i) => <li key={i} className="flex flex-wrap items-center gap-2"><Badge tone={s.severity === "high" ? "bad" : "warn"}>{s.severity}</Badge><code className="font-mono text-xs">{s.file}:{s.line}</code><span>{s.kind}</span>{s.preview && <span className="text-muted">{s.preview}</span>}</li>)}</ul>
              )}
              <div className="border-t border-line pt-3">
                <h3 className="mb-2 text-sm font-semibold text-ink">Security questions to expect</h3>
                <ul className="list-disc space-y-1 pl-5 text-sm text-body">{p.questions.map((q) => <li key={q}>{q}</li>)}</ul>
                <Link href="/practice/interview/"><Button size="sm" className="mt-3"><Mic className="size-4" /> Practise answering aloud</Button></Link>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
