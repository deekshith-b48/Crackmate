"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { BookOpen, CheckCircle2, Download, RefreshCw, Sparkles, Wand2 } from "lucide-react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { useToast } from "@/components/ui/Toast";
import { api, API_BASE } from "@/lib/api";
import type { Status } from "@/lib/profile";
import { useJob } from "@/lib/stream";
import type { LessonRef, LessonState } from "@/lib/types";
import { LessonViewer } from "./LessonViewer";

const params = (ref: LessonRef) => new URLSearchParams(Object.entries(ref).filter(([, v]) => v) as [string, string][]).toString();

/** One lesson: load it, generate it with live progress, or reuse the shared copy instantly. */
export function LessonPanel({ pid, lessonRef }: { pid: string; lessonRef: LessonRef }) {
  const client = useQueryClient();
  const toast = useToast();
  const key = ["lesson", pid, lessonRef];
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: () => api.get<Status>("/api/status") });
  const { data: state, isLoading } = useQuery({ queryKey: key, queryFn: () => api.get<LessonState>(`/api/profiles/${pid}/lessons?${params(lessonRef)}`) });
  const job = useJob<LessonState>();
  const noKey = status && !status.has_key;

  async function go(options: { regenerate?: boolean; tailor?: boolean } = {}) {
    const next = await job.run(`/api/profiles/${pid}/lessons/generate`, { ...lessonRef, ...options });
    if (!next) return;
    client.setQueryData(key, next);
    client.invalidateQueries({ queryKey: ["overview", pid] });
    client.invalidateQueries({ queryKey: ["dashboard", pid] });
    toast("good", next.fresh ? "Lesson written and saved." : "Lesson loaded.");
  }

  async function toggleComplete() {
    try {
      const next = await api.post<LessonState>(`/api/profiles/${pid}/lessons/complete`, { ...lessonRef, completed: !state?.item?.completed });
      client.setQueryData(key, next);
      client.invalidateQueries({ queryKey: ["overview", pid] });
      client.invalidateQueries({ queryKey: ["dashboard", pid] });
    } catch (error) {
      toast("bad", error instanceof Error ? error.message : "Could not update progress.");
    }
  }

  if (job.status === "running") return <StepGenerating title={state?.item ? "Refreshing your lesson" : "Writing your lesson"} steps={job.steps} running startedAt={job.startedAt} />;
  if (isLoading || !state) return <div className="h-40 animate-shimmer rounded-[var(--radius-card)] shimmer" aria-label="Loading lesson" />;

  const instant = state.shared_available;
  const primary = state.status === "current" ? null : instant ? "Load shared lesson (instant)" : state.item ? "Regenerate lesson" : "Generate lesson";
  const disabled = noKey && !instant;

  return (
    <div className="space-y-6">
      {job.status === "error" && <p role="alert" className="rounded-[var(--radius-control)] bg-bad-tint p-3 text-sm text-bad">{job.error} Your saved work is untouched.</p>}
      {!state.item ? (
        <EmptyState icon={BookOpen} title={state.title} text={instant ? "A ready-made lesson is available and loads instantly." : "Ready to write. This takes about half a minute and is saved for next time."}
          action={<div className="flex flex-col items-center gap-2"><Button variant="primary" onClick={() => go()} disabled={disabled}><Sparkles className="size-4" /> {primary}</Button>{disabled && <p className="text-xs text-warn">Add your Groq key to enable generation.</p>}</div>} />
      ) : (
        <>
          <div className="flex flex-wrap items-center gap-2 border-b border-line pb-4">
            <h2 className="mr-auto text-xl font-semibold text-ink">{state.item.title}</h2>
            {state.status === "current" ? <Badge tone="good">Saved · {state.item.model.split("/").pop()}</Badge> : <Badge tone="warn">Outdated · inputs changed</Badge>}
            {primary && <Button variant="primary" size="sm" onClick={() => go()} disabled={disabled}>{primary}</Button>}
            {state.status === "current" && <Button size="sm" onClick={toggleComplete}>{state.item.completed ? <><CheckCircle2 className="size-4 text-good" /> Completed</> : "Mark complete"}</Button>}
            <Button size="sm" onClick={() => go({ regenerate: true })} disabled={!!noKey}><RefreshCw className="size-4" /> Regenerate</Button>
            <a href={`${API_BASE}/api/profiles/${pid}/export/lesson?${params(lessonRef)}`} download><Button size="sm"><Download className="size-4" /> Download</Button></a>
            {state.can_tailor && <Button size="sm" onClick={() => go({ regenerate: true, tailor: true })} disabled={!!noKey} title="Rewrites the lesson using your stack and target role. Slower, and private to this profile."><Wand2 className="size-4" /> Tailor to my resume</Button>}
          </div>
          <LessonViewer pid={pid} lesson={state.item} />
        </>
      )}
    </div>
  );
}
