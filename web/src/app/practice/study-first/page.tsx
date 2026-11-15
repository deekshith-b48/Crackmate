"use client";
import { ListOrdered } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { RiskBadge } from "@/components/analyse/RiskCell";
import { WhyList } from "@/components/analyse/RiskCell";
import { NoProfile } from "@/components/learn/NoProfile";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { lessonHref, useSignals } from "@/lib/career";
import { useProfiles } from "@/lib/profile";

export default function StudyFirst() {
  const { active } = useProfiles();
  const { data } = useSignals(active?.id);
  const [open, setOpen] = useState<string | null>(null);
  const list = (data?.topics ?? []).filter((t) => t.risk > 0).slice(0, 10);
  return (
    <>
      <PageHeader title="Study first" description="The topics most likely to hurt you in an interview, in order. Risk is how likely a topic is to come up times how weak you are on it." />
      {!active ? <NoProfile /> : !data ? null : list.length === 0 ? (
        <EmptyState icon={ListOrdered} title="Nothing to rank yet" text="Add a project with its technologies and CrackMate will rank the concepts behind them." action={<Link href="/setup/"><Button variant="primary">Add a project</Button></Link>} />
      ) : (
        <ol className="space-y-3">
          {list.map((t, i) => (
            <li key={t.topic}>
              <Card className="space-y-3 py-4">
                <div className="flex flex-wrap items-center gap-3">
                  <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-brand-50 text-sm font-semibold text-brand-700">{i + 1}</span>
                  <div className="min-w-0 flex-1"><h2 className="font-semibold text-ink">{t.topic}</h2><p className="text-sm text-muted">{t.assessed ? `Readiness ${t.readiness}/10` : "Not assessed yet"} · used by {t.projects} of your project(s) · {t.dependents} topic(s) build on it</p></div>
                  <RiskBadge row={t} />
                  <Link href={lessonHref(t.topic)}><Button variant="primary" size="sm">Start</Button></Link>
                  <Button size="sm" variant="ghost" onClick={() => setOpen(open === t.topic ? null : t.topic)} aria-expanded={open === t.topic}>Why?</Button>
                </div>
                {open === t.topic && <div className="border-t border-line pt-3"><WhyList why={t.why} /></div>}
              </Card>
            </li>
          ))}
        </ol>
      )}
    </>
  );
}
