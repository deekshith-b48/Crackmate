"use client";
import { Compass } from "lucide-react";
import { useState } from "react";
import { NoProfile } from "@/components/learn/NoProfile";
import { ProjectPicker } from "@/components/learn/ProjectPicker";
import { RunBar } from "@/components/learn/RunBar";
import { PageHeader } from "@/components/shell/PageHeader";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { Markdown } from "@/components/ui/Markdown";
import { Mermaid } from "@/components/ui/Mermaid";
import { useProfiles } from "@/lib/profile";
import { useProfile } from "@/lib/queries";
import type { DiagramData } from "@/lib/types";
import { useArtifact } from "@/lib/useArtifact";

export default function Architecture() {
  const { active } = useProfiles();
  const pid = active?.id;
  const { data: record } = useProfile(pid);
  const [projectId, setProjectId] = useState("");
  const { state, job, run, exportHref } = useArtifact<DiagramData>(pid, "diagram", projectId, !!projectId);
  const diagram = state?.data;

  return (
    <>
      <PageHeader title="Architecture" description="A likely architecture for each project. Dashed nodes are assumptions, not facts from your resume." />
      {!pid || !record ? <NoProfile /> : (
        <div className="space-y-6">
          <ProjectPicker projects={record.profile.projects} value={projectId} onPick={setProjectId} />
          {projectId && <RunBar state={state} job={job as never} onRun={run} runLabel="Draw architecture" redoLabel="Redraw" runningTitle="Drawing and checking the diagram" exportHref={exportHref} />}
          {projectId && !diagram && job.status !== "running" && <EmptyState icon={Compass} title="Your diagram is ready to draw" text="Interviewers love when you can sketch your system. CrackMate drafts one from your project and labels every guess." />}
          {diagram && (
            <>
              <Card className="overflow-hidden"><Mermaid source={diagram.diagram} /></Card>
              <details className="rounded-[var(--radius-card)] border border-line bg-surface px-4 py-3 text-sm">
                <summary className="cursor-pointer font-medium text-ink">Mermaid source</summary>
                <pre className="mt-3 overflow-x-auto rounded-[var(--radius-control)] bg-[#150020] p-4 font-mono text-[13px] text-[#eadcf7]">{diagram.diagram}</pre>
              </details>
              <Card className="border-amber-200 bg-warn-tint"><h3 className="mb-1 font-semibold text-ink">Assumptions to confirm</h3><Markdown>{diagram.assumptions}</Markdown></Card>
            </>
          )}
        </div>
      )}
    </>
  );
}
