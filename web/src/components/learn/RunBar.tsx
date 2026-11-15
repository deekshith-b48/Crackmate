"use client";
import { useQuery } from "@tanstack/react-query";
import { Download, RefreshCw, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { api } from "@/lib/api";
import type { Status } from "@/lib/profile";
import type { useJob } from "@/lib/stream";
import type { ArtifactState } from "@/lib/types";

type Props = { state?: ArtifactState<unknown>; job: ReturnType<typeof useJob<ArtifactState<never>>>; onRun: (regenerate: boolean) => void; runLabel: string; redoLabel: string; runningTitle: string; exportHref: string };

export function RunBar({ state, job, onRun, runLabel, redoLabel, runningTitle, exportHref }: Props) {
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: () => api.get<Status>("/api/status") });
  const noKey = !!status && !status.has_key;
  if (job.status === "running") return <StepGenerating title={runningTitle} steps={job.steps} running startedAt={job.startedAt} />;
  return (
    <div className="space-y-3">
      {job.status === "error" && <p role="alert" className="rounded-[var(--radius-control)] bg-bad-tint p-3 text-sm text-bad">{job.error}</p>}
      {state?.status === "outdated" && <p className="rounded-[var(--radius-control)] bg-warn-tint p-3 text-sm text-warn">Outdated: your profile changed since this was made. Redo it to update.</p>}
      <div className="flex flex-wrap items-center gap-2">
        {state?.data ? (
          <>
            <Badge tone={state.status === "current" ? "good" : "warn"}>{state.status === "current" ? "Saved" : "Outdated"} · {state.model?.split("/").pop()}</Badge>
            <Button size="sm" onClick={() => onRun(true)} disabled={noKey}><RefreshCw className="size-4" /> {redoLabel}</Button>
            <a href={exportHref} download><Button size="sm"><Download className="size-4" /> Download</Button></a>
          </>
        ) : (
          <>
            <Button variant="primary" onClick={() => onRun(false)} disabled={noKey}><Sparkles className="size-4" /> {runLabel}</Button>
            {noKey && <span className="text-sm text-warn">Add your Groq key to enable this.</span>}
          </>
        )}
      </div>
    </div>
  );
}
