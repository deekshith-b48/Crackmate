"use client";
import { Play } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Checkbox, Field, Input } from "@/components/ui/Field";
import { StepGenerating } from "@/components/ui/StepGenerating";
import { Tabs } from "@/components/ui/Tabs";
import { useJob } from "@/lib/stream";
import type { InterviewOptions, InterviewView } from "@/lib/types";

const SELECT = "h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 text-sm text-ink";

export function InterviewSetup({ pid, options, hasKey, onCreated }: { pid: string; options: InterviewOptions; hasKey: boolean; onCreated: (id: string) => void }) {
  const [f, setF] = useState({ mode: options.modes[0], topic: options.topics[0] ?? "", project_id: options.projects[0]?.id ?? "", difficulty: "Basics", budget: 5, coach: true, spoken: false, weak_areas: "", probe_claims: options.open_claims > 0, consent: false });
  const job = useJob<InterviewView>();
  const set = (patch: Partial<typeof f>) => setF((old) => ({ ...old, ...patch }));
  const needsProject = f.mode === "Project deep-dive";
  const needsTopic = !["DSA reasoning", "System design", "Project deep-dive"].includes(f.mode);

  async function start() {
    const out = await job.run(`/api/profiles/${pid}/interviews`, f);
    if (out) onCreated(out.id);
  }

  if (job.status === "running") return <StepGenerating title="Preparing your interview questions" steps={job.steps} running startedAt={job.startedAt} />;
  return (
    <Card className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Interview mode" htmlFor="mode"><select id="mode" className={SELECT} value={f.mode} onChange={(e) => set({ mode: e.target.value })}>{options.modes.map((m) => <option key={m}>{m}</option>)}</select></Field>
        {needsProject && <Field label="Project" htmlFor="project"><select id="project" className={SELECT} value={f.project_id} onChange={(e) => set({ project_id: e.target.value })}>{options.projects.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></Field>}
        {needsTopic && <Field label="Topic" htmlFor="topic"><select id="topic" className={SELECT} value={f.topic} onChange={(e) => set({ topic: e.target.value })}>{options.topics.map((t) => <option key={t}>{t}</option>)}</select></Field>}
        <div><p className="mb-1.5 text-sm font-medium text-ink">Difficulty</p><div className="-mb-6"><Tabs tabs={options.levels.map((l) => ({ id: l, label: l }))} value={f.difficulty} onChange={(difficulty) => set({ difficulty })} /></div></div>
        <Field label="Number of questions" htmlFor="budget" hint="Adaptive follow-ups count toward this."><Input id="budget" type="number" min={1} max={10} value={f.budget} onChange={(e) => set({ budget: Math.max(1, Math.min(10, Number(e.target.value) || 1)) })} /></Field>
        <div><p className="mb-1.5 text-sm font-medium text-ink">Feedback timing</p><div className="-mb-6"><Tabs tabs={[{ id: "coach", label: "Coach (after each)" }, { id: "sim", label: "Simulation (at the end)" }]} value={f.coach ? "coach" : "sim"} onChange={(v) => set({ coach: v === "coach" })} /></div></div>
      </div>
      <Field label="Areas to focus on (optional)" htmlFor="weak"><Input id="weak" maxLength={1000} value={f.weak_areas} onChange={(e) => set({ weak_areas: e.target.value })} placeholder="Caching, SQL joins…" /></Field>
      <div className="space-y-3">
        <Checkbox checked={f.spoken} onChange={(e) => set({ spoken: e.target.checked })} label="Read each question aloud" />
        {options.open_claims > 0 && <Checkbox checked={f.probe_claims} onChange={(e) => set({ probe_claims: e.target.checked })} label={`Probe my ${options.open_claims} undefended resume claims (from Claim Checker)`} />}
        <Checkbox checked={f.consent} onChange={(e) => set({ consent: e.target.checked })} label="I understand that audio is sent to Groq for transcription and only answers I confirm are evaluated. Audio is never saved." />
      </div>
      {job.status === "error" && <p role="alert" className="text-sm text-bad">{job.error}</p>}
      <div className="flex items-center gap-3">
        <Button variant="primary" onClick={start} disabled={!f.consent || !hasKey || (needsProject && !f.project_id)}><Play className="size-4" /> Start interview</Button>
        {!hasKey && <span className="text-sm text-warn">Add your Groq key to start.</span>}
      </div>
      <p className="text-xs text-muted">English only. For preparation and mock practice. Typed answers are available throughout.</p>
    </Card>
  );
}
