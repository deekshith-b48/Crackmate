"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, ChevronDown, Layers } from "lucide-react";
import { useEffect, useState } from "react";
import { LessonPanel } from "@/components/learn/LessonPanel";
import { NoProfile } from "@/components/learn/NoProfile";
import { ProjectPicker } from "@/components/learn/ProjectPicker";
import { ClarifyForm } from "@/components/learn/ClarifyForm";
import { RepoInsights } from "@/components/learn/RepoInsights";
import { PageHeader } from "@/components/shell/PageHeader";
import { Button } from "@/components/ui/Button";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { useToast } from "@/components/ui/Toast";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useProfiles, type Status } from "@/lib/profile";
import { useProfile } from "@/lib/queries";
import { useJob } from "@/lib/stream";
import type { SectionRow } from "@/lib/types";
import { useQueryParam } from "@/lib/useQueryParam";

export default function Projects() {
  const { active } = useProfiles();
  const pid = active?.id;
  const { data: record } = useProfile(pid);
  const client = useQueryClient();
  const toast = useToast();
  const [projectId, setProjectId] = useState("");
  const [section, setSection] = useState("Project story");
  const [showClarify, setShowClarify] = useState(false);
  const projectFromUrl = useQueryParam("project");
  const sectionFromUrl = useQueryParam("section");
  useEffect(() => { if (projectFromUrl) setProjectId(projectFromUrl); }, [projectFromUrl]);
  useEffect(() => { if (sectionFromUrl) setSection(sectionFromUrl); }, [sectionFromUrl]);
  const job = useJob<{ done: number; failed: string[] }>();
  const { data: status } = useQuery({ queryKey: ["status"], queryFn: () => api.get<Status>("/api/status") });
  const project = record?.profile.projects.find((p) => p.id === projectId);
  const { data: rows } = useQuery({ queryKey: ["overview", pid, projectId], queryFn: () => api.get<SectionRow[]>(`/api/profiles/${pid}/lessons/overview?project_id=${projectId}`), enabled: !!pid && !!project });

  async function generateAll() {
    const out = await job.run(`/api/profiles/${pid}/lessons/generate-all`, { project_id: projectId });
    if (!out) return;
    client.invalidateQueries({ queryKey: ["overview", pid] });
    client.invalidateQueries({ queryKey: ["lesson", pid] });
    toast(out.failed.length ? "bad" : "good", `${out.done} sections generated.` + (out.failed.length ? ` Could not finish: ${out.failed.join(", ")}. Try those again.` : ""));
  }

  const saved = rows?.filter((r) => r.status === "current").length ?? 0;
  return (
    <>
      <PageHeader title="Projects" description="Learn the concepts behind each project, then practise explaining your decisions." />
      {!pid || !record ? <NoProfile /> : (
        <div className="space-y-6">
          <ProjectPicker projects={record.profile.projects} value={projectId} onPick={(id) => { setProjectId(id); setSection("Project story"); }} />
          {project && (
            <>
              <div className="flex flex-wrap items-center justify-between gap-3">
                <p className="text-sm text-muted">{saved} of 6 sections saved and current</p>
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => setShowClarify(!showClarify)} aria-expanded={showClarify}>Clarify the project <ChevronDown className={cn("size-4 transition-transform", showClarify && "rotate-180")} /></Button>
                  <Button variant="primary" size="sm" onClick={generateAll} loading={job.status === "running"} disabled={!status?.has_key} title="Runs up to three sections at the same time."><Layers className="size-4" /> Generate all missing sections</Button>
                </div>
              </div>
              {job.status === "running" && <StepGenerating title="Writing your project sections" steps={job.steps} running startedAt={job.startedAt} />}
              <RepoInsights key={projectId} pid={pid} projectId={projectId} />
              {showClarify && <ClarifyForm pid={pid} record={record} project={project} onDone={() => setShowClarify(false)} />}
              <div className="flex flex-wrap gap-2" role="tablist" aria-label="Project section">
                {(rows ?? []).map((r) => (
                  <button key={r.section} role="tab" aria-selected={r.section === section} onClick={() => setSection(r.section)} title={r.scope}
                    className={cn("flex items-center gap-1.5 rounded-[var(--radius-control)] border px-3 py-1.5 text-sm font-medium transition-colors duration-150", r.section === section ? "border-brand-600 bg-brand-50 text-brand-700" : "border-line bg-surface text-body hover:bg-slate-50")}>
                    {r.status === "current" ? <Check className="size-3.5 text-good" /> : <span className={cn("size-2 rounded-full", r.status === "outdated" ? "bg-warn" : "bg-slate-300")} />}
                    {r.section}
                  </button>
                ))}
              </div>
              <LessonPanel key={`${projectId}:${section}`} pid={pid} lessonRef={{ kind: "project", project_id: projectId, section }} />
            </>
          )}
        </div>
      )}
    </>
  );
}
