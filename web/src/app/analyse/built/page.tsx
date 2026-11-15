"use client";
import { GitCommitHorizontal } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { IdentityPicker } from "@/components/analyse/IdentityPicker";
import { NeedRepo } from "@/components/analyse/NeedRepo";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useOverview } from "@/lib/career";
import { useProfiles } from "@/lib/profile";

export default function Built() {
  const { active } = useProfiles();
  const pid = active?.id;
  const { data } = useOverview(pid);
  const [editing, setEditing] = useState<string | null>(null);
  const withRepo = data?.filter((c) => c.repo) ?? [];
  return (
    <>
      <PageHeader title="What you built" description="How much of each project's code you personally wrote, from the commit history. Interviewers will ask about all of it, so know the parts you did not write too." />
      {!pid ? <NoProfile /> : !data ? null : withRepo.length === 0 ? <NeedRepo what="Ownership numbers" /> : (
        <div className="space-y-5">
          {withRepo.map((c) => { const r = c.repo!; const o = r.ownership; return (
            <Card key={c.project_id} className="space-y-4">
              <div className="flex flex-wrap items-center gap-3"><h2 className="flex-1 text-lg font-semibold text-ink">{c.title}</h2><Badge>{o.commits} commits · {r.authors.length} author{r.authors.length === 1 ? "" : "s"}</Badge></div>
              {!o.identified || editing === c.project_id ? <IdentityPicker pid={pid!} projectId={c.project_id} repo={r} initial={r.identities} onSaved={() => setEditing(null)} /> : (
                <>
                  <div>
                    <div className="mb-1 flex items-end justify-between"><p><span className="text-3xl font-semibold text-ink">{Math.round(o.share * 100)}%</span> <span className="text-sm text-muted">of added lines · {o.your_commits} of {o.commits} commits</span></p><button className="text-sm text-brand-700 underline" onClick={() => setEditing(c.project_id)}>Change who you are</button></div>
                    <div className="h-2.5 overflow-hidden rounded-full bg-slate-100"><div className="h-full rounded-full bg-brand-600 transition-[width] duration-500" style={{ width: `${o.share * 100}%` }} /></div>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2">
                    <div><h3 className="mb-2 text-sm font-semibold text-ink">Files you mostly wrote</h3>{o.files_yours.length ? <ul className="space-y-1">{o.files_yours.slice(0, 6).map((f) => <li key={f.path} className="flex items-center gap-2 text-sm"><code className="min-w-0 flex-1 truncate font-mono text-xs">{f.path}</code><span className="text-xs text-muted">{Math.round(f.yours * 100)}% yours</span></li>)}</ul> : <p className="text-sm text-muted">No file is mostly yours yet.</p>}</div>
                    <div className="rounded-[var(--radius-control)] bg-warn-tint p-3"><h3 className="mb-2 text-sm font-semibold text-ink">You did not write these, but may be asked</h3>{o.files_not_yours.length ? <ul className="space-y-1">{o.files_not_yours.slice(0, 6).map((f) => <li key={f.path} className="flex items-center gap-2 text-sm"><code className="min-w-0 flex-1 truncate font-mono text-xs">{f.path}</code><span className="text-xs text-muted">{Math.round(f.yours * 100)}% yours</span></li>)}</ul> : <p className="text-sm text-muted">Nothing significant. You wrote nearly everything you touched.</p>}<p className="mt-2 text-xs text-muted">Read these files before the interview so you can explain how they work.</p></div>
                  </div>
                </>
              )}
              <div className="flex flex-wrap gap-2 border-t border-line pt-3"><Link href={`/learn/projects/?project=${c.project_id}`}><Button size="sm">Open project</Button></Link><Link href="/analyse/talking-points/"><Button size="sm" variant="ghost">See talking points</Button></Link></div>
            </Card>); })}
          {data.length > withRepo.length && <p className="flex items-center gap-2 text-sm text-muted"><GitCommitHorizontal className="size-4" /> {data.length - withRepo.length} project(s) have no repository attached.</p>}
        </div>
      )}
    </>
  );
}
