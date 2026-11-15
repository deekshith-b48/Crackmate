"use client";
import { Flame, Mic } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { NeedRepo } from "@/components/analyse/NeedRepo";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useOverview } from "@/lib/career";
import { useProfiles } from "@/lib/profile";

const PROMPTS = ["What was hard about this file, and what broke along the way?", "How did you find the cause? Which tools or clues did you use?", "What exactly did you change, and why that fix?", "What would you do differently now, or what would you test first?"];

export default function TalkingPoints() {
  const { active } = useProfiles();
  const pid = active?.id;
  const { data } = useOverview(pid);
  const [open, setOpen] = useState<string | null>(null);
  const rows = (data ?? []).flatMap((c) => (c.repo?.hotspots ?? []).map((h) => ({ ...h, project: c.title, project_id: c.project_id, identified: c.repo!.ownership.identified }))).sort((a, b) => b.score - a.score).slice(0, 15);
  const has = (data ?? []).some((c) => c.repo);
  return (
    <>
      <PageHeader title="Talking points" description="The files you changed most often are where the hard problems were. Interviewers love “tell me about a challenge you solved”, so pick two and prepare a story." />
      {!pid ? <NoProfile /> : !data ? null : !has ? <NeedRepo what="Hotspots" /> : rows.length === 0 ? <Card className="text-sm text-muted">Not enough commit history yet to find hotspots. Files need more than one commit to count.</Card> : (
        <ol className="space-y-3">
          {rows.map((h, i) => {
            const key = h.project_id + h.path;
            return (
              <li key={key}>
                <Card className="space-y-3 py-4">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-warn-tint text-sm font-semibold text-warn"><Flame className="size-4" aria-hidden /></span>
                    <div className="min-w-0 flex-1"><code className="block truncate font-mono text-sm text-ink">{h.path}</code><p className="text-xs text-muted">{h.project} · {h.commits} commits · {h.churn.toLocaleString()} lines changed{h.identified ? ` · ${h.your_commits} yours` : ""}</p></div>
                    {h.identified && h.your_commits === 0 && <Badge tone="warn">Not yours</Badge>}
                    {i < 3 && <Badge tone="brand">Top story</Badge>}
                    <Button size="sm" onClick={() => setOpen(open === key ? null : key)} aria-expanded={open === key}>Prepare this story</Button>
                  </div>
                  {open === key && (
                    <div className="space-y-3 border-t border-line pt-3">
                      <p className="text-sm text-body">Answer each prompt out loud in about 30 seconds. Together they make a complete story.</p>
                      <ol className="list-decimal space-y-1 pl-5 text-sm text-body">{PROMPTS.map((p) => <li key={p}>{p}</li>)}</ol>
                      <Link href="/practice/interview/"><Button size="sm" variant="primary"><Mic className="size-4" /> Practise it in the Interview Room</Button></Link>
                    </div>
                  )}
                </Card>
              </li>
            );
          })}
        </ol>
      )}
    </>
  );
}
