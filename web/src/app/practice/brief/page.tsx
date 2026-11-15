"use client";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, Circle, Download, FileText } from "lucide-react";
import Link from "next/link";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Markdown } from "@/components/ui/Markdown";
import { api, API_BASE } from "@/lib/api";
import { useProfiles } from "@/lib/profile";
import type { Brief } from "@/lib/types";

export default function BriefPage() {
  const { active } = useProfiles();
  const pid = active?.id;
  const { data } = useQuery({ queryKey: ["brief", pid], queryFn: () => api.get<Brief>(`/api/profiles/${pid}/career/brief`), enabled: !!pid });
  const c = data?.checklist;
  const items = c ? [
    { label: `Pitches written: ${c.pitches[0]} of ${c.pitches[1]}`, done: c.pitches[1] > 0 && c.pitches[0] === c.pitches[1], href: "/learn/pitch/" },
    { label: "Resume claim check run", done: c.claim_check, href: "/learn/claims/" },
    { label: `Lessons saved for your top risks: ${c.lessons} of 5`, done: c.lessons >= 3, href: "/practice/study-first/" },
    { label: `Repositories attached: ${c.repos}`, done: c.repos > 0, href: "/learn/projects/" },
    { label: c.decisions[1] ? `Decisions mined: ${c.decisions[0]} of ${c.decisions[1]}` : "Decisions mined (needs an attached repo)", done: c.decisions[1] > 0 && c.decisions[0] === c.decisions[1], href: "/analyse/decisions/" },
  ] : [];
  return (
    <>
      <PageHeader title="Interview brief" description="One document with everything you have prepared: pitches, risks, claims to defend and key answers. Read it the night before. It is built only from what you have already generated, so nothing here is new or invented."
        actions={pid ? <a href={`${API_BASE}/api/profiles/${pid}/career/brief/export`} download><Button variant="primary"><Download className="size-4" /> Download Markdown</Button></a> : undefined} />
      {!pid ? <NoProfile /> : !data ? null : data.markdown.length < 300 ? <EmptyState icon={FileText} title="Your brief is empty" text="Add a project and generate a pitch or lesson, and the brief fills itself in." /> : (
        <div className="grid gap-6 lg:grid-cols-[1fr_300px]">
          <Card className="min-w-0"><Markdown>{data.markdown}</Markdown></Card>
          <aside className="space-y-3 lg:sticky lg:top-6 lg:self-start">
            <Card className="space-y-3 py-4"><h2 className="text-sm font-semibold text-ink">What makes it stronger</h2>
              <ul className="space-y-2.5">{items.map((i) => <li key={i.label}><Link href={i.href} className="flex items-start gap-2 text-sm hover:underline">{i.done ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-good" /> : <Circle className="mt-0.5 size-4 shrink-0 text-muted" />}<span className={i.done ? "text-muted" : "text-ink"}>{i.label}</span></Link></li>)}</ul>
            </Card>
          </aside>
        </div>
      )}
    </>
  );
}
