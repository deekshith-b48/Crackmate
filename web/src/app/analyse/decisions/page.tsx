"use client";
import { ExternalLink, Scale } from "lucide-react";
import { useState } from "react";
import { NeedRepo } from "@/components/analyse/NeedRepo";
import { NoProfile } from "@/components/learn/NoProfile";
import { ProjectPicker } from "@/components/learn/ProjectPicker";
import { RunBar } from "@/components/learn/RunBar";
import { PageHeader } from "@/components/shell/PageHeader";
import { Badge } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Markdown } from "@/components/ui/Markdown";
import { useOverview } from "@/lib/career";
import { useProfiles } from "@/lib/profile";
import { useProfile } from "@/lib/queries";
import type { DecisionData } from "@/lib/types";
import { useArtifact } from "@/lib/useArtifact";

const TONE = { high: "good", medium: "warn", low: "bad" } as const;

export default function Decisions() {
  const { active } = useProfiles();
  const pid = active?.id;
  const { data: record } = useProfile(pid);
  const { data: overview } = useOverview(pid);
  const [projectId, setProjectId] = useState("");
  const card = overview?.find((c) => c.project_id === projectId);
  const attached = !!card?.repo;
  const { state, job, run, exportHref } = useArtifact<DecisionData>(pid, "decisions", projectId, !!projectId && attached);
  const data = state?.data;

  return (
    <>
      <PageHeader title="Decisions" description="“Why did you choose X?” is the most common deep question. CrackMate finds the real decisions in your commit history, README and dependencies, then prepares the trade-off answer, citing its evidence." />
      {!pid || !record ? <NoProfile /> : (
        <div className="space-y-6">
          <ProjectPicker projects={record.profile.projects} value={projectId} onPick={setProjectId} />
          {projectId && !attached && overview && <NeedRepo what="Decisions" />}
          {projectId && attached && <RunBar state={state} job={job as never} onRun={run} runLabel="Find my decisions" redoLabel="Re-mine" runningTitle="Reading your history and writing up decisions" exportHref={exportHref} />}
          {projectId && attached && !data && job.status !== "running" && <EmptyState icon={Scale} title="Find the decisions behind your project" text="Only evidence found in the repository is used. If it is thin, you get fewer decisions, not invented ones." />}
          {data?.decisions.map((d) => (
            <Card key={d.title} className="space-y-4">
              <div className="flex flex-wrap items-start gap-3"><h2 className="flex-1 text-lg font-semibold text-ink">{d.title}</h2><span title={d.confidence === "high" ? "A commit or the README states the reason." : d.confidence === "medium" ? "The choice is clear but the reason is inferred." : "A guess from thin evidence."} className="cursor-help"><Badge tone={TONE[d.confidence]}>{d.confidence} confidence</Badge></span></div>
              <p className="text-body">{d.decision}</p>
              <div className="flex flex-wrap items-center gap-2"><span className="text-xs font-medium uppercase tracking-wide text-muted">Evidence</span>
                {d.evidence.map((e) => e.kind === "commit" && card?.repo ? <a key={e.ref} href={`${card.repo.url}/commit/${e.ref}`} target="_blank" rel="noreferrer noopener" className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-0.5 font-mono text-xs text-body hover:bg-brand-50" title={e.quote}>commit {e.ref}<ExternalLink className="size-3" /></a> : <Badge key={e.ref}>{e.kind} · {e.ref}</Badge>)}
              </div>
              {d.alternatives.length > 0 && <p className="text-sm text-muted">Options not taken: {d.alternatives.join(" · ")}</p>}
              <div className="rounded-[var(--radius-control)] bg-brand-50/60 p-4">
                <p className="text-xs font-medium uppercase tracking-wide text-muted">Likely question</p><p className="font-medium text-ink">{d.tradeoff_question}</p>
                <details className="mt-3"><summary className="cursor-pointer text-sm font-medium text-brand-700">Show a spoken answer</summary><div className="mt-2"><Markdown>{d.answer}</Markdown>{d.assumption && <p className="mt-2 text-sm text-warn">Assumption: {d.assumption}</p>}</div></details>
              </div>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
